import json
import os
import shutil
import subprocess
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "16_WINDOWS_CLIENT" / "worker"
SEM = SourceFileLoader("neewa_action_semantics_delivery", str(ROOT / "12_SCRIPTS" / "neewa_action_semantics.py")).load_module()
MISSION = SourceFileLoader("neewa_mission_delivery", str(ROOT / "12_SCRIPTS" / "neewa_mission.py")).load_module()
AUTO = SourceFileLoader("neewa_autonomy_delivery", str(ROOT / "12_SCRIPTS" / "neewa_autonomy.py")).load_module()
AUTH = SourceFileLoader("neewa_authorization_delivery", str(ROOT / "12_SCRIPTS" / "neewa_authorization.py")).load_module()
ROUTE = SourceFileLoader("neewa_model_route_delivery", str(ROOT / "12_SCRIPTS" / "neewa_model_route.py")).load_module()
CHAKRA = r"C:\Users\swap2\NEEWA-Personal\projects\ChakraOps"


class DeliverySemanticsTests(unittest.TestCase):
    def test_deferred_restart_is_not_an_immediate_release(self):
        text = (
            "Commit and sync only verified changes through the normal project workflow; "
            "deploy/restart only after required checks."
        )
        parsed = SEM.analyze_objective(text)
        self.assertNotIn("deploy", parsed["requested_families"])
        self.assertNotEqual(parsed["needed"], "A2")

    def test_explicit_production_rollout_stays_gated(self):
        parsed = SEM.analyze_objective("deploy this release to production")
        self.assertEqual(parsed["needed"], "A2")
        self.assertIn("deploy", parsed["requested_families"])


class InfrastructureRecoveryTests(unittest.TestCase):
    def test_temp_failure_does_not_consume_a_repair_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobs"
            mission = MISSION.create_mission(
                "repair the worker temp directory and rerun the product test",
                workspace=CHAKRA,
                project_id="PRJ-CHAKRAOPS",
                root=root,
                kind="sdlc",
                auto=AUTO,
            )
            job = AUTO.create_parent_job(
                mission["owner_objective"],
                workspace=CHAKRA,
                root=root,
                origin="mission-supervisor",
                mission_id=mission["mission_id"],
            )
            job["state"] = "FAILED"
            job["failure_class"] = "NO_USABLE_TEMP"
            job["failure_reason"] = "No usable temporary directory"
            AUTO.save_job(job)
            mission["active_job_id"] = job["job_id"]
            mission["job_ids"] = [job["job_id"]]
            mission["state"] = "RECOVERING"
            MISSION.save_mission(mission, root)
            updated = MISSION.step_mission(mission, root=root, auto=AUTO, worker_available=True)
            self.assertEqual(updated["state"], "PLANNING")
            self.assertEqual(updated["repair_cycles"], 0)
            self.assertEqual(updated["infrastructure_retries"], 1)

    def test_linked_successor_requires_a_terminal_parent_and_one_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobs"
            parent = MISSION.create_mission(
                "parent stays terminal",
                workspace=CHAKRA,
                project_id="PRJ-CHAKRAOPS",
                root=root,
                kind="diagnostic",
                auto=AUTO,
            )
            parent["state"] = "FAILED"
            parent["failure_reason"] = "MAX_REPAIR_CYCLES"
            parent["terminal_result"] = "FAILED"
            MISSION.save_mission(parent, root)
            child = MISSION.create_mission(
                "reconcile the existing dirty ORATS work and run the independent test",
                workspace=CHAKRA,
                project_id="PRJ-CHAKRAOPS",
                root=root,
                kind="sdlc",
                parent_mission_id=parent["mission_id"],
                successor_justification="temp repair changed the validator path",
                auto=AUTO,
            )
            reloaded = MISSION.load_mission(parent["mission_id"], root)
            self.assertEqual(reloaded["state"], "FAILED")
            self.assertEqual(reloaded["failure_reason"], "MAX_REPAIR_CYCLES")
            self.assertEqual(reloaded["successor_mission_id"], child["mission_id"])
            with self.assertRaises(ValueError):
                MISSION.create_mission(
                    "a second successor",
                    workspace=CHAKRA,
                    project_id="PRJ-CHAKRAOPS",
                    root=root,
                    parent_mission_id=parent["mission_id"],
                    successor_justification="must not storm",
                    auto=AUTO,
                )


