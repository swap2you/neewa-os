"""Enqueue or inspect NEEWA Windows-worker jobs on neewa-core-01.

The Windows worker polls this inbox over outbound Tailscale SSH.
Default path is the Hermes Docker workspace, which the sandbox can write.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_ROOT = Path(
    os.environ.get(
        "NEEWA_WINDOWS_JOB_INBOX",
        "/home/ubuntu/.hermes/sandboxes/docker/default/workspace/windows-jobs",
    )
)
ALLOWED = {"ping", "capability_inventory", "personal_artifact", "portfolio_inventory"}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_dirs(root: Path) -> None:
    for name in ("inbox", "processing", "done", "failed"):
        (root / name).mkdir(parents=True, exist_ok=True)


def enqueue(job_id: str, action: str, approval: str = "A1", root: Path = DEFAULT_ROOT) -> Path:
    if action not in ALLOWED:
        raise ValueError(f"action {action} is not allowlisted")
    if approval in {"A2", "A3"}:
        raise ValueError("A2/A3 jobs cannot be enqueued for unattended Windows execution")
    ensure_dirs(root)
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
    path = root / "inbox" / f"{job_id}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="NEEWA Windows job inbox")
    parser.add_argument("command", choices=("enqueue", "status"))
    parser.add_argument("--job-id")
    parser.add_argument("--action", default="personal_artifact")
    parser.add_argument("--approval", default="A1")
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    args = parser.parse_args()
    root = Path(args.root)
    ensure_dirs(root)
    if args.command == "enqueue":
        if not args.job_id:
            raise SystemExit("--job-id is required")
        path = enqueue(args.job_id, args.action, args.approval, root)
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
