"""Local broad-autonomy evidence. Not a production job runner."""
from __future__ import annotations

import json
import tempfile
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MOD = SourceFileLoader("neewa_autonomy_e2e", str(ROOT / "12_SCRIPTS" / "neewa_autonomy.py")).load_module()
PLAN = MOD.PLANNING
OUT = Path(__file__).resolve().parent / "controller-e2e.json"


def main() -> None:
    cases = {
        "mixed_docs_tests": "Review the documentation and add a unit test in tests/test_foo.py",
        "software_sandbox": "Create echo_util.py with a unit test in test_echo_util.py. Do not publish.",
        "research": "Write a briefing on NEEWA personal project access stages citing OWNER.md and PROJECT_ACCESS.md. Do not publish.",
        "file_op": "Create a file note NEEWA-Personal/notes/autonomy-policy-check.md",
        "a2_publish": "publish this article to the public blog",
        "a2_email": "send email to the client with the report",
        "a3_trade": "place a live trade for AAPL",
        "question": "what is the status of connected projects",
    }
    auth_cases = {
        "orats": dict(approval_level="A1", prompt="implement a helper", repo=r"C:\Development\Workspace\OratsUtil", write=True),
        "unlisted_personal": dict(approval_level="A1", prompt="implement a helper", repo=r"C:\Development\Workspace\BrandNewPersonalApp", write=True),
        "zume": dict(approval_level="A1", prompt="implement a helper", repo=r"C:\Development\Workspace\Zume", write=True),
        "sciencequest": dict(approval_level="A1", prompt="add a vitest", repo=r"C:\Development\Workspace\KidsProjects\ScienceQuest", write=True),
        "udemy": dict(approval_level="A1", prompt="add a note.md", repo=r"C:\Development\Workspace\Udemy-Yutube-repos", write=True),
        "workspace_root": dict(approval_level="A1", prompt="implement a helper", repo=r"C:\Development\Workspace", write=True),
        "sandbox": dict(approval_level="A1", prompt="implement a helper", repo=r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox", write=True),
        "a2": dict(approval_level="A1", prompt="deploy to production", repo=r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox", write=True),
        "a3": dict(approval_level="A1", prompt="place a live trade", repo=r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox", write=True),
    }
    resolve_cases = {
        "wani_root": ("PRJ-WANI", r"C:\Development\Workspace"),
        "unregistered": ("PRJ-NEW-PERSONAL", r"C:\Development\Workspace\BrandNewPersonalApp"),
        "bhava_nopath": ("PRJ-BHAVA", None),
        "kids": ("PRJ-KIDS", r"C:\Development\Workspace\KidsProjects\ScienceQuest"),
    }
    payload = {
        "classifications": {k: MOD.classify_intent(v) for k, v in cases.items()},
        "authorization": {k: MOD.authorize_execution(**kwargs) for k, kwargs in auth_cases.items()},
        "resolve": {k: PLAN.resolve_project(pid, ws) for k, (pid, ws) in resolve_cases.items()},
    }
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "jobs"

        def boom(**kwargs):
            raise AssertionError("cursor must not run")

        a2job = MOD.create_parent_job(
            "publish this article to the public blog",
            project_id="PRJ-NEEWA",
            workspace=r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox",
            root=root,
        )
        a2job = MOD.run_until_idle(a2job, root=root, orch_submit=boom)
        orats = MOD.create_parent_job(
            "add a helper in notes.md",
            project_id="PRJ-NEW",
            workspace=r"C:\Development\Workspace\OratsUtil",
            root=root,
        )
        orats = MOD.run_until_idle(orats, root=root, orch_submit=boom)
        payload["blocked_jobs"] = {
            "a2": {"state": a2job["state"], "reason": a2job.get("failure_reason")},
            "orats": {"state": orats["state"], "reason": orats.get("failure_reason")},
        }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
