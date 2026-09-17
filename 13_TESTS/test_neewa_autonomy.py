import json
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTO = ROOT / "12_SCRIPTS" / "neewa_autonomy.py"
ORCH = ROOT / "12_SCRIPTS" / "neewa_orchestrate.py"


class AutonomyTests(unittest.TestCase):
    def setUp(self):
        self.mod = SourceFileLoader("neewa_autonomy", str(AUTO)).load_module()

    def test_software_intent(self):
        row = self.mod.classify_intent(
            "NEEWA, build a project-status application. Research, council, tests, release candidate."
        )
        self.assertEqual(row["intent"], "software")
        self.assertEqual(row["workflow"], "sdlc")
        self.assertEqual(row["approval"], "A1")

    def test_question_does_not_start_sdlc(self):
        row = self.mod.classify_intent("what is the status of connected projects")
        self.assertEqual(row["intent"], "question")
        self.assertEqual(row["workflow"], "answer")

    def test_a2_publish_is_gated(self):
        row = self.mod.classify_intent("publish this article to the public blog")
        self.assertEqual(row["approval"], "A2")

    def test_a3_trade_is_gated(self):
        row = self.mod.classify_intent("place a live trade for AAPL")
        self.assertEqual(row["approval"], "A3")

    def test_local_sdlc_reaches_owner_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobs"
            work = Path(tmp) / "work"
            job = self.mod.create_parent_job(
                "build a project-status application with tests and a release candidate",
                project_id="PRJ-NEEWA",
                root=root,
            )
            job = self.mod.run_software_local(job, work)
            self.assertEqual(job["state"], "OWNER_REVIEW")
            self.assertEqual(job["requirements_version"], "REQ-v1")
            self.assertEqual(job["design_version"], "DES-v2")
            self.assertGreaterEqual(json.loads((work / "council.json").read_text())["material_count"], 1)
            self.assertEqual(job["validation"]["tests"], "PASS")
            self.assertEqual(job["validation"]["traceability"], "PASS")
            self.assertTrue((work / "RELEASE_CANDIDATE.md").is_file())
            self.assertGreater(job["validation"]["first_fail_exit"], 0)
            self.assertEqual(job["owner_decision"], "pending_review")
            self.assertNotEqual(job["state"], "DONE")

    def test_restart_resumes_from_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobs"
            work = Path(tmp) / "work"
            job = self.mod.create_parent_job(
                "build a project-status application",
                root=root,
            )
            job = self.mod.run_software_local(job, work, stop_before="DESIGN")
            self.assertEqual(job["state"], "REQUIREMENTS")
            job_id = job["job_id"]
            reloaded = self.mod.resume_job(job_id, root)
            self.assertIsNotNone(reloaded)
            finished = self.mod.run_software_local(reloaded, work)
            self.assertEqual(finished["state"], "OWNER_REVIEW")

    def test_idempotent_rerun_does_not_leave_owner_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobs"
            work = Path(tmp) / "work"
            job = self.mod.create_parent_job("build a project-status application", root=root)
            job = self.mod.run_software_local(job, work)
            again = self.mod.run_software_local(job, work)
            self.assertEqual(again["state"], "OWNER_REVIEW")

    def test_budget_exhaustion_blocks_without_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobs"
            work = Path(tmp) / "work"
            job = self.mod.create_parent_job(
                "build a project-status application",
                root=root,
                budget_ceiling=0,
            )
            job = self.mod.run_software_local(job, work)
            self.assertEqual(job["state"], "BLOCKED")
            self.assertEqual(job["failure_reason"], "BUDGET_EXHAUSTED")
            self.assertFalse((work / "status_app.py").exists())

    def test_a2_parent_job_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobs"
            job = self.mod.create_parent_job("publish this to production", root=root)
            self.assertEqual(job["approval_level"], "A2")
            self.mod.transition(job, "CLASSIFIED", job["intent"])
            self.mod.transition(job, "BLOCKED", "owner gate required")
            self.assertEqual(job["state"], "BLOCKED")

    def test_failover_waits_when_no_coding_worker(self):
        empty = {
            "workers": [
                {"id": "codex", "class": "coding-worker", "status": "missing", "routable": False}
            ]
        }
        choice = self.mod.select_coding_worker(empty)
        self.assertFalse(choice["available"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobs"
            work = Path(tmp) / "work"
            job = self.mod.create_parent_job("build a project-status application", root=root)
            parked = self.mod.run_software_local(job, work, worker_registry=empty)
            self.assertEqual(parked["state"], "WAITING")
            resumed = self.mod.run_software_local(parked, work)
            self.assertEqual(resumed["state"], "OWNER_REVIEW")

    def test_done_gate_rejects_missing_tests(self):
        job = {
            "state": "VALIDATING",
            "approval_level": "A1",
            "requirements_version": "REQ-v1",
            "design_version": "DES-v2",
            "artifacts": ["x"],
            "validation": {"council": "PASS", "tests": "NOT RUN", "traceability": "PASS"},
        }
        failures = self.mod.evaluate_autonomy_done(job)
        self.assertTrue(failures)
        self.assertTrue(any("unit tests" in item for item in failures))

    def test_done_gate_rejects_a3_without_owner(self):
        job = {
            "state": "VALIDATING",
            "approval_level": "A3",
            "requirements_version": "REQ-v1",
            "design_version": "DES-v2",
            "artifacts": ["x"],
            "owner_decision": None,
            "validation": {"council": "PASS", "tests": "PASS", "traceability": "PASS"},
        }
        self.assertTrue(self.mod.evaluate_autonomy_done(job))

    def test_cancel_is_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = self.mod.create_parent_job("build a project-status application", root=Path(tmp))
            self.mod.cancel_job(job, "owner cancelled")
            self.assertEqual(job["state"], "CANCELLED")

    def test_council_finds_material_defect(self):
        design = self.mod.initial_design(self.mod.build_requirements("build status app"))
        council = self.mod.run_council(design)
        self.assertGreaterEqual(council["material_count"], 1)
        self.assertEqual(council["approved_design"]["version"], "DES-v2")
        self.assertTrue(any(f["severity"] == "material" for f in council["findings"]))


class OrchestrateUsageTests(unittest.TestCase):
    def setUp(self):
        self.mod = SourceFileLoader("neewa_orchestrate_usage", str(ORCH)).load_module()

    def test_harvest_records_usage_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rec = self.mod.submit(
                job_id="JOB-TEST-USAGE",
                capability="project_inventory",
                objective="inventory",
                inbox_root=root,
            )
            inbox_file = root / "inbox" / "JOB-TEST-USAGE.json"
            done = root / "done"
            done.mkdir(exist_ok=True)
            (done / "JOB-TEST-USAGE.json").write_text(
                json.dumps(
                    {
                        "job_id": "JOB-TEST-USAGE",
                        "status": "COMPLETED",
                        "artifact": "report.json",
                        "usage": {"inputTokens": 11, "outputTokens": 7},
                    }
                ),
                encoding="utf-8",
            )
            inbox_file.unlink()
            harvested = self.mod.harvest("JOB-TEST-USAGE", root)
            self.assertEqual(harvested["usage"]["inputTokens"], 11)
            self.assertEqual(harvested["usage_basis"], "worker-reported")


if __name__ == "__main__":
    unittest.main()
