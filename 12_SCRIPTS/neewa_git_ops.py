"""Governed Git and GitHub operations. No arbitrary commands or flags."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
AUTH = SourceFileLoader("neewa_authorization_git", str(SCRIPTS / "neewa_authorization.py")).load_module()
AUTHORIZED = AUTH.AUTHORIZED
decide = AUTH.decide
find_repository = AUTH.find_repository
load_registry = AUTH.load_registry
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
GIT_TIMEOUT = 60
GH_TIMEOUT = 90
SECRET_NAMES = {".env", "credentials.json", "id_rsa", "id_ed25519"}
BRANCH_RE = re.compile(r"^(feat|fix|test)/[A-Za-z0-9._/-]+$")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_operation_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"GIT-{stamp}-{uuid.uuid4().hex[:8].upper()}"


def receipt(**kwargs) -> dict:
    row = {
        "schema_version": 1,
        "operation_id": kwargs.get("operation_id") or new_operation_id(),
        "mission_id": kwargs.get("mission_id"),
        "repository": kwargs.get("repository"),
        "operation": kwargs.get("operation"),
        "authorization": kwargs.get("authorization") or {},
        "executor": kwargs.get("executor") or "neewa-git-ops",
        "source_sha": kwargs.get("source_sha"),
        "destination_sha": kwargs.get("destination_sha"),
        "status": kwargs.get("status") or "FAILED",
        "created_at": utc_now(),
        "verification": kwargs.get("verification") or {},
        "failure_reason": kwargs.get("failure_reason"),
        "public_listener": False,
        "unrestricted_shell": False,
        "forced": False,
    }
    extra = kwargs.get("extra")
    if extra:
        row.update(extra)
    return row


def run_git(args: list[str], cwd: Path, timeout: int = GIT_TIMEOUT) -> subprocess.CompletedProcess:
    if any(flag in args for flag in ("--force", "-f", "--force-with-lease", "--delete", "-D")):
        raise ValueError("force/delete git flags are not permitted")
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def run_gh(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    if any(flag in args for flag in ("--admin", "--delete-branch")):
        raise ValueError("admin/delete gh flags are not permitted")
    env = os.environ.copy()
    return subprocess.run(
        ["gh", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=GH_TIMEOUT,
        check=False,
        env=env,
    )


def git_sha(repo: Path, ref: str = "HEAD") -> str | None:
    completed = run_git(["rev-parse", ref], repo)
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def remote_url(repo: Path) -> str:
    completed = run_git(["remote", "get-url", "origin"], repo)
    return (completed.stdout or "").strip()


def ls_remote(repo: Path, branch: str) -> str | None:
    completed = run_git(["ls-remote", "origin", f"refs/heads/{branch}"], repo)
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    return completed.stdout.split()[0]


def is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    completed = run_git(["merge-base", "--is-ancestor", ancestor, descendant], repo)
    return completed.returncode == 0


def authorize(operation: str, job: dict) -> tuple[dict, dict | None]:
    auth = decide(
        operation=operation,
        repo=str(job.get("repo") or ""),
        source_branch=job.get("source_branch") or job.get("branch"),
        destination_branch=job.get("destination_branch") or job.get("head") or job.get("branch"),
        expected_local_sha=job.get("expected_local_sha"),
        expected_remote_sha=job.get("expected_remote_sha"),
        owner_authorization=job.get("owner_decision"),
        required_validation=job.get("required_validation"),
    )
    if auth.get("decision") != AUTHORIZED:
        return (
            receipt(
                operation_id=job.get("operation_id") or job.get("job_id"),
                mission_id=job.get("mission_id"),
                repository=job.get("repo"),
                operation=operation,
                authorization=auth,
                status="BLOCKED",
                failure_reason=auth.get("reason"),
            ),
            None,
        )
    path = Path(str(job.get("repo")))
    if not path.is_dir():
        auth["decision"] = "DENIED"
        return (
            receipt(
                operation_id=job.get("job_id"),
                mission_id=job.get("mission_id"),
                repository=str(path),
                operation=operation,
                authorization=auth,
                status="BLOCKED",
                failure_reason="MISSING_REPO",
            ),
            None,
        )
    row = find_repository(str(path), load_registry())
    expected_remote = (row or {}).get("authorized_remote")
    actual = remote_url(path)
    if expected_remote and actual:
        if AUTH._norm_remote(actual) != AUTH._norm_remote(str(expected_remote)):
            return (
                receipt(
                    operation_id=job.get("job_id"),
                    mission_id=job.get("mission_id"),
                    repository=str(path),
                    operation=operation,
                    authorization=auth,
                    status="BLOCKED",
                    failure_reason="REMOTE_MISMATCH",
                    extra={"actual_remote": actual},
                ),
                None,
            )
    return {}, path


def git_fetch(job: dict) -> dict:
    blocked, path = authorize("git_fetch", job)
    if path is None:
        return blocked
    before = git_sha(path)
    completed = run_git(["fetch", "origin"], path)
    status = "COMPLETED" if completed.returncode == 0 else "FAILED"
    return receipt(
        operation_id=job.get("job_id"),
        mission_id=job.get("mission_id"),
        repository=str(path),
        operation="git_fetch",
        authorization=decide(operation="git_fetch", repo=str(path)),
        source_sha=before,
        destination_sha=git_sha(path),
        status=status,
        verification={"returncode": completed.returncode},
        failure_reason=None if status == "COMPLETED" else (completed.stderr or completed.stdout)[:400],
    )


def git_pull(job: dict) -> dict:
    blocked, path = authorize("git_pull", job)
    if path is None:
        return blocked
    before = git_sha(path)
    completed = run_git(["pull", "--ff-only", "origin", job.get("source_branch") or "HEAD"], path)
    status = "COMPLETED" if completed.returncode == 0 else "FAILED"
    return receipt(
        operation_id=job.get("job_id"),
        mission_id=job.get("mission_id"),
        repository=str(path),
        operation="git_pull",
        authorization=decide(operation="git_pull", repo=str(path), source_branch=job.get("source_branch")),
        source_sha=before,
        destination_sha=git_sha(path),
        status=status,
        verification={"ff_only": True},
        failure_reason=None if status == "COMPLETED" else (completed.stderr or completed.stdout)[:400],
    )


def git_create_feature_branch(job: dict) -> dict:
    blocked, path = authorize("git_create_feature_branch", job)
    if path is None:
        return blocked
    branch = str(job.get("source_branch") or job.get("branch") or "")
    expected = job.get("expected_local_sha")
    head = git_sha(path)
    if expected and head and not head.lower().startswith(expected.lower()) and not expected.lower().startswith(head.lower()[: len(expected)]):
        return receipt(
            operation_id=job.get("job_id"),
            repository=str(path),
            operation="git_create_feature_branch",
            status="BLOCKED",
            source_sha=head,
            failure_reason="SHA_MISMATCH",
            mission_id=job.get("mission_id"),
        )
    created = run_git(["switch", "-c", branch], path)
    status = "COMPLETED" if created.returncode == 0 else "FAILED"
    return receipt(
        operation_id=job.get("job_id"),
        mission_id=job.get("mission_id"),
        repository=str(path),
        operation="git_create_feature_branch",
        authorization=decide(operation="git_create_feature_branch", repo=str(path), source_branch=branch),
        source_sha=head,
        destination_sha=git_sha(path),
        status=status,
        verification={"branch": branch},
        failure_reason=None if status == "COMPLETED" else (created.stderr or created.stdout)[:400],
    )


def git_commit_scoped_changes(job: dict) -> dict:
    blocked, path = authorize("git_commit_scoped_changes", job)
    if path is None:
        return blocked
    files = job.get("files") or job.get("selected_files") or []
    if isinstance(files, str):
        files = [files]
    if not files:
        return receipt(
            operation_id=job.get("job_id"),
            repository=str(path),
            operation="git_commit_scoped_changes",
            status="BLOCKED",
            failure_reason="EMPTY_FILE_SCOPE",
            mission_id=job.get("mission_id"),
        )
    for rel in files:
        raw = str(rel).replace("\\", "/")
        if raw.startswith("/") or re.match(r"^[a-zA-Z]:", raw) or ".." in Path(raw).parts:
            return receipt(
                operation_id=job.get("job_id"),
                repository=str(path),
                operation="git_commit_scoped_changes",
                status="BLOCKED",
                failure_reason="PATH_TRAVERSAL",
                mission_id=job.get("mission_id"),
            )
        if Path(raw).name.lower() in SECRET_NAMES:
            return receipt(
                operation_id=job.get("job_id"),
                repository=str(path),
                operation="git_commit_scoped_changes",
                status="BLOCKED",
                failure_reason="SECRET_FILE",
                mission_id=job.get("mission_id"),
            )
    before = git_sha(path)
    added = run_git(["add", "--", *files], path)
    if added.returncode != 0:
        return receipt(
            operation_id=job.get("job_id"),
            repository=str(path),
            operation="git_commit_scoped_changes",
            status="FAILED",
            source_sha=before,
            failure_reason=(added.stderr or "git add failed")[:400],
            mission_id=job.get("mission_id"),
        )
    message = str(job.get("message") or "chore: scoped governed commit")
    committed = run_git(["commit", "-m", message], path)
    status = "COMPLETED" if committed.returncode == 0 else "FAILED"
    return receipt(
        operation_id=job.get("job_id"),
        mission_id=job.get("mission_id"),
        repository=str(path),
        operation="git_commit_scoped_changes",
        authorization=decide(operation="git_commit_scoped_changes", repo=str(path), source_branch=job.get("source_branch")),
        source_sha=before,
        destination_sha=git_sha(path),
        status=status,
        verification={"files": list(files), "committed": status == "COMPLETED"},
        failure_reason=None if status == "COMPLETED" else (committed.stderr or committed.stdout)[:400],
    )


def git_verify_remote_state(job: dict) -> dict:
    blocked, path = authorize("git_verify_remote_state", job)
    if path is None:
        return blocked
    branch = str(job.get("source_branch") or job.get("destination_branch") or "")
    local = git_sha(path)
    remote = ls_remote(path, branch) if branch else None
    expected_local = job.get("expected_local_sha")
    expected_remote = job.get("expected_remote_sha")
    ok = True
    reason = None
    if expected_local and local and local.lower() != expected_local.lower() and not local.lower().startswith(expected_local.lower()):
        ok = False
        reason = "LOCAL_SHA_MISMATCH"
    if expected_remote and remote and remote.lower() != expected_remote.lower() and not remote.lower().startswith(expected_remote.lower()):
        ok = False
        reason = "REMOTE_SHA_MISMATCH"
    return receipt(
        operation_id=job.get("job_id"),
        mission_id=job.get("mission_id"),
        repository=str(path),
        operation="git_verify_remote_state",
        authorization=decide(operation="git_verify_remote_state", repo=str(path), source_branch=branch),
        source_sha=local,
        destination_sha=remote,
        status="COMPLETED" if ok else "BLOCKED",
        verification={"branch": branch, "local": local, "remote": remote},
        failure_reason=reason,
    )


def git_push_feature_branch(job: dict) -> dict:
    blocked, path = authorize("git_push_feature_branch", job)
    if path is None:
        return blocked
    branch = str(job.get("source_branch") or job.get("destination_branch") or "")
    if not BRANCH_RE.match(branch):
        return receipt(
            operation_id=job.get("job_id"),
            repository=str(path),
            operation="git_push_feature_branch",
            status="BLOCKED",
            failure_reason="UNAUTHORIZED_BRANCH",
            mission_id=job.get("mission_id"),
        )
    local = git_sha(path)
    expected = job.get("expected_local_sha")
    if expected and local and local.lower() != expected.lower() and not local.lower().startswith(expected.lower()):
        return receipt(
            operation_id=job.get("job_id"),
            repository=str(path),
            operation="git_push_feature_branch",
            status="BLOCKED",
            source_sha=local,
            failure_reason="SHA_MISMATCH",
            mission_id=job.get("mission_id"),
        )
    run_git(["fetch", "origin"], path)
    remote = ls_remote(path, branch)
    expected_remote = job.get("expected_remote_sha")
    if expected_remote and remote and remote.lower() != expected_remote.lower() and not remote.lower().startswith(expected_remote.lower()):
        return receipt(
            operation_id=job.get("job_id"),
            repository=str(path),
            operation="git_push_feature_branch",
            status="BLOCKED",
            source_sha=local,
            destination_sha=remote,
            failure_reason="STALE_REMOTE",
            mission_id=job.get("mission_id"),
        )
    if remote and local and not is_ancestor(path, remote, local):
        return receipt(
            operation_id=job.get("job_id"),
            repository=str(path),
            operation="git_push_feature_branch",
            status="BLOCKED",
            source_sha=local,
            destination_sha=remote,
            failure_reason="NON_FAST_FORWARD",
            mission_id=job.get("mission_id"),
        )
    pushed = run_git(["push", "--ff-only", "origin", f"refs/heads/{branch}:refs/heads/{branch}"], path)
    # git push --ff-only may be unsupported on older git; fall back to plain push after ancestor check
    if pushed.returncode != 0 and "unknown option" in (pushed.stderr or "").lower():
        pushed = run_git(["push", "origin", f"refs/heads/{branch}:refs/heads/{branch}"], path)
    after = ls_remote(path, branch)
    status = "COMPLETED" if pushed.returncode == 0 else "FAILED"
    return receipt(
        operation_id=job.get("job_id"),
        mission_id=job.get("mission_id"),
        repository=str(path),
        operation="git_push_feature_branch",
        authorization=decide(
            operation="git_push_feature_branch",
            repo=str(path),
            source_branch=branch,
            destination_branch=branch,
            expected_local_sha=local,
        ),
        source_sha=local,
        destination_sha=after,
        status=status,
        verification={"ff_only": True, "forced": False, "branch": branch},
        failure_reason=None if status == "COMPLETED" else (pushed.stderr or pushed.stdout)[:400],
    )


def git_create_pull_request(job: dict) -> dict:
    blocked, path = authorize("git_create_pull_request", job)
    if path is None:
        return blocked
    head = str(job.get("source_branch") or job.get("head") or "")
    base = str(job.get("destination_branch") or "main")
    title = str(job.get("title") or f"Integrate {head}")
    body = str(job.get("body") or "Governed NEEWA feature integration.")
    created = run_gh(
        ["pr", "create", "--base", base, "--head", head, "--title", title, "--body", body],
        path,
    )
    status = "COMPLETED" if created.returncode == 0 else "FAILED"
    url = (created.stdout or "").strip().splitlines()[-1] if created.stdout else None
    return receipt(
        operation_id=job.get("job_id"),
        mission_id=job.get("mission_id"),
        repository=str(path),
        operation="git_create_pull_request",
        authorization=decide(operation="git_create_pull_request", repo=str(path), source_branch=head, destination_branch=base),
        source_sha=git_sha(path),
        destination_sha=ls_remote(path, base),
        status=status,
        verification={"url": url, "base": base, "head": head},
        failure_reason=None if status == "COMPLETED" else (created.stderr or created.stdout)[:400],
        extra={"pull_request": url},
    )


def git_update_pull_request(job: dict) -> dict:
    blocked, path = authorize("git_update_pull_request", job)
    if path is None:
        return blocked
    number = str(job.get("pr_number") or "")
    args = ["pr", "edit", number]
    if job.get("title"):
        args.extend(["--title", str(job["title"])])
    if job.get("body"):
        args.extend(["--body", str(job["body"])])
    edited = run_gh(args, path)
    status = "COMPLETED" if edited.returncode == 0 else "FAILED"
    return receipt(
        operation_id=job.get("job_id"),
        mission_id=job.get("mission_id"),
        repository=str(path),
        operation="git_update_pull_request",
        authorization=decide(operation="git_update_pull_request", repo=str(path)),
        status=status,
        verification={"pr_number": number},
        failure_reason=None if status == "COMPLETED" else (edited.stderr or edited.stdout)[:400],
    )


def git_review_pull_request(job: dict) -> dict:
    blocked, path = authorize("git_review_pull_request", job)
    if path is None:
        return blocked
    number = str(job.get("pr_number") or "")
    event = str(job.get("review_event") or "COMMENT")
    if event not in {"COMMENT", "APPROVE", "REQUEST_CHANGES"}:
        return receipt(
            operation_id=job.get("job_id"),
            repository=str(path),
            operation="git_review_pull_request",
            status="BLOCKED",
            failure_reason="INVALID_REVIEW_EVENT",
            mission_id=job.get("mission_id"),
        )
    body = str(job.get("body") or "Governed review comment.")
    reviewed = run_gh(["pr", "review", number, f"--{event.lower().replace('_', '-')}", "--body", body], path)
    status = "COMPLETED" if reviewed.returncode == 0 else "FAILED"
    return receipt(
        operation_id=job.get("job_id"),
        mission_id=job.get("mission_id"),
        repository=str(path),
        operation="git_review_pull_request",
        authorization=decide(operation="git_review_pull_request", repo=str(path)),
        status=status,
        verification={"pr_number": number, "event": event, "identity": "neewa-git-ops"},
        failure_reason=None if status == "COMPLETED" else (reviewed.stderr or reviewed.stdout)[:400],
        extra={"independence_class": "same_github_account_not_independent"},
    )


def git_merge_approved_pull_request(job: dict) -> dict:
    blocked, path = authorize("git_merge_approved_pull_request", job)
    if path is None:
        return blocked
    if job.get("independent_rerun") == "IMPLEMENTER_CLAIMED":
        return receipt(
            operation_id=job.get("job_id"),
            repository=str(path),
            operation="git_merge_approved_pull_request",
            status="BLOCKED",
            failure_reason="IMPLEMENTER_CLAIMED_INSUFFICIENT",
            mission_id=job.get("mission_id"),
        )
    number = str(job.get("pr_number") or "")
    merged = run_gh(["pr", "merge", number, "--merge", "--delete-branch=false"], path)
    # --delete-branch=false might not exist; retry without it
    if merged.returncode != 0 and "unknown" in (merged.stderr or "").lower():
        merged = run_gh(["pr", "merge", number, "--merge"], path)
    status = "COMPLETED" if merged.returncode == 0 else "FAILED"
    main_sha = ls_remote(path, "main")
    return receipt(
        operation_id=job.get("job_id"),
        mission_id=job.get("mission_id"),
        repository=str(path),
        operation="git_merge_approved_pull_request",
        authorization=decide(
            operation="git_merge_approved_pull_request",
            repo=str(path),
            destination_branch="main",
        ),
        source_sha=git_sha(path),
        destination_sha=main_sha,
        status=status,
        verification={"pr_number": number, "strategy": "merge"},
        failure_reason=None if status == "COMPLETED" else (merged.stderr or merged.stdout)[:400],
    )


DISPATCH = {
    "git_fetch": git_fetch,
    "git_pull": git_pull,
    "git_create_feature_branch": git_create_feature_branch,
    "git_commit_scoped_changes": git_commit_scoped_changes,
    "git_push_feature_branch": git_push_feature_branch,
    "git_verify_remote_state": git_verify_remote_state,
    "git_create_pull_request": git_create_pull_request,
    "git_update_pull_request": git_update_pull_request,
    "git_review_pull_request": git_review_pull_request,
    "git_merge_approved_pull_request": git_merge_approved_pull_request,
}


def dispatch(job: dict) -> dict:
    action = str(job.get("action") or job.get("operation") or "")
    func = DISPATCH.get(action)
    if not func:
        return receipt(
            operation_id=job.get("job_id"),
            operation=action,
            status="FAILED",
            failure_reason=f"unknown git operation {action}",
            repository=job.get("repo"),
            mission_id=job.get("mission_id"),
        )
    return func(job)


def main() -> int:
    parser = argparse.ArgumentParser(description="NEEWA governed git operations")
    parser.add_argument("command", choices=("dispatch", *sorted(DISPATCH)))
    parser.add_argument("--job-file")
    parser.add_argument("--repo")
    parser.add_argument("--branch")
    parser.add_argument("--expected-local-sha")
    parser.add_argument("--expected-remote-sha")
    args = parser.parse_args()
    if args.command == "dispatch":
        job = json.loads(Path(args.job_file).read_text(encoding="utf-8"))
        result = dispatch(job)
    else:
        result = dispatch(
            {
                "action": args.command,
                "repo": args.repo,
                "source_branch": args.branch,
                "destination_branch": args.branch,
                "expected_local_sha": args.expected_local_sha,
                "expected_remote_sha": args.expected_remote_sha,
            }
        )
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") == "COMPLETED" else 2


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    raise SystemExit(main())
