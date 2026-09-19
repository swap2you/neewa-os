#!/usr/bin/env python3
"""Durable, integrity-checked handoff checkpoints for NEEWA sessions."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CHECKPOINT_VERSION = 1
FORBIDDEN_FIELD_PATTERN = re.compile(r"(?:password|passwd|secret|token|credential|api[_-]?key|private[_-]?key)", re.I)
REQUIRED_FIELDS = (
    "objective", "completed_work", "decisions", "mission_job_ids",
    "branches_commits_prs", "test_validation_evidence", "runtime_versions",
    "active_operations", "blockers", "next_operation", "acceptance_criteria",
    "authoritative_receipts", "previous_session_id", "new_session_id",
    "checkpoint_version", "created_at",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _reject_secrets(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if FORBIDDEN_FIELD_PATTERN.search(str(key)):
                raise ValueError(f"credential-like field is not allowed: {path}.{key}")
            _reject_secrets(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secrets(child, f"{path}[{index}]")
    elif isinstance(value, str) and FORBIDDEN_FIELD_PATTERN.search(value):
        raise ValueError(f"credential-like text is not allowed: {path}")


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _integrity(payload: dict[str, Any]) -> str:
    unsigned = dict(payload)
    unsigned.pop("integrity_sha256", None)
    return hashlib.sha256(_canonical(unsigned)).hexdigest()


def create_checkpoint(
    directory: str | os.PathLike[str],
    *,
    previous_session_id: str,
    new_session_id: str | None = None,
    objective: str,
    completed_work: list[Any],
    decisions: list[Any],
    mission_job_ids: list[Any],
    branches_commits_prs: list[Any],
    test_validation_evidence: list[Any],
    runtime_versions: dict[str, Any],
    active_operations: list[Any],
    blockers: list[Any],
    next_operation: str,
    acceptance_criteria: list[Any],
    authoritative_receipts: list[Any],
    filename: str | None = None,
) -> Path:
    if not previous_session_id or not objective or not next_operation:
        raise ValueError("previous_session_id, objective, and next_operation are required")
    checkpoint = {
        "checkpoint_version": CHECKPOINT_VERSION,
        "previous_session_id": previous_session_id,
        "new_session_id": new_session_id or f"session-{uuid.uuid4().hex[:12]}",
        "created_at": utc_now(),
        "objective": objective,
        "completed_work": completed_work,
        "decisions": decisions,
        "mission_job_ids": mission_job_ids,
        "branches_commits_prs": branches_commits_prs,
        "test_validation_evidence": test_validation_evidence,
        "runtime_versions": runtime_versions,
        "active_operations": active_operations,
        "blockers": blockers,
        "next_operation": next_operation,
        "acceptance_criteria": acceptance_criteria,
        "authoritative_receipts": authoritative_receipts,
        "successor_status": "PREPARED",
    }
    _reject_secrets(checkpoint)
    checkpoint["integrity_sha256"] = _integrity(checkpoint)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (filename or f"checkpoint-{checkpoint['created_at'].replace(':', '').replace('-', '')}.json")
    path.write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_checkpoint(path: str | os.PathLike[str]) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"missing checkpoint fields: {', '.join(missing)}")
    if payload.get("checkpoint_version") != CHECKPOINT_VERSION:
        raise ValueError("unsupported checkpoint version")
    _reject_secrets({k: v for k, v in payload.items() if k != "integrity_sha256"})
    expected = _integrity(payload)
    if payload.get("integrity_sha256") != expected:
        raise ValueError("checkpoint integrity mismatch")
    return payload


def latest_valid_checkpoint(directory: str | os.PathLike[str]) -> tuple[Path, dict[str, Any]]:
    candidates = sorted(Path(directory).glob("checkpoint-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    invalid: list[str] = []
    for path in candidates:
        try:
            return path, load_checkpoint(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            invalid.append(f"{path.name}: {exc}")
    raise FileNotFoundError("no valid checkpoint" + (f" ({'; '.join(invalid)})" if invalid else ""))


def reconcile_live_jobs(records: list[dict[str, Any]]) -> dict[str, Any]:
    active = [r for r in records if str(r.get("state", r.get("status", ""))).upper() in {"QUEUED", "DISPATCHED", "RUNNING", "VALIDATING"}]
    ids = [str(r.get("id", r.get("job_id", r.get("mission_id", "")))) for r in active]
    duplicates = sorted({item for item in ids if item and ids.count(item) > 1})
    return {"active_ids": [item for item in ids if item], "duplicate_ids": duplicates, "safe_to_start": not duplicates}


def confirm_successor(path: str | os.PathLike[str], successor_session_id: str) -> dict[str, Any]:
    payload = load_checkpoint(path)
    if payload["new_session_id"] != successor_session_id:
        raise ValueError("successor session ID does not match checkpoint")
    payload["successor_status"] = "LOADED"
    payload["loaded_at"] = utc_now()
    payload.pop("integrity_sha256", None)
    payload["integrity_sha256"] = _integrity(payload)
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def close_previous_session(path: str | os.PathLike[str], successor_session_id: str) -> dict[str, Any]:
    payload = load_checkpoint(path)
    if payload.get("successor_status") != "LOADED" or payload.get("new_session_id") != successor_session_id:
        raise ValueError("previous session cannot close before successor confirms checkpoint loading")
    payload["previous_session_status"] = "CLOSED"
    payload.pop("integrity_sha256", None)
    payload["integrity_sha256"] = _integrity(payload)
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    latest = sub.add_parser("latest")
    latest.add_argument("directory")
    args = parser.parse_args()
    if args.command == "latest":
        path, payload = latest_valid_checkpoint(args.directory)
        print(json.dumps({"path": str(path), "new_session_id": payload["new_session_id"], "integrity_sha256": payload["integrity_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
