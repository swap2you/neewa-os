"""Governed NEEWA Home / chatbot mission bridge.

Submits through the existing mission supervisor. Arbitrary chatbot text is not
authorization. A2/A3 objectives remain blocked unless standing registry auth applies.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
AUTO = SourceFileLoader("neewa_autonomy_home", str(SCRIPTS / "neewa_autonomy.py")).load_module()
MISSION = SourceFileLoader("neewa_mission_home", str(SCRIPTS / "neewa_mission.py")).load_module()
SEM = SourceFileLoader("neewa_action_semantics_home", str(SCRIPTS / "neewa_action_semantics.py")).load_module()

ALLOWED_ORIGINS = {"home", "chatbot", "conversation"}
DEFAULT_HOME_WORKSPACE = r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox"
CORE_HOST = os.environ.get("NEEWA_HOME_CORE", "ubuntu@neewa-core-01")
CORE_BRIDGE = "/opt/neewa/neewa-os/12_SCRIPTS/neewa_home_bridge.py"
SSH_TIMEOUT = 90


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def snapshot_dir() -> Path:
    override = os.environ.get("NEEWA_HOME_SNAPSHOT_DIR")
    if override:
        path = Path(override)
    else:
        path = Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or ".") / "NEEWA-Personal" / "missions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_snapshot(mission: dict) -> Path:
    public = snapshot_from_mission(mission)
    path = snapshot_dir() / "current.json"
    path.write_text(json.dumps(public, indent=2) + "\n", encoding="utf-8")
    return path


def snapshot_from_mission(mission: dict, job: dict | None = None) -> dict:
    job = job or {}
    validation = job.get("validation") if isinstance(job.get("validation"), dict) else {}
    council = job.get("council") if isinstance(job.get("council"), dict) else mission.get("council") or {}
    return {
        "schema_version": 1,
        "mission_id": mission.get("mission_id"),
        "state": mission.get("state"),
        "origin": mission.get("origin"),
        "objective": mission.get("owner_objective"),
        "implementation_job_id": mission.get("active_job_id") or (mission.get("job_ids") or [None])[-1],
        "validation_child_id": job.get("validation_child_id"),
        "independent_rerun": validation.get("independent_rerun"),
        "council": council.get("roles") if isinstance(council, dict) else council,
        "pull_request": (job.get("github") or {}).get("pull_request") or mission.get("pull_request"),
        "recovery": {
            "repair_cycles": mission.get("repair_cycles"),
            "last_failure": mission.get("last_failure_signature"),
            "history": (mission.get("failure_history") or [])[-5:],
        },
        "final_result": mission.get("terminal_result") or mission.get("state"),
        "artifacts": job.get("artifacts") or mission.get("evidence_locations") or [],
        "authorization_bypass": False,
        "updated_at": utc_now(),
    }


def should_dispatch_remote(root: Path | None) -> bool:
    if root is not None:
        return False
    if os.environ.get("NEEWA_HOME_DISPATCH", "core").strip().lower() == "local":
        return False
    return os.name == "nt"


def _ssh_json(payload: dict) -> dict:
    command = str(payload.get("command") or "").strip().lower()
    parts = ["python3", CORE_BRIDGE, command]
    if command == "submit":
        parts += [
            "--objective",
            str(payload.get("objective") or ""),
            "--origin",
            str(payload.get("origin") or "home"),
        ]
        if payload.get("workspace"):
            parts += ["--workspace", str(payload["workspace"])]
        if payload.get("project_id"):
            parts += ["--project-id", str(payload["project_id"])]
    elif command == "status":
        if payload.get("mission_id"):
            parts += ["--mission-id", str(payload["mission_id"])]
    else:
        return {"status": "BLOCKED", "reason": "UNKNOWN_COMMAND", "authorization_bypass": False}
    remote = " ".join(shlex.quote(p) for p in parts)
    completed = subprocess.run(
        [
            "ssh",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=8",
            CORE_HOST,
            remote,
        ],
        capture_output=True,
        text=True,
        timeout=SSH_TIMEOUT,
        check=False,
    )
    text = (completed.stdout or "").strip() or (completed.stderr or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        for line in reversed(text.splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
        return {
            "status": "BLOCKED",
            "reason": "CORE_BRIDGE_UNAVAILABLE",
            "detail": text[:400],
            "returncode": completed.returncode,
            "authorization_bypass": False,
        }


def submit(objective: str, *, origin: str = "home", workspace: str | None = None, project_id: str | None = None, root: Path | None = None) -> dict:
    origin = (origin or "home").strip().lower()
    if origin not in ALLOWED_ORIGINS:
        return {"status": "BLOCKED", "reason": "ORIGIN_NOT_ALLOWED", "authorization_bypass": False}
    text = (objective or "").strip()
    if not text:
        return {"status": "BLOCKED", "reason": "EMPTY_OBJECTIVE", "authorization_bypass": False}
    if not workspace:
        workspace = DEFAULT_HOME_WORKSPACE
    gate = AUTO.authorize_execution(
        approval_level="A1",
        owner_decision=None,
        prompt=text,
        repo=workspace or str(ROOT),
        write=True,
    )
    if not gate.get("allowed"):
        return {
            "status": "BLOCKED",
            "reason": gate.get("reason") or "AUTHORIZATION_DENIED",
            "needed": gate.get("needed"),
            "authorization": gate,
            "authorization_bypass": False,
            "mission_id": None,
        }
    if should_dispatch_remote(root):
        result = _ssh_json(
            {
                "command": "submit",
                "objective": text,
                "origin": origin,
                "workspace": workspace,
                "project_id": project_id,
            }
        )
        if isinstance(result, dict) and not result.get("mission_id") and isinstance(result.get("mission"), dict):
            result["mission_id"] = result["mission"].get("mission_id")
        return result
    try:
        mission = MISSION.create_mission(
            text,
            workspace=workspace,
            project_id=project_id,
            root=root,
            origin=origin,
            kind="sdlc",
            auto=AUTO,
        )
    except MISSION.DuplicateMission as exc:
        existing = MISSION.public_mission(exc.existing)
        snap = snapshot_from_mission(existing)
        write_snapshot(existing)
        return {
            "status": "RESUMED",
            "reason": "DUPLICATE_ACTIVE_MISSION",
            "mission": snap,
            "mission_id": snap.get("mission_id"),
            "authorization_bypass": False,
        }
    except MISSION.HostPathUnmounted as exc:
        return {"status": "BLOCKED", "reason": str(exc), "authorization_bypass": False}
    snap = snapshot_from_mission(mission)
    write_snapshot(mission)
    return {
        "status": "CREATED",
        "mission": snap,
        "mission_id": snap.get("mission_id"),
        "authorization_bypass": False,
        "authorization": gate,
    }


def status(mission_id: str | None = None, *, root: Path | None = None) -> dict:
    if should_dispatch_remote(root):
        return _ssh_json({"command": "status", "mission_id": mission_id})
    jobs_root = None
    try:
        jobs_root = MISSION.autonomy_root(root, auto=AUTO)
    except MISSION.HostPathUnmounted as exc:
        current = snapshot_dir() / "current.json"
        if current.is_file():
            return json.loads(current.read_text(encoding="utf-8"))
        return {"status": "BLOCKED", "reason": str(exc)}
    if mission_id:
        mission = MISSION.load_mission(mission_id, jobs_root)
        if not mission:
            return {"status": "MISSING", "mission_id": mission_id}
        job = None
        job_id = mission.get("active_job_id")
        if job_id:
            try:
                job = AUTO.resume_job(job_id, jobs_root)
            except Exception:
                job = None
        snap = snapshot_from_mission(mission, job)
        write_snapshot(mission)
        return snap
    current = snapshot_dir() / "current.json"
    if current.is_file():
        return json.loads(current.read_text(encoding="utf-8"))
    return {"status": "EMPTY"}


def dispatch_json(payload: dict) -> dict:
    command = str(payload.get("command") or "").strip().lower()
    if command == "submit":
        return submit(
            str(payload.get("objective") or ""),
            origin=str(payload.get("origin") or "home"),
            workspace=payload.get("workspace"),
            project_id=payload.get("project_id"),
            root=Path(payload["root"]) if payload.get("root") else None,
        )
    if command == "status":
        return status(payload.get("mission_id"), root=Path(payload["root"]) if payload.get("root") else None)
    return {"status": "BLOCKED", "reason": "UNKNOWN_COMMAND", "authorization_bypass": False}


def main() -> int:
    parser = argparse.ArgumentParser(description="NEEWA Home mission bridge")
    parser.add_argument("command", nargs="?", choices=("submit", "status"))
    parser.add_argument("--objective")
    parser.add_argument("--origin", default="home")
    parser.add_argument("--workspace")
    parser.add_argument("--project-id")
    parser.add_argument("--mission-id")
    parser.add_argument("--root")
    parser.add_argument("--json-stdin", action="store_true")
    args = parser.parse_args()
    if args.json_stdin:
        payload = json.loads(sys.stdin.read() or "{}")
        result = dispatch_json(payload)
        print(json.dumps(result, indent=2))
        return 0 if result.get("status") in {"CREATED", "RESUMED"} or result.get("mission_id") else 2
    if args.command == "submit":
        result = submit(
            args.objective or "",
            origin=args.origin,
            workspace=args.workspace,
            project_id=args.project_id,
            root=Path(args.root) if args.root else None,
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("status") in {"CREATED", "RESUMED"} else 2
    result = status(args.mission_id, root=Path(args.root) if args.root else None)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
