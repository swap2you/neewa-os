"""Isolated mocked end-to-end for the failed neewa_date_tool_acceptance intake.

Does not create a live NEEWA job and does not invoke Cursor Agent CLI.
Does not touch historical jobs or personal project trees.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTO = ROOT / "12_SCRIPTS" / "neewa_autonomy.py"
SANDBOX_ROOT = r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox"
DATE_TOOL_PATH = r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox\neewa_date_tool_acceptance"
DATE_TOOL_OBJECTIVE = (
    "Build exactly one new isolated Python standard-library CLI project named "
    "neewa_date_tool_acceptance under the approved workspace root "
    r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox. The canonical project directory is "
    r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox\neewa_date_tool_acceptance. "
    "Before dispatch, use the Windows worker to verify that this canonical directory "
    "does not already contain implementation artifacts; if it exists with artifacts, "
    "stop with a precise validation failure and do not reuse it. Do not copy or reuse "
    "local_date_summary or any historical acceptance project. Implement a CLI that "
    "accepts YYYY-MM-DD and outputs weekday, whether the year is a leap year, and day "
    "number within the year. Valid dates exit 0. Invalid dates exit nonzero with a "
    "clear error. Include automated tests for an ordinary valid date, leap-year date, "
    "non-leap-year date, invalid calendar date, and day-of-year calculation, plus "
    "concise usage documentation. Use only Python standard library. Execute through "
    "Cursor Agent CLI on Windows. After implementation verify the canonical path and "
    "actual files, run the product test command, independently rerun the same product "
    "tests in the same canonical directory, validate every requirement individually, "
    "validate the scoped diff, produce controller-owned traceability, finalize budget "
    "accounting, and reconcile child to parent. Preserve all historical jobs and "
    "unrelated projects. Reach OWNER_REVIEW only if Cursor executed, artifacts exist "
    "at the canonical path, both test runs pass, traceability passes, child and parent "
    "reconcile, and reserved budget is zero."
)

CANONICAL_RELATIVE = (
    "neewa_date_tool_acceptance.py",
    "test_neewa_date_tool_acceptance.py",
    "test-results.json",
    "README.md",
    "RELEASE_CANDIDATE.md",
)
HISTORICAL_MARKERS = (
    "local_date_summary",
    "isolated_python_standard_library",
    "c_users_swap2_neewa_personal_cursor_sandbox",
)


def _test_stdout() -> str:
    payload = {
        "passed": True,
        "exit_code": 0,
        "stdout": "Ran 5 tests in 0.02s\nOK",
        "stderr": "",
    }
    return (
        "Ran 5 tests in 0.02s\n\nOK\n"
        f"TEST_JSON:{json.dumps(payload, separators=(',', ':'))}"
    )


def _canonical_artifacts() -> list[str]:
    return [rf"{DATE_TOOL_PATH}\{name}" for name in CANONICAL_RELATIVE]


class DateToolAcceptanceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.mod = SourceFileLoader("neewa_autonomy_date_tool_e2e", str(AUTO)).load_module()

    def _create(self, root: Path, **kwargs):
        return self.mod.create_parent_job(
            DATE_TOOL_OBJECTIVE,
            workspace=SANDBOX_ROOT,
            project_id="PRJ-NEEWA",
            root=root,
            origin="conversation",
            **kwargs,
        )

    def _completed_child(self, job_id: str) -> dict:
        return {
            "job_id": job_id,
            "state": "COMPLETED",
            "selected_worker": "cursor-agent-cli",
            "cli": r"C:\Users\swap2\AppData\Local\cursor-agent\agent.cmd",
            "exit_code": 0,
            "duration_sec": 90,
            "artifact_paths": _canonical_artifacts(),
            "validation": {"stdout_tail": _test_stdout(), "result": "PASS"},
            "usage": {"inputTokens": 1200, "outputTokens": 180},
        }

    def _assert_identity(self, job: dict) -> None:
        identity = job.get("project_identity") or {}
        self.assertEqual(identity.get("project_name"), "neewa_date_tool_acceptance")
        self.assertEqual(identity.get("workspace_root"), SANDBOX_ROOT)
        self.assertEqual(identity.get("project_path"), DATE_TOOL_PATH)
        self.assertTrue(identity.get("allowed"), identity)

    def _assert_not_historical(self, *blobs) -> None:
        text = " ".join(str(item) for item in blobs).lower()
        for marker in HISTORICAL_MARKERS:
            self.assertNotIn(marker, text)

    def test_conversation_intake_through_owner_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobs"
            submits: list[dict] = []
            harvests: list[str] = []

            def submit(**kwargs):
                submits.append(kwargs)
                return {
                    "job_id": kwargs["job_id"],
                    "state": "DISPATCHED",
                    "selected_worker": "cursor-agent-cli",
                }

            def harvest(job_id, inbox_root=None):
                harvests.append(job_id)
                return self._completed_child(job_id)

            job = self._create(root)
            self._assert_identity(job)
            classified = self.mod.classify_intent(DATE_TOOL_OBJECTIVE)
            self.assertEqual(classified["intent"], "software")
            self.assertEqual(classified["workflow"], "sdlc")
            self.assertEqual(classified["approval"], "A1")
            parent_gate = self.mod.authorize_execution(
                approval_level="A1",
                owner_decision=None,
                prompt=DATE_TOOL_OBJECTIVE,
                repo=DATE_TOOL_PATH,
                write=True,
            )
            self.assertTrue(parent_gate["allowed"], parent_gate)
            self.assertEqual(parent_gate["needed"], "A1")

            finished = self.mod.run_until_idle(
                job, root=root, orch_submit=submit, orch_harvest=harvest
            )
            states = [row["state"] for row in finished.get("history") or []]
            self.assertIn("INTAKE", states)
            self.assertIn("CLASSIFIED", states)
            self.assertIn("REQUIREMENTS", states)
            self.assertIn("DESIGN", states)
            self.assertIn("EXECUTING", states)
            self.assertIn("TESTING", states)
            self.assertIn("VALIDATING", states)
            self.assertEqual(finished["state"], "OWNER_REVIEW")
            self._assert_identity(finished)
            self.assertEqual(finished["workspace"], DATE_TOOL_PATH)

            self.assertEqual(len(submits), 2)
            self.assertTrue(all(item.get("approval") == "A1" for item in submits))
            self.assertTrue(all(item.get("repo") == DATE_TOOL_PATH for item in submits))
            child_prompt = submits[0]["prompt"]
            child_gate = self.mod.authorize_execution(
                approval_level="A1",
                owner_decision=None,
                prompt=child_prompt,
                repo=DATE_TOOL_PATH,
                write=True,
            )
            self.assertTrue(child_gate["allowed"], child_gate)
            self.assertEqual(child_gate["needed"], "A1")
            self.assertEqual(child_gate["reason"], "ALLOW")
            self.assertEqual((finished.get("authorization") or {}).get("child", {}).get("needed"), "A1")

            expected = finished.get("expected_paths") or []
            self.assertTrue(expected)
            for rel in expected:
                self.assertFalse(Path(rel).is_absolute())
                self.assertNotIn("..", Path(rel).parts)
                resolved = str(Path(DATE_TOOL_PATH) / rel.replace("/", "\\"))
                self.assertTrue(resolved.lower().startswith(DATE_TOOL_PATH.lower()))
            self.assertTrue(any(rel.endswith("neewa_date_tool_acceptance.py") for rel in expected))
            self.assertTrue(any("test_neewa_date_tool_acceptance.py" in rel for rel in expected))
            artifacts = [str(item) for item in (finished.get("artifacts") or [])]
            self.assertTrue(any(DATE_TOOL_PATH in item for item in artifacts))
            self._assert_not_historical(expected, artifacts, finished.get("project_identity"))
            self.assertIn("neewa_date_tool_acceptance", child_prompt)
            self.assertNotIn("isolated_python_standard_library", child_prompt)

            validation = finished.get("validation") or {}
            self.assertEqual(validation.get("tests"), "PASS")
            self.assertEqual(validation.get("independent_rerun"), "PASS")
            self.assertEqual(validation.get("traceability"), "PASS")
            self.assertEqual(validation.get("council"), "PASS")
            self.assertTrue((validation.get("test_evidence") or {}).get("passed"))
            self.assertTrue((validation.get("independent_test_evidence") or {}).get("passed"))

            work = self.mod.job_workdir(finished, root)
            trace = json.loads((work / "traceability.json").read_text(encoding="utf-8"))
            self.assertTrue(trace["all_pass"], trace)
            self.assertTrue(trace["rows"])
            self.assertTrue(all(row["result"] == "PASS" for row in trace["rows"]))

            budget = finished.get("budget") or {}
            self.assertEqual(budget.get("reserved_usd"), 0.0)
            self.assertEqual(len(budget.get("invocations") or []), 2)
            self.assertGreater(float(budget.get("consumed_usd") or 0), 0.0)
            self.assertEqual((finished.get("budget_finalized") or {}).get("reserved_usd"), 0.0)
            finalized_at = (finished.get("budget_finalized") or {}).get("at")

            again = self.mod.reconcile_parent_job(finished, orch_harvest=harvest)
            third = self.mod.run_until_idle(
                again, root=root, orch_submit=submit, orch_harvest=harvest
            )
            self.assertEqual(third["state"], "OWNER_REVIEW")
            self.assertEqual(len(submits), 2)
            self.assertEqual(len(third.get("budget", {}).get("invocations") or []), 2)
            self.assertEqual(third["budget"]["reserved_usd"], 0.0)
            self.assertEqual((third.get("budget_finalized") or {}).get("at"), finalized_at)
            self.assertEqual(len(third.get("child_jobs") or []), 2)

    def test_failed_child_closes_parent_without_stale_executing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobs"
            submits: list[str] = []

            def submit(**kwargs):
                submits.append(kwargs["job_id"])
                return {"job_id": kwargs["job_id"], "state": "DISPATCHED"}

            def harvest(job_id, inbox_root=None):
                return {
                    "job_id": job_id,
                    "state": "FAILED",
                    "failure_class": "VALIDATION",
                    "failure_reason": "validation failed; missing expected files: neewa_date_tool_acceptance.py",
                    "cli": r"C:\Users\swap2\AppData\Local\cursor-agent\agent.cmd",
                    "exit_code": 0,
                    "artifact_paths": _canonical_artifacts(),
                }

            finished = self.mod.run_until_idle(
                self._create(root), root=root, orch_submit=submit, orch_harvest=harvest
            )
            self.assertEqual(finished["state"], "FAILED")
            self.assertNotEqual(finished["state"], "EXECUTING")
            self.assertEqual(len(submits), 1)
            self.assertEqual(finished["budget"]["reserved_usd"], 0.0)
            again = self.mod.reconcile_parent_job(finished, orch_harvest=harvest)
            third = self.mod.run_until_idle(
                again, root=root, orch_submit=submit, orch_harvest=harvest
            )
            self.assertEqual(third["state"], "FAILED")
            self.assertEqual(len(submits), 1)

    def test_blocked_child_closes_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobs"
            submits: list[str] = []

            def submit(**kwargs):
                submits.append(kwargs["job_id"])
                return {"job_id": kwargs["job_id"], "state": "DISPATCHED"}

            def harvest(job_id, inbox_root=None):
                return {
                    "job_id": job_id,
                    "state": "BLOCKED",
                    "failure_class": "POLICY",
                    "failure_reason": "owner gate",
                }

            finished = self.mod.run_until_idle(
                self._create(root), root=root, orch_submit=submit, orch_harvest=harvest
            )
            self.assertEqual(finished["state"], "BLOCKED")
            self.assertNotEqual(finished["state"], "EXECUTING")
            self.assertEqual(len(submits), 1)
            self.assertEqual(finished["budget"]["reserved_usd"], 0.0)
            again = self.mod.run_until_idle(
                finished, root=root, orch_submit=submit, orch_harvest=harvest
            )
            self.assertEqual(again["state"], "BLOCKED")
            self.assertEqual(len(submits), 1)
