"""Enqueue or inspect NEEWA Windows-worker jobs on neewa-core-01.

The Windows worker polls this inbox over outbound Tailscale SSH.
Default path is the Hermes Docker workspace, which the sandbox can write.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HOST_ROOT = Path(
    "/home/ubuntu/.hermes/sandboxes/docker/default/workspace/windows-jobs"
)
SANDBOX_ROOT = Path("/workspace/windows-jobs")
HOST_WORKSPACE = HOST_ROOT.parent
SANDBOX_WORKSPACE = SANDBOX_ROOT.parent


def _same_directory(left: Path, right: Path) -> bool:
    try:
        if not left.is_dir() or not right.is_dir():
            return False
        if left.resolve() == right.resolve():
            return True
        left_stat = left.stat()
        right_stat = right.stat()
        return left_stat.st_dev == right_stat.st_dev and left_stat.st_ino == right_stat.st_ino
    except OSError:
        return False


def in_conversation_sandbox(
    *,
    sandbox_workspace: Path | None = None,
    host_workspace: Path | None = None,
) -> bool:
    """True when /workspace exists and is not the Ubuntu host directory.

    An empty host-shaped overlay inside the container must not count as the
    real mount. Compare identity with /workspace instead of existence alone.
    """
    sandbox_workspace = sandbox_workspace or SANDBOX_WORKSPACE
    host_workspace = host_workspace or HOST_WORKSPACE
    try:
        if not sandbox_workspace.is_dir():
            return False
        return not _same_directory(sandbox_workspace, host_workspace)
    except OSError:
        return sandbox_workspace.is_dir()


def is_unmounted_host_inbox(
    path: Path | str | None,
    *,
    sandbox_workspace: Path | None = None,
    host_workspace: Path | None = None,
) -> bool:
    if not path:
        return False
    text = str(path).replace("\\", "/")
    if "/home/ubuntu/.hermes/sandboxes/" not in text:
        return False
    return in_conversation_sandbox(
        sandbox_workspace=sandbox_workspace, host_workspace=host_workspace
    )


def path_mapping() -> dict:
    return {
        "canonical_inbox": str(resolve_inbox_root()),
        "sandbox_inbox": str(SANDBOX_ROOT),
        "host_inbox": str(HOST_ROOT),
        "in_conversation_sandbox": in_conversation_sandbox(),
        "note": (
            "Conversation must use /workspace/windows-jobs. That bind-mount is "
            "the same host directory "
            "/home/ubuntu/.hermes/sandboxes/docker/default/workspace/windows-jobs. "
            "The host-shaped path is not mounted inside the sandbox; creating it "
            "there would be an invisible overlay."
        ),
    }


def resolve_inbox_root(
    explicit: str | None = None,
    *,
    environ: dict | None = None,
    sandbox_root: Path | None = None,
    host_root: Path | None = None,
) -> Path:
    """Prefer the Hermes sandbox bind-mount so Conversation jobs reach the worker.

    Inside the Docker sandbox, python can also create the host-shaped path as a
    local overlay. That copy is invisible to the Windows worker, so /workspace
    wins whenever that directory exists.
    """
    sandbox_root = sandbox_root or SANDBOX_ROOT
    host_root = host_root or HOST_ROOT
    environ = os.environ if environ is None else environ
    if explicit:
        return Path(explicit)
    env = environ.get("NEEWA_WINDOWS_JOB_INBOX") if hasattr(environ, "get") else None
    if env:
        return Path(env)
    if sandbox_root.parent.exists() and sandbox_root.parent.is_dir():
        return sandbox_root
    return host_root


DEFAULT_ROOT = resolve_inbox_root()
ALLOWED = {
    "ping",
    "capability_inventory",
    "personal_artifact",
    "portfolio_inventory",
    "workspace_inventory",
    "cursor_call",
    "repo_preflight",
    "create_scoped_repair_workspace",
    "review_scoped_repair_patch",
    "apply_scoped_repair_patch",
    "cleanup_scoped_repair_workspace",
    "git_fetch",
    "git_pull",
    "git_create_feature_branch",
    "git_commit_scoped_changes",
    "git_push_feature_branch",
    "git_verify_remote_state",
    "git_create_pull_request",
    "git_update_pull_request",
    "git_review_pull_request",
    "git_merge_approved_pull_request",
    "home_mission_submit",
    "home_mission_status",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_dirs(root: Path) -> None:
    for name in ("inbox", "processing", "done", "failed"):
        (root / name).mkdir(parents=True, exist_ok=True)


def enqueue(
    job_id: str,
    action: str,
    approval: str = "A1",
    root: Path = DEFAULT_ROOT,
    extra: dict | None = None,
) -> Path:
    if action not in ALLOWED:
        raise ValueError(f"action {action} is not allowlisted")
    if approval in {"A2", "A3"}:
        extra_payload = extra or {}
        receipt_mod = SourceFileLoader(
            "neewa_a2_receipt_auth_inbox",
            str(ROOT / "12_SCRIPTS" / "neewa_a2_receipt_auth.py"),
        ).load_module()
        structured = extra_payload.get("authorization")
        if receipt_mod.authorization_object_is_well_formed(structured):
            pass
        else:
            auth_mod = SourceFileLoader(
                "neewa_authorization_inbox", str(ROOT / "12_SCRIPTS" / "neewa_authorization.py")
            ).load_module()
            payload = {"action": action, "approval": approval, **extra_payload}
            gate = auth_mod.decide_from_job(payload)
            if gate.get("decision") != auth_mod.AUTHORIZED:
                raise ValueError(
                    f"A2/A3 requires standing authorization or owner approval ({gate.get('reason')})"
                )
    ensure_dirs(root)
    for folder in ("inbox", "processing", "done", "failed"):
        existing = root / folder / f"{job_id}.json"
        if existing.is_file():
            raise ValueError(f"duplicate job_id {job_id} already exists in {folder}")
    payload = {
        "schema_version": 1,
        "job_id": job_id,
        "action": action,
        "approval": approval,
        "created_at": utc_now(),
        "coordinator": "neewa-core-01",
        "target": "neewa-edge-01",
        "public_listener": False,
    }
    if extra:
        for key, value in extra.items():
            if key in payload:
                continue
            payload[key] = value
    path = root / "inbox" / f"{job_id}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="NEEWA Windows job inbox")
    parser.add_argument("command", choices=("enqueue", "status"))
    parser.add_argument("--job-id")
    parser.add_argument("--action", default="personal_artifact")
    parser.add_argument("--approval", default="A1")
    parser.add_argument("--root", default=str(resolve_inbox_root()))
    parser.add_argument("--repo")
    parser.add_argument("--prompt")
    parser.add_argument("--timeout-sec", type=int)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--expected-path", action="append", dest="expected_paths")
    args = parser.parse_args()
    root = Path(args.root)
    ensure_dirs(root)
    if args.command == "enqueue":
        if not args.job_id:
            raise SystemExit("--job-id is required")
        extra = {}
        if args.repo:
            extra["repo"] = args.repo
        if args.prompt:
            extra["prompt"] = args.prompt
        if args.timeout_sec is not None:
            # Preserve timeout_sec=0 (unlimited; no elapsed-time kill on the worker).
            extra["timeout_sec"] = args.timeout_sec
        if args.write:
            extra["write"] = True
        if args.expected_paths:
            extra["expected_paths"] = args.expected_paths
        path = enqueue(args.job_id, args.action, args.approval, root, extra or None)
        print(path)
        return 0
    for folder in ("inbox", "processing", "done", "failed"):
        files = sorted(p.name for p in (root / folder).glob("*.json"))
        print(f"{folder}: {len(files)}")
        for name in files:
            print(f"  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
