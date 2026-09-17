"""REGRESSION FIXTURE ONLY — not the production SDLC path.

Hard-coded project-status JSON CLI used to lock the original demonstration.
Production work must use neewa_autonomy.py (objective-derived requirements,
council inspection, and Cursor via the Windows worker).
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

FIXTURE_ID = "demo-status"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fixture_build_requirements(objective: str) -> dict:
    reqs = [
        {
            "id": "REQ-001",
            "text": "Accept a JSON file describing project statuses.",
            "kind": "functional",
        },
        {
            "id": "REQ-002",
            "text": "Print a human-readable status report including name and health.",
            "kind": "functional",
        },
        {
            "id": "REQ-003",
            "text": "Reject malformed JSON with a non-zero exit code.",
            "kind": "functional",
        },
        {
            "id": "REQ-004",
            "text": "Automated tests cover happy path and malformed input.",
            "kind": "quality",
        },
        {
            "id": "REQ-005",
            "text": "Do not access employer trees or unrestricted filesystem paths.",
            "kind": "security",
        },
    ]
    return {
        "version": "REQ-v1",
        "fixture": FIXTURE_ID,
        "original_objective": objective,
        "clarifications": [],
        "implementation_decisions": [],
        "proposed_enhancements": [],
        "out_of_scope": ["public deployment", "live trading", "employer data"],
        "requirements": reqs,
        "created_at": utc_now(),
        "source_class": "FIXTURE",
    }


def fixture_initial_design(requirements: dict) -> dict:
    return {
        "version": "DES-v1",
        "fixture": FIXTURE_ID,
        "summary": "CLI that reads a JSON array of {name, status} and prints a table.",
        "assumptions": ["Local Python 3 is available.", "Workspace is the approved sandbox."],
        "components": ["status_app.py", "sample_status.json", "test_status_app.py"],
        "acceptance": [r["id"] for r in requirements["requirements"]],
        "created_at": utc_now(),
    }


def fixture_run_council(design: dict) -> dict:
    findings = [
        {
            "role": "solution_architect",
            "severity": "info",
            "finding": "Single-file CLI is appropriate for the sandbox scope.",
            "evidence": "components=%s" % design.get("components"),
        },
        {
            "role": "implementation_engineer",
            "severity": "info",
            "finding": "No third-party dependencies required.",
            "evidence": "summary has no vendor names",
        },
        {
            "role": "quality_engineer",
            "severity": "material",
            "finding": "DES-v1 does not specify behavior for malformed JSON; REQ-003 would fail.",
            "evidence": "summary=%s" % design.get("summary"),
        },
        {
            "role": "security_privacy",
            "severity": "info",
            "finding": "Keep reads on an explicit path argument; do not walk C:\\.",
            "evidence": "fixture scope",
        },
        {
            "role": "ux_product",
            "severity": "info",
            "finding": "Print a one-line error to stderr on invalid input.",
            "evidence": "REQ-003",
        },
        {
            "role": "cost_operations",
            "severity": "info",
            "finding": "Fixture uses local files; production must use Cursor worker.",
            "evidence": "fixture=%s" % FIXTURE_ID,
        },
    ]
    material = [f for f in findings if f["severity"] == "material"]
    revised = dict(design)
    revised["version"] = "DES-v2"
    revised["summary"] = (
        "CLI that reads a JSON array of {name, status}, prints a table, "
        "and exits non-zero on malformed JSON without walking other directories."
    )
    revised["corrections"] = [f["finding"] for f in material]
    return {
        "rounds": 1,
        "fixture": FIXTURE_ID,
        "findings": findings,
        "material_count": len(material),
        "approved_design": revised,
        "unresolved_risks": [],
        "created_at": utc_now(),
    }


STATUS_APP_SRC = '''\
"""Project status CLI. Reads one JSON file; does not walk the filesystem."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def load_projects(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("status file must be a JSON array")
    out = []
    for row in data:
        if not isinstance(row, dict) or "name" not in row or "status" not in row:
            raise ValueError("each item needs name and status")
        out.append({"name": str(row["name"]), "status": str(row["status"])})
    return out


def render(projects: list[dict]) -> str:
    lines = ["PROJECT STATUS", "=============="]
    for row in projects:
        lines.append(f"{row['name']}: {row['status']}")
    lines.append(f"count={len(projects)}")
    return "\\n".join(lines) + "\\n"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        sys.stderr.write("usage: status_app.py <file.json>\\n")
        return 2
    path = Path(args[0])
    try:
        text = render(load_projects(path))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        sys.stderr.write(f"invalid status file: {exc}\\n")
        return 1
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

STATUS_APP_BROKEN = STATUS_APP_SRC.replace(
    """    try:
        text = render(load_projects(path))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        sys.stderr.write(f"invalid status file: {exc}\\n")
        return 1
    sys.stdout.write(text)
    return 0""",
    """    try:
        text = render(load_projects(path))
    except Exception:
        sys.stdout.write("PROJECT STATUS\\n==============\\ncount=0\\n")
        return 0
    sys.stdout.write(text)
    return 0""",
)

STATUS_TEST_SRC = '''\
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parent / "status_app.py"


class StatusAppTests(unittest.TestCase):
    def test_happy_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sample = Path(tmp) / "ok.json"
            sample.write_text(
                json.dumps([{"name": "NEEWA", "status": "healthy"}]),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [sys.executable, str(APP), str(sample)],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("NEEWA: healthy", completed.stdout)
        self.assertIn("count=1", completed.stdout)

    def test_malformed_json_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sample = Path(tmp) / "bad.json"
            sample.write_text("{not json", encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(APP), str(sample)],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("invalid status file", completed.stderr)


if __name__ == "__main__":
    unittest.main()
'''


def implement_local(workdir: Path, broken: bool = False) -> list[Path]:
    workdir.mkdir(parents=True, exist_ok=True)
    src = STATUS_APP_BROKEN if broken else STATUS_APP_SRC
    files = {
        "status_app.py": src,
        "test_status_app.py": STATUS_TEST_SRC,
        "sample_status.json": json.dumps(
            [
                {"name": "NEEWA-OS", "status": "healthy"},
                {"name": "cursor-sandbox", "status": "active"},
            ],
            indent=2,
        )
        + "\n",
    }
    paths = []
    for name, body in files.items():
        path = workdir / name
        path.write_text(body, encoding="utf-8")
        paths.append(path)
    return paths


def run_unit_tests(workdir: Path) -> dict:
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "test_status_app.py", "-v"],
        cwd=str(workdir),
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "exit_code": completed.returncode,
        "passed": completed.returncode == 0,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-2000:],
    }


def fixture_traceability(requirements: dict, test_result: dict) -> dict:
    rows = []
    for req in requirements["requirements"]:
        covered = req["id"] in {"REQ-001", "REQ-002", "REQ-003", "REQ-004", "REQ-005"}
        tested = test_result.get("passed") and req["id"] != "REQ-005"
        if req["id"] == "REQ-005":
            tested = True
        rows.append(
            {
                "requirement": req["id"],
                "design": "DES-v2",
                "implementation": "status_app.py",
                "test": "test_status_app.py" if req["id"] != "REQ-005" else "policy",
                "result": "PASS" if covered and tested else "FAIL",
                "fixture": FIXTURE_ID,
            }
        )
    return {"all_pass": all(r["result"] == "PASS" for r in rows), "rows": rows, "fixture": FIXTURE_ID}
