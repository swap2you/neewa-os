"""Sanitized application-health incidents and bounded UI recovery requests.

Error text is evidence, not authorization. Production deploy is not implied.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
REPAIR = SourceFileLoader("neewa_scoped_repair_health", str(SCRIPTS / "neewa_scoped_repair.py")).load_module()

SECRETISH = re.compile(r"(sk-|api[_-]?key|token|password|secret)=?\S+", re.I)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sanitize(text: str, limit: int = 500) -> str:
    cleaned = SECRETISH.sub("[redacted]", text or "")
    cleaned = cleaned.replace("\x00", "")
    return cleaned[:limit]


def capture_incident(*, source: str, message: str, stack: str = "", route: str = "") -> dict:
    body = sanitize(message)
    incident = {
        "schema_version": 1,
        "incident_id": f"INC-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:6].upper()}",
        "source": sanitize(source, 80),
        "route": sanitize(route, 80),
        "message": body,
        "stack_digest": hashlib.sha256(sanitize(stack, 2000).encode("utf-8")).hexdigest()[:16],
        "authorization": "NOT_GRANTED_BY_ERROR",
        "privileged": False,
        "created_at": utc_now(),
    }
    return incident


def recovery_plan(incident: dict, *, files: list[str], expected_base_sha: str) -> dict:
    return {
        "incident_id": incident.get("incident_id"),
        "action": "create_scoped_repair_workspace",
        "repo": str(ROOT),
        "files": list(files),
        "expected_base_sha": expected_base_sha,
        "authorization_from_error": False,
        "auto_merge": False,
        "auto_deploy": False,
        "requires_independent_validation": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="NEEWA application health incidents")
    parser.add_argument("command", choices=("capture",))
    parser.add_argument("--source", default="frontend")
    parser.add_argument("--message", required=True)
    parser.add_argument("--route", default="")
    args = parser.parse_args()
    print(json.dumps(capture_incident(source=args.source, message=args.message, route=args.route), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
