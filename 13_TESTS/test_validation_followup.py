"""Behavioral checks for the 2026-10-08 validation follow-up."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from importlib.machinery import SourceFileLoader

ROOT = Path(__file__).resolve().parents[1]
AUTO = SourceFileLoader("neewa_autonomy", str(ROOT / "12_SCRIPTS" / "neewa_autonomy.py")).load_module()
MISSION = SourceFileLoader("neewa_mission", str(ROOT / "12_SCRIPTS" / "neewa_mission.py")).load_module()
ORCH = SourceFileLoader("neewa_orchestrate", str(ROOT / "12_SCRIPTS" / "neewa_orchestrate.py")).load_module()
WORKER = ROOT / "16_WINDOWS_CLIENT" / "worker"


class IndependentContractTests(unittest.TestCase):
    def test_generated_unittest_job_has_structured_args(self):
        adapter = AUTO.resolve_test_adapter(
            r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox\neewa-lifecycle-canary",
            "python -m unittest",
        )
        self.assertEqual(adapter["argv"], ["-m", "unittest"])
        self.assertEqual(adapter["cwd"], ".")
        self.assertEqual(adapter["id"], "lifecycle-canary-unittest")
        job = {
            "job_id": "JOB-IT",
            "parent_objective": "fixture",
            "workspace": r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox\neewa-lifecycle-canary",
            "project_identity": {},
            "child_jobs": [],
        }
        seen = {}

        def submit(**kwargs):
            seen.update(kwargs)
            return {"job_id": kwargs["job_id"], "state": "DISPATCHED"}

        AUTO._submit_independent_test(job, "python -m unittest", inbox_root=None, orch_submit=submit)
        self.assertEqual(seen["test_args"], ["-m", "unittest"])
        self.assertEqual(seen["test_cwd"], ".")
        self.assertTrue(seen["test_python"])

    def test_absent_stdout_uses_independent_artifact(self):
        evidence = AUTO.parse_test_evidence("", {
            "independent_test": {
                "passed": True,
                "collected": 12,
                "exit_code": 0,
                "stdout_tail": "12 passed",
                "candidate_head": "abc",
            }
        })
        self.assertTrue(evidence["passed"])
        self.assertEqual(evidence["source"], "independent_test")
        self.assertEqual(evidence["collected"], 12)
        zero = AUTO.parse_test_evidence("", {"independent_test": {"passed": True, "collected": 0, "exit_code": 0}})
        self.assertFalse(zero["passed"])

    def test_sidecar_receipt_reaches_harvest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "done").mkdir()
            job_id = "JOB-IT1"
            (root / "done" / f"{job_id}.json").write_text(json.dumps({
                "job_id": job_id,
                "status": "COMPLETED",
                "artifact": f"{job_id}-independent-test.json",
            }), encoding="utf-8")
            (root / "done" / f"{job_id}-independent-test.json").write_text(json.dumps({
                "passed": True,
                "collected": 12,
                "exit_code": 0,
                "stdout_tail": "12 passed",
            }), encoding="utf-8")
            _folder, payload = ORCH.inspect_folders(job_id, root)
            self.assertEqual(payload["independent_test"]["collected"], 12)
            self.assertTrue(payload["test_results"]["passed"])

    def test_object_review_fails_done_gate_and_mission_success(self):
        job = {
            "state": "VALIDATING",
            "approval_level": "A1",
            "requirements_version": "REQ-v1",
            "design_version": "DES-v1",
            "artifacts": ["x"],
            "validation": {
                "council": "CHECKLIST_ONLY",
                "tests": "PASS",
                "traceability": "PASS",
                "independent_rerun": "PASS",
                "review_decision": "OBJECT",
            },
        }
        failures = AUTO.evaluate_autonomy_done(job)
        self.assertTrue(any("did not approve" in item for item in failures))
        self.assertFalse(MISSION.job_meets_mission_success({
            "state": "OWNER_REVIEW",
            "validation": job["validation"],
        }))
        approved = dict(job)
        approved["state"] = "OWNER_REVIEW"
        approved["validation"] = dict(job["validation"])
        approved["validation"]["review_decision"] = "APPROVE"
        self.assertEqual(AUTO.evaluate_autonomy_done({**job, "validation": approved["validation"]}), [])
        self.assertTrue(MISSION.job_meets_mission_success(approved))

    def test_dispatched_consultation_is_not_consulted(self):
        def invoke(advisor, evidence):
            return {"status": "DISPATCHED", "response": {"job_id": "CONSULT-1", "decision": None, "approval": False}}

        receipt = MISSION.consult_advisors(
            {"hash": "abc", "repo": r"C:\Users\swap2\NEEWA-Personal\projects\ChakraOps"},
            invoke=True,
            invoke_fn=invoke,
            models=[{"id": "neewa-premium", "model": "gpt-5.6-sol", "provider": "openai", "status": "verified"}],
            providers=[{"id": "openai", "status": "active", "cost_class": "subscription"}],
        )
        self.assertEqual(receipt["consulted_count"], 0)

    def test_explicit_modify_existing_survives_sandbox_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = AUTO.create_parent_job(
                "Make canary.answer return 42",
                workspace=r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox\neewa-lifecycle-canary",
                project_lifecycle="modify_existing",
                root=root,
            )
            self.assertEqual(job["project_lifecycle"], "modify_existing")
            AUTO.attach_project_identity(job)
            self.assertEqual(job["project_lifecycle"], "modify_existing")

    def test_charter_plan_has_more_than_the_first_two_stages(self):
        plan = MISSION.default_stage_plan("PRJ-CHAKRAOPS", "reconcile")
        self.assertGreater(len(plan), 2)
        self.assertEqual(plan[0]["id"], "orats_reconciliation")
        self.assertIn("no_signal_evidence", [stage["id"] for stage in plan])
        self.assertIn("traceability", [stage["id"] for stage in plan])

    def test_handoff_adopts_only_the_named_failed_mission(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "autonomy"
            inbox = Path(tmp) / "inbox"
            root.mkdir()
            (inbox / "records").mkdir(parents=True)
            failed = {
                "mission_id": "MISSION-KEEP",
                "project_id": "PRJ-CHAKRAOPS",
                "state": "FAILED",
                "failure_reason": "MAX_REPAIR_CYCLES",
                "repair_cycles": 3,
                "auto_continue": True,
                "stage_plan": [{"id": "orats_reconciliation", "status": "in_progress", "objective": "orats"}],
                "history": [{"state": "FAILED", "at": "2026-10-08T17:17:04Z", "note": "MAX_REPAIR_CYCLES"}],
                "failure_history": [],
            }
            other = dict(failed)
            other["mission_id"] = "MISSION-OTHER"
            other["project_id"] = "PRJ-OTHER"
            (root / "MISSION-KEEP.json").write_text(json.dumps(failed), encoding="utf-8")
            (root / "MISSION-OTHER.json").write_text(json.dumps(other), encoding="utf-8")
            (inbox / "records" / "neewa-handoff-latest.json").write_text(json.dumps({
                "handoff_id": "handoff-1",
                "changed_condition": True,
                "adopt_mission_ids": ["MISSION-KEEP"],
            }), encoding="utf-8")
            adopted = MISSION.adopt_bridge_handoff(root, inbox)
            self.assertEqual([row["mission_id"] for row in adopted], ["MISSION-KEEP"])
            kept = json.loads((root / "MISSION-KEEP.json").read_text(encoding="utf-8"))
            untouched = json.loads((root / "MISSION-OTHER.json").read_text(encoding="utf-8"))
            self.assertEqual(kept["state"], "PLANNING")
            self.assertEqual(kept["terminal_result"], "FAILED")
            self.assertGreater(len(kept["stage_plan"]), 2)
            self.assertEqual(untouched["state"], "FAILED")
            again = MISSION.adopt_bridge_handoff(root, inbox)
            self.assertEqual(again, [])


class WindowsRunnerTests(unittest.TestCase):
    def test_installed_script_parses_and_drains_both_streams(self):
        if os.name != "nt":
            self.skipTest("Windows runner proof")
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if shell is None:
            self.skipTest("PowerShell is required")
        script = WORKER / "Invoke-NeewaDrainedProcess.ps1"
        with tempfile.TemporaryDirectory() as tmp:
            probe = Path(tmp) / "drain.ps1"
            probe.write_text(
                "\n".join([
                    "$ErrorActionPreference = 'Stop'",
                    f". '{script}'",
                    "$psi = New-Object System.Diagnostics.ProcessStartInfo",
                    f"$psi.FileName = '{shell}'",
                    "$psi.Arguments = '-NoProfile -Command \"[Console]::Out.WriteLine((''x'' * 70000)); [Console]::Error.WriteLine((''y'' * 70000))\"'",
                    "$psi.UseShellExecute = $false",
                    "$psi.RedirectStandardOutput = $true",
                    "$psi.RedirectStandardError = $true",
                    "$psi.CreateNoWindow = $true",
                    "$result = Invoke-NeewaDrainedProcess -StartInfo $psi -TimeoutMs 20000",
                    "if ($result.TimedOut) { exit 2 }",
                    "if ($result.Stdout.Length -lt 60000) { exit 3 }",
                    "if ($result.Stderr.Length -lt 60000) { exit 4 }",
                    "$hang = New-Object System.Diagnostics.ProcessStartInfo",
                    f"$hang.FileName = '{shell}'",
                    "$hang.Arguments = '-NoProfile -Command \"Start-Sleep -Seconds 30\"'",
                    "$hang.UseShellExecute = $false",
                    "$hang.RedirectStandardOutput = $true",
                    "$hang.RedirectStandardError = $true",
                    "$hang.CreateNoWindow = $true",
                    "$timed = Invoke-NeewaDrainedProcess -StartInfo $hang -TimeoutMs 1500",
                    "if (-not $timed.TimedOut) { exit 5 }",
                    "",
                ]),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(probe)],
                capture_output=True,
                text=True,
                timeout=40,
            )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