class ReviewRouteTests(unittest.TestCase):
    def test_committed_probe_selects_the_sol_model_that_answered(self):
        routes = ROUTE.load_routes()
        self.assertTrue(routes["probed"]["gpt-5.6-sol"]["available"])
        self.assertFalse(routes["probed"]["gpt-6-sol"]["available"])
        self.assertTrue(routes["probed"]["gpt-6-astra"]["available"])
        self.assertTrue(routes["probed"]["gpt-5.6-luna"]["available"])
        selected = ROUTE.select_task("software_review", routes)
        self.assertEqual(selected["model"], "gpt-5.6-sol")
        self.assertEqual(selected["effort"], "high")
        self.assertEqual(selected["authentication"], "ChatGPT sign-in")
        self.assertFalse(selected["substituted"])
        self.assertFalse(selected["paid_api"])

    def test_unavailable_sol_uses_astra_without_paid_api(self):
        routes = ROUTE.load_routes()
        routes["probed"] = {
            "gpt-6-sol": {"available": False, "reason": "model rejected for this ChatGPT account"},
            "gpt-6-astra": {"available": True, "authentication": "ChatGPT sign-in"},
        }
        selected = ROUTE.select_task("software_review", routes)
        self.assertEqual(selected["model"], "gpt-6-astra")
        self.assertEqual(selected["effort"], "high")
        self.assertTrue(selected["substituted"])
        self.assertFalse(selected["api_key_fallback"])
        self.assertFalse(selected["paid_api"])
        self.assertEqual(ROUTE.select_task("strategy", routes)["model"], "gpt-6-astra")

    def test_chakraops_broker_actions_stay_denied(self):
        decision = AUTH.decide(operation="submit_order", repo=CHAKRA)
        self.assertEqual(decision["decision"], AUTH.DENIED)
        self.assertEqual(decision["reason"], "OPERATION_ALWAYS_DENIED")
        allowed = AUTH.decide(operation="independent_test", repo=CHAKRA)
        self.assertEqual(allowed["decision"], AUTH.AUTHORIZED)
        self.assertEqual(allowed["repository_id"], "chakraops")


class WorkerTempTests(unittest.TestCase):
    def test_scripts_keep_review_read_only_and_tests_writable(self):
        review = (WORKER / "Invoke-NeewaCodexReview.ps1").read_text(encoding="utf-8")
        tests = (WORKER / "Invoke-NeewaIndependentTest.ps1").read_text(encoding="utf-8")
        probe = (WORKER / "Invoke-NeewaTempProbe.ps1").read_text(encoding="utf-8")
        self.assertIn("-s read-only", review)
        self.assertIn("OPENAI_API_KEY", review)
        self.assertIn("ZERO_COLLECTED", tests)
        self.assertIn("NO_USABLE_TEMP", tests)
        self.assertIn("PYTEST_CACHE_DIR", probe)
        self.assertNotIn("Invoke-Expression", tests)

    def test_outcome_and_scratch_persistence(self):
        if os.name != "nt":
            self.skipTest("scratch probe runs on the Windows worker")
        shell = shutil.which("powershell") or shutil.which("pwsh")
        if shell is None:
            self.skipTest("Windows PowerShell is required for the scratch probe")
        script = WORKER / "Invoke-NeewaIndependentTest.ps1"
        probe = WORKER / "Invoke-NeewaTempProbe.ps1"
        command = (
            f". '{probe}'; . '{script}'; "
            "$bad = Get-NeewaPytestOutcome -Stdout '' -Stderr 'No usable temporary directory' -ExitCode 4; "
            "if ($bad.failure_class -ne 'NO_USABLE_TEMP' -or $bad.passed) { exit 2 }; "
            "$zero = Get-NeewaPytestOutcome -Stdout 'collected 0 items' -Stderr '' -ExitCode 5; "
            "if ($zero.failure_class -ne 'ZERO_COLLECTED' -or $zero.collected -ne 0 -or $zero.passed) { exit 3 }; "
            "$ok = Get-NeewaPytestOutcome -Stdout \"12 passed in 0.2s\" -Stderr '' -ExitCode 0; "
            "if (-not $ok.passed -or $ok.collected -ne 12) { exit 4 }; "
            "$first = Invoke-NeewaTempProbeReport; "
            "if (-not $first.scratch_persisted -or $first.failure_class) { exit 5 }; "
            "$second = Invoke-NeewaTempProbeReport; "
            "if ($second.scratch -ne $first.scratch) { exit 6 }"
        )
        completed = subprocess.run(
            [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_allowlist_exposes_typed_actions_only(self):
        data = json.loads((WORKER / "allowlist.json").read_text(encoding="utf-8"))
        for name in ("temp_probe", "independent_test", "local_health", "local_app_restart", "ui_verify", "repo_preflight", "codex_review"):
            self.assertIn(name, data["actions"])
        self.assertNotIn("shell", data["actions"])
        self.assertEqual(data["capability_version"], "2026-10-08-chakraops-1")
