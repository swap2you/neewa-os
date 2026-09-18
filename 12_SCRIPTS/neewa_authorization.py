"""Approval-aware execution authorization for NEEWA.

Separates action risk (A0/A1/A2/A3) from execution authorization
(AUTHORIZED / APPROVAL_REQUIRED / DENIED). Standing owner authorization is
read only from the repository registry, never from job JSON owner_decision.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "11_CONFIG" / "repository_authorizations.json"

AUTHORIZED = "AUTHORIZED"
APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
DENIED = "DENIED"

FEATURE_PREFIX_RE = re.compile(r"^(feat|fix|test)/[A-Za-z0-9._/-]+$")
SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")

RISK = {
    "inspect": "A0",
    "git_fetch": "A0",
    "git_verify_remote_state": "A0",
    "git_pull": "A1",
    "git_create_feature_branch": "A1",
    "git_commit_scoped_changes": "A1",
    "execute_tests": "A0",
    "council_review": "A0",
    "git_push_feature_branch": "A2",
    "git_create_pull_request": "A2",
    "git_update_pull_request": "A2",
    "git_review_pull_request": "A1",
    "git_merge_approved_pull_request": "A2",
    "staging_acceptance": "A1",
    "bounded_recovery": "A1",
    "force_push": "A3",
    "delete_remote_branch": "A3",
    "rewrite_history": "A3",
    "deploy_production": "A2",
    "rotate_credentials": "A3",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_registry(path: Path | None = None) -> dict:
    env = os.environ.get("NEEWA_REPO_AUTH_PATH")
    target = path or (Path(env) if env else REGISTRY_PATH)
    if not target.is_file():
        return {"repositories": [], "denied_name_equals": []}
    return json.loads(target.read_text(encoding="utf-8"))


def _norm(path: str) -> str:
    text = os.path.expandvars(path or "").replace("/", "\\").strip().lower()
    while "\\\\" in text:
        text = text.replace("\\\\", "\\")
    return text.rstrip("\\")


def _norm_remote(url: str) -> str:
    text = (url or "").strip().lower().rstrip("/")
    if text.endswith(".git"):
        text = text[:-4]
    text = text.replace("git@github.com:", "https://github.com/")
    text = text.replace("ssh://git@github.com/", "https://github.com/")
    return text


def find_repository(repo: str, registry: dict | None = None) -> dict | None:
    registry = registry or load_registry()
    n_path = _norm(repo)
    n_remote = _norm_remote(repo)
    leaf = Path(repo.replace("/", "\\")).name.lower()
    for row in registry.get("repositories") or []:
        if leaf in {str(x).lower() for x in (registry.get("denied_name_equals") or [])}:
            return None
        if n_path == _norm(str(row.get("authorized_local_path") or "")):
            return row
        if n_remote and n_remote == _norm_remote(str(row.get("authorized_remote") or "")):
            return row
        if leaf and leaf == str(row.get("id") or "").lower():
            return row
        if leaf and leaf == str(row.get("repository_identity") or "").split("/")[-1].lower():
            return row
    return None


def is_denied_repo(repo: str, registry: dict | None = None) -> bool:
    registry = registry or load_registry()
    parts = [p for p in _norm(repo).split("\\") if p]
    denied = [str(x).lower() for x in (registry.get("denied_name_equals") or [])]
    return any(part in denied for part in parts)


def _valid_sha(value: str | None) -> bool:
    return bool(value and SHA_RE.fullmatch(value.strip()))


def decide(
    *,
    operation: str,
    repo: str,
    source_branch: str | None = None,
    destination_branch: str | None = None,
    expected_local_sha: str | None = None,
    expected_remote_sha: str | None = None,
    owner_authorization: str | None = None,
    required_validation: str | None = None,
    registry: dict | None = None,
) -> dict:
    """Return execution authorization. Job JSON owner_authorization is ignored."""
    _ = owner_authorization  # untrusted; registry is the only standing source
    op = (operation or "").strip()
    risk = RISK.get(op, "A2")
    base = {
        "schema_version": 1,
        "decision": DENIED,
        "operation": op,
        "risk": risk,
        "repository_id": None,
        "reason": None,
        "standing": False,
        "created_at": utc_now(),
        "required_validation": required_validation,
    }
    if not op:
        base["reason"] = "MISSING_OPERATION"
        return base
    if is_denied_repo(repo, registry):
        base["reason"] = "DENIED_REPO"
        return base
    row = find_repository(repo, registry)
    if not row:
        base["reason"] = "UNREGISTERED_REPOSITORY"
        return base
    base["repository_id"] = row.get("id")
    if op in set(row.get("always_denied_operations") or []):
        base["reason"] = "OPERATION_ALWAYS_DENIED"
        return base
    if op in {"force_push", "delete_remote_branch", "rewrite_history"}:
        base["reason"] = "OPERATION_ALWAYS_DENIED"
        return base
    dest = (destination_branch or source_branch or "").strip()
    protected = {str(b).lower() for b in (row.get("protected_branches") or [])}
    if op == "git_push_feature_branch" and dest.lower() in protected:
        base["reason"] = "PROTECTED_BRANCH"
        return base
    if op in {"git_push_feature_branch", "git_create_feature_branch"}:
        branch = (source_branch or dest).strip()
        prefixes = tuple(row.get("permitted_feature_branch_prefixes") or ["feat/", "fix/"])
        if not branch.startswith(prefixes) or not FEATURE_PREFIX_RE.match(branch):
            base["reason"] = "UNAUTHORIZED_BRANCH"
            return base
    if op in {
        "git_push_feature_branch",
        "git_commit_scoped_changes",
        "git_merge_approved_pull_request",
        "git_create_feature_branch",
    }:
        if expected_local_sha is not None and not _valid_sha(expected_local_sha):
            base["reason"] = "INVALID_LOCAL_SHA"
            return base
        if expected_remote_sha is not None and expected_remote_sha != "" and not _valid_sha(expected_remote_sha):
            base["reason"] = "INVALID_REMOTE_SHA"
            return base
    if op == "deploy_production" and not (row.get("deployment_policy") or {}).get("autonomous_production"):
        base["decision"] = APPROVAL_REQUIRED
        base["reason"] = "PRODUCTION_RELEASE_POLICY"
        return base
    standing = set(row.get("standing_operations") or [])
    if op in standing:
        base["decision"] = AUTHORIZED
        base["standing"] = True
        base["reason"] = "STANDING_AUTHORIZATION"
        return base
    if risk in {"A0", "A1"}:
        base["decision"] = AUTHORIZED
        base["reason"] = "ROUTINE_PERSONAL"
        return base
    base["decision"] = APPROVAL_REQUIRED
    base["reason"] = f"{risk}_OWNER_GATE"
    return base


def decide_from_job(job: dict, registry: dict | None = None) -> dict:
    return decide(
        operation=str(job.get("action") or job.get("operation") or ""),
        repo=str(job.get("repo") or job.get("authoritative_repo") or ""),
        source_branch=job.get("source_branch") or job.get("branch"),
        destination_branch=job.get("destination_branch") or job.get("head"),
        expected_local_sha=job.get("expected_local_sha") or job.get("base_sha"),
        expected_remote_sha=job.get("expected_remote_sha"),
        owner_authorization=job.get("owner_decision") or job.get("owner_authorization"),
        required_validation=job.get("required_validation"),
        registry=registry,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="NEEWA standing authorization")
    parser.add_argument("--job-file")
    parser.add_argument("--operation")
    parser.add_argument("--repo")
    parser.add_argument("--source-branch")
    parser.add_argument("--destination-branch")
    parser.add_argument("--expected-local-sha")
    parser.add_argument("--expected-remote-sha")
    args = parser.parse_args()
    if args.job_file:
        job = json.loads(Path(args.job_file).read_text(encoding="utf-8"))
        result = decide_from_job(job)
    else:
        result = decide(
            operation=args.operation or "",
            repo=args.repo or "",
            source_branch=args.source_branch,
            destination_branch=args.destination_branch,
            expected_local_sha=args.expected_local_sha,
            expected_remote_sha=args.expected_remote_sha,
        )
    print(json.dumps(result, indent=2))
    return 0 if result.get("decision") == AUTHORIZED else 2


if __name__ == "__main__":
    raise SystemExit(main())
