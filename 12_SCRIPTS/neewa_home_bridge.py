"""Governed NEEWA Home / chatbot mission bridge.

Submits through the existing mission supervisor. Arbitrary chatbot text is not
authorization. A2/A3 objectives remain blocked unless standing registry auth applies.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
AUTO = SourceFileLoader("neewa_autonomy_home", str(SCRIPTS / "neewa_autonomy.py")).load_module()
MISSION = SourceFileLoader("neewa_mission_home", str(SCRIPTS / "neewa_mission.py")).load_module()
SEM = SourceFileLoader("neewa_action_semantics_home", str(SCRIPTS / "neewa_action_semantics.py")).load_module()

ALLOWED_ORIGINS = {"home", "chatbot", "conversation"}


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
        "artifacts": job.get("artifacts") or mission.get("evidence_locations") or [],
        "authorization_bypass": False,
        "updated_at": utc_now(),
    }


def submit(objective: str, *, origin: str = "home", workspace: str | None = None, project_id: str | None = None, root: Path | None = None) -> dict:
    origin = (origin or "home").strip().lower()
    if origin not in ALLOWED_ORIGINS:
        return {"status": "BLOCKED", "reason": "ORIGIN_NOT_ALLOWED", "authorization_bypass": False}
    text = (objective or "").strip()
    if not text:
        return {"status": "BLOCKED", "reason": "EMPTY_OBJECTIVE", "authorization_bypass": False}
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
        }
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
        return {"status": "RESUMED", "reason": "DUPLICATE_ACTIVE_MISSION", "mission": snap, "authorization_bypass": False}
    except MISSION.HostPathUnmounted as exc:
        return {"status": "BLOCKED", "reason": str(exc), "authorization_bypass": False}
    snap = snapshot_from_mission(mission)
    write_snapshot(mission)
    return {"status": "CREATED", "mission": snap, "authorization_bypass": False}


def status(mission_id: str | None = None, *, root: Path | None = None) -> dict:
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
        snap = snapshot_from_mission(mission)
        write_snapshot(mission)
        return snap
    current = snapshot_dir() / "current.json"
    if current.is_file():
        return json.loads(current.read_text(encoding="utf-8"))
    return {"status": "EMPTY"}


def main() -> int:
    parser = argparse.ArgumentParser(description="NEEWA Home mission bridge")
    parser.add_argument("command", choices=("submit", "status"))
    parser.add_argument("--objective")
    parser.add_argument("--origin", default="home")
    parser.add_argument("--workspace")
    parser.add_argument("--project-id")
    parser.add_argument("--mission-id")
    parser.add_argument("--root")
    args = parser.parse_args()
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
