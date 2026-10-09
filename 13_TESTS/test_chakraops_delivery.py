import json
import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "16_WINDOWS_CLIENT" / "worker"
SEM = SourceFileLoader("neewa_action_semantics_delivery", str(ROOT / "12_SCRIPTS" / "neewa_action_semantics.py")).load_module()
MISSION = SourceFileLoader("neewa_mission_delivery", str(ROOT / "12_SCRIPTS" / "neewa_mission.py")).load_module()
AUTO = SourceFileLoader("neewa_autonomy_delivery", str(ROOT / "12_SCRIPTS" / "neewa_autonomy.py")).load_module()
ORCH = SourceFileLoader("neewa_orchestrate_delivery", str(ROOT / "12_SCRIPTS" / "neewa_orchestrate.py")).load_module()
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
        self.assertIn("'-s', 'read-only'", review)
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


class ReceiptConsumptionTests(unittest.TestCase):
    def test_completed_receipt_beats_stale_processing_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job_id = "JOB-STALE-CLAIM"
            for folder in ("inbox", "processing", "done", "failed", "records"):
                (root / folder).mkdir()
            (root / "processing" / f"{job_id}.json").write_text(
                json.dumps({"job_id": job_id, "state": "RUNNING", "status": "RUNNING"}),
                encoding="utf-8",
            )
            (root / "done" / f"{job_id}.json").write_text(
                json.dumps({"job_id": job_id, "status": "COMPLETED", "artifact": "artifact.json"}),
                encoding="utf-8",
            )
            folder, payload = ORCH.inspect_folders(job_id, root)
            self.assertEqual(folder, "VALIDATING")
            self.assertEqual(payload["status"], "COMPLETED")
            ORCH.save_record(
                {"job_id": job_id, "state": "RUNNING", "history": [{"state": "RUNNING", "at": "2020-01-01T00:00:00Z"}]},
                root,
            )
            first = ORCH.harvest(job_id, root)
            second = ORCH.harvest(job_id, root)
            self.assertEqual(first["state"], "COMPLETED")
            self.assertEqual(second["state"], "COMPLETED")
            self.assertEqual(len(second["history"]), len(first["history"]))
            self.assertEqual((second.get("validation") or {}).get("worker_status"), "COMPLETED")

    def test_unreadable_done_file_does_not_hide_processing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job_id = "JOB-BAD-DONE"
            (root / "processing").mkdir()
            (root / "done").mkdir()
            (root / "done" / f"{job_id}.json").write_text("{", encoding="utf-8")
            (root / "processing" / f"{job_id}.json").write_text(
                json.dumps({"job_id": job_id, "state": "RUNNING"}),
                encoding="utf-8",
            )
            (root / "records").mkdir()
            (root / "records" / f"{job_id}.progress.json").write_text(
                json.dumps({"progress_at": "2026-10-08T13:45:58Z", "child_pid": 53284}),
                encoding="utf-8",
            )
            folder, payload = ORCH.inspect_folders(job_id, root)
            self.assertEqual(folder, "RUNNING")
            self.assertEqual(payload["progress_at"], "2026-10-08T13:45:58Z")
            ORCH.save_record({"job_id": job_id, "state": "DISPATCHED", "history": []}, root)
            record = ORCH.harvest(job_id, root)
            self.assertEqual(record["state"], "RUNNING")
            self.assertEqual(record["progress_at"], "2026-10-08T13:45:58Z")

    def _old_child(self, root: Path, child_id: str = "JOB-CC02") -> dict:
        job = AUTO.create_parent_job("repair the execution path", root=root)
        job["state"] = "EXECUTING"
        job["workflow"] = "sdlc"
        job["timeout_sec"] = 1
        job["active_child_id"] = child_id
        job["child_jobs"] = [{"job_id": child_id, "at": "2020-01-01T00:00:00Z"}]
        AUTO.save_job(job)
        return job

    def test_late_completion_is_harvested_before_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobs"
            job = self._old_child(root)
            finished = AUTO.reconcile_parent_job(
                job,
                orch_harvest=lambda *a, **k: {"state": "COMPLETED", "job_id": "JOB-CC02"},
            )
            self.assertEqual(finished["state"], "EXECUTING")
            self.assertNotEqual(finished.get("failure_reason"), "CHILD_TIMEOUT")
            self.assertEqual(finished["_harvested_child"]["state"], "COMPLETED")
            self.assertFalse(MISSION.job_meets_mission_success(finished))

    def test_running_child_with_fresh_progress_stays_executing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobs"
            job = self._old_child(root)
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            finished = AUTO.reconcile_parent_job(
                job,
                orch_harvest=lambda *a, **k: {"state": "RUNNING", "progress_at": stamp, "child_pid": 53284},
            )
            self.assertEqual(finished["state"], "EXECUTING")
            self.assertEqual(finished["active_child_id"], "JOB-CC02")
            self.assertEqual(finished["child_progress_at"], stamp)
            self.assertNotEqual(finished.get("failure_reason"), "CHILD_TIMEOUT")

    def test_queued_child_past_poll_wait_does_not_start_another_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobs"
            job = self._old_child(root)
            finished = AUTO.reconcile_parent_job(
                job,
                orch_harvest=lambda *a, **k: {"state": "QUEUED"},
            )
            self.assertEqual(finished["state"], "EXECUTING")
            self.assertEqual(finished["active_child_id"], "JOB-CC02")
            self.assertEqual(finished.get("wait_state"), "WAIT_EXPIRED")
            self.assertEqual(finished.get("failure_class"), "WAIT_EXPIRED")
            classified = MISSION.classify_failure(finished)
            self.assertTrue(classified["waiting"])
            self.assertFalse(classified["recoverable"])
            self.assertEqual(classified["class"], "WAIT_EXPIRED")

    def test_genuine_dead_child_is_child_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobs"
            job = self._old_child(root)
            finished = AUTO.reconcile_parent_job(
                job,
                orch_harvest=lambda *a, **k: {
                    "state": "RUNNING",
                    "progress_at": "2020-01-01T00:00:00Z",
                    "child_pid": 53284,
                },
            )
            self.assertEqual(finished["state"], "FAILED")
            self.assertEqual(finished["failure_reason"], "CHILD_TIMEOUT")
            self.assertEqual(finished["failure_class"], "CHILD_TIMEOUT")
            self.assertIsNone(finished.get("active_child_id"))

    def test_late_receipt_preserves_historical_failure_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobs"
            job = AUTO.create_parent_job("repair the execution path", root=root)
            job["state"] = "FAILED"
            job["failure_reason"] = "IDENTICAL_FAILURE_NO_NEW_EVIDENCE"
            job["failure_class"] = "CHILD_TIMEOUT"
            job["active_child_id"] = None
            job["child_jobs"] = [{"job_id": "JOB-CC02", "at": "2026-10-08T13:37:00Z"}]
            AUTO.save_job(job)
            harvest = lambda *a, **k: {"state": "COMPLETED", "job_id": "JOB-CC02"}
            once = AUTO.reconcile_parent_job(job, orch_harvest=harvest)
            twice = AUTO.reconcile_parent_job(once, orch_harvest=harvest)
            self.assertEqual(twice["state"], "FAILED")
            self.assertEqual(twice["failure_reason"], "IDENTICAL_FAILURE_NO_NEW_EVIDENCE")
            self.assertEqual(len(twice["late_receipts"]), 1)
            self.assertFalse(twice["late_receipts"][0]["consumed_as_approval"])
            self.assertFalse(MISSION.job_meets_mission_success(twice))

    def test_failed_upload_survives_restart_and_duplicate_delivery_is_acked(self):
        if os.name != "nt":
            self.skipTest("worker outbox probe runs on the Windows worker")
        shell = shutil.which("powershell") or shutil.which("pwsh")
        if shell is None:
            self.skipTest("Windows PowerShell is required")
        script = WORKER / "Start-NeewaWindowsWorker.ps1"
        command = f"""
$ErrorActionPreference = 'Stop'
. '{script}'
$out = Join-Path $env:LOCALAPPDATA 'NEEWA\\scratch\\outbox-regression'
if (Test-Path $out) {{ Remove-Item -Recurse -Force $out }}
New-Item -ItemType Directory -Force -Path $out | Out-Null
$script:NeewaOutbox = $out
$script:RemoteFiles = @{{}}
$script:RemoteCalls = New-Object System.Collections.Generic.List[string]
$script:FailScp = 1
$script:NeewaRemoteCommand = {{
  param($Request)
  $Executable = [string]$Request.Executable
  $ArgumentList = @($Request.ArgumentList)
  $joined = (@($Executable) + $ArgumentList) -join ' '
  $script:RemoteCalls.Add($joined)
  if ($Executable -eq 'scp' -and $script:FailScp -gt 0) {{
    $script:FailScp = $script:FailScp - 1
    return 7
  }}
  if ($Executable -eq 'scp') {{
    $script:RemoteFiles[[string]$ArgumentList[-1]] = 'bytes'
    return 0
  }}
  $text = $ArgumentList -join ' '
  if ($text -match 'test -s\\s+''([^'']+)''') {{
    $path = $Matches[1]
    foreach ($key in @($script:RemoteFiles.Keys)) {{
      if ([string]$key.EndsWith($path)) {{ return 0 }}
    }}
    return 1
  }}
  return 0
}}
$job = Join-Path $out 'JOB-OUTBOX.json'
Set-Content -LiteralPath $job -Value '{{}}' -Encoding utf8
$result = [pscustomobject]@{{ status = 'COMPLETED'; artifact = $null }}
$item = Save-NeewaOutboxResult $job $result
$payload = Join-Path $out 'JOB-OUTBOX.json.payload.json'
if (-not (Test-Path -LiteralPath $payload)) {{ exit 2 }}
$failed = $false
try {{ Send-NeewaOutboxItem $item | Out-Null }} catch {{ $failed = $true }}
if (-not $failed) {{ exit 3 }}
if (-not (Test-Path -LiteralPath $payload)) {{ exit 4 }}
if (Test-Path -LiteralPath ($item + '.ack')) {{ exit 5 }}
$again = Send-NeewaOutboxItem $item
if ($again -ne 'acked') {{ exit 6 }}
if (-not (Test-Path -LiteralPath ($item + '.ack'))) {{ exit 7 }}
if (-not (Test-Path -LiteralPath $payload)) {{ exit 8 }}
if ($script:RemoteFiles.Count -ne 1) {{ exit 9 }}
$calls = $script:RemoteCalls.Count
$dup = Send-NeewaOutboxItem $item
if ($dup -ne 'already-acked') {{ exit 10 }}
if ($script:RemoteCalls.Count -ne $calls) {{ exit 11 }}
"""
        completed = subprocess.run(
            [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


class ContractBehaviorTests(unittest.TestCase):
    def test_parse_utc_accepts_fractional_and_rejects_naive_or_future(self):
        parsed = AUTO.parse_utc("2026-10-08T13:45:58.7279552Z")
        self.assertEqual(parsed.year, 2026)
        self.assertIsNone(AUTO.parse_utc("2026-10-08T13:45:58"))
        self.assertIsNone(AUTO.parse_utc("2099-01-01T00:00:00Z"))

    def test_checklist_is_not_a_consultation(self):
        council = AUTO.run_council(
            {"summary": "scoped change", "acceptance": ["R1"], "components": ["readme.md"], "version": "DES-v1"},
            {"requirements": [{"id": "R1", "text": "keep the note", "kind": "functional"}], "workflow": "sdlc"},
        )
        self.assertFalse(council["checklist_is_consultation"])
        self.assertEqual(council["independence_class"], "deterministic_only")
        self.assertEqual(council["roles"]["INDEPENDENT_CODE_REVIEWER"]["decision"], "CHECKLIST_ONLY")

    def test_conflicting_terminal_receipts_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job_id = "JOB-CONFLICT"
            for folder in ("done", "failed", "processing"):
                (root / folder).mkdir()
            (root / "processing" / f"{job_id}.json").write_text(
                json.dumps({"status": "RUNNING"}), encoding="utf-8"
            )
            (root / "failed" / f"{job_id}.json").write_text(
                json.dumps({"status": "FAILED", "reason": "old"}), encoding="utf-8"
            )
            done = root / "done" / f"{job_id}.json"
            done.write_text(json.dumps({"status": "COMPLETED"}), encoding="utf-8")
            folder, payload = ORCH.inspect_folders(job_id, root)
            self.assertEqual(folder, "VALIDATING")
            self.assertEqual(payload["status"], "COMPLETED")
            self.assertEqual(payload["receipt_conflict"]["selected"], "done")
            self.assertIn("failed", payload["receipt_conflict"]["candidates"])

    def test_owner_review_continues_one_stage_and_historical_review_stays(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobs"
            mission = MISSION.create_mission(
                "build a disposable note with a test",
                workspace=r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox",
                root=root,
                kind="sdlc",
                project_id="PRJ-NEEWA",
            )
            self.assertTrue(mission["auto_continue"])
            self.assertEqual(mission["stage_plan"][1]["status"], "not_started")
            mission["state"] = "OWNER_REVIEW"
            MISSION.save_mission(mission, root)
            continued = MISSION.step_mission(mission, root=root)
            self.assertEqual(continued["state"], "PLANNING")
            self.assertEqual(continued["active_stage_id"], "follow_through")
            historical = MISSION.create_mission(
                "diagnostic only",
                workspace=r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox",
                root=root,
                kind="diagnostic",
            )
            historical["state"] = "OWNER_REVIEW"
            MISSION.save_mission(historical, root)
            stayed = MISSION.step_mission(historical, root=root)
            self.assertEqual(stayed["state"], "OWNER_REVIEW")

    def test_parent_job_records_the_shared_standard(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = AUTO.create_parent_job("repair the note", root=Path(tmp) / "jobs")
            self.assertEqual(job["delivery_standard"], "AI-OPS/delivery/PERSONAL_AUTONOMY_STANDARD.md")
