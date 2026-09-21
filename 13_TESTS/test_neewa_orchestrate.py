import json
import shutil
import subprocess
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORCH = ROOT / "12_SCRIPTS" / "neewa_orchestrate.py"
INBOX = ROOT / "12_SCRIPTS" / "windows_job_inbox.py"
WORKER = ROOT / "16_WINDOWS_CLIENT" / "worker"
POLICY = WORKER / "cursor-call-policy.json"


class OrchestrateTests(unittest.TestCase):
    def setUp(self):
        self.mod = SourceFileLoader("neewa_orchestrate", str(ORCH)).load_module()
        self.inbox = SourceFileLoader("windows_job_inbox_orch", str(INBOX)).load_module()

    def test_route_code_to_cursor(self):
        choice = self.mod.select_worker("code_implementation")
        self.assertTrue(choice["available"])
        self.assertEqual(choice["worker"], "cursor-agent-cli")
        self.assertEqual(choice["action"], "cursor_call")

    def test_route_inventory_to_windows_worker(self):
        choice = self.mod.select_worker("project_inventory")
        self.assertEqual(choice["worker"], "neewa-windows-worker")
        self.assertEqual(choice["action"], "workspace_inventory")

    def test_route_unknown_is_blocked_not_invented(self):
        choice = self.mod.select_worker("quantum-trading")
        self.assertFalse(choice["available"])

    def test_submit_duplicate_job_id_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rec = self.mod.submit(
                job_id="JOB-TEST-DUP",
                capability="project_inventory",
                objective="inventory",
                inbox_root=root,
            )
            self.assertEqual(rec["state"], "DISPATCHED")
            with self.assertRaises(ValueError):
                self.mod.submit(
                    job_id="JOB-TEST-DUP",
                    capability="project_inventory",
                    objective="inventory again",
                    inbox_root=root,
                )

    def test_submit_cursor_records_queued_then_dispatched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rec = self.mod.submit(
                job_id="JOB-TEST-ORCH-CC",
                capability="code_implementation",
                objective="harmless sandbox task",
                repo=r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox",
                prompt="List files. Do not edit files.",
                inbox_root=root,
            )
            self.assertEqual(rec["state"], "DISPATCHED")
            self.assertEqual([h["state"] for h in rec["history"]], ["QUEUED", "DISPATCHED"])
            payload = json.loads((root / "inbox" / "JOB-TEST-ORCH-CC.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["action"], "cursor_call")
            self.assertEqual(payload["selected_worker"], "cursor-agent-cli")

    def test_submit_preserves_unlimited_timeout_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rec = self.mod.submit(
                job_id="JOB-TEST-ORCH-TIMEOUT-0",
                capability="code_implementation",
                objective="harmless sandbox task",
                repo=r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox",
                prompt="List files. Do not edit files.",
                timeout_sec=0,
                inbox_root=root,
            )
            self.assertEqual(rec["state"], "DISPATCHED")
            payload = json.loads((root / "inbox" / "JOB-TEST-ORCH-TIMEOUT-0.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["timeout_sec"], 0)

    def test_harvest_completed_from_done_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rec = self.mod.submit(
                job_id="JOB-TEST-HARVEST",
                capability="project_inventory",
                objective="inventory",
                inbox_root=root,
            )
            inbox_file = root / "inbox" / "JOB-TEST-HARVEST.json"
            done = root / "done"
            done.mkdir(exist_ok=True)
            done_file = done / "JOB-TEST-HARVEST.json"
            done_file.write_text(
                json.dumps(
                    {
                        "job_id": "JOB-TEST-HARVEST",
                        "status": "COMPLETED",
                        "artifact": "report.json",
                        "host": "LAPTOP-HKGLJEE8",
                    }
                ),
                encoding="utf-8",
            )
            inbox_file.unlink()
            harvested = self.mod.harvest("JOB-TEST-HARVEST", root)
            self.assertEqual(harvested["state"], "COMPLETED")
            self.assertIn("report.json", harvested["artifact_paths"])


class CursorCallHardeningTests(unittest.TestCase):
    def test_script_does_not_enable_yolo_or_mcp_autoapprove(self):
        src = "\n".join(
            line for line in (WORKER / "Invoke-NeewaCursorCall.ps1").read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("#")
        )
        self.assertNotIn("'--yolo'", src)
        self.assertNotIn('"--yolo"', src)
        self.assertNotIn("--approve-mcps", src)
        self.assertNotIn("--add-dir", src)
        self.assertIn("--sandbox", src)
        self.assertIn("Windows_NT", src)
        self.assertIn("ask", src)
        self.assertIn("AUTH_REQUIRED", src)
        self.assertIn("taskkill.exe", src)

    def test_policy_keeps_sandbox_enabled(self):
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        self.assertEqual(policy["sandbox"], "omit_on_windows")
        self.assertIn("--yolo", policy["never_pass"])

    def _run(self, job, jobs, dry_run=False, cli=r"C:\neewa-missing\agent.exe"):
        job_path = jobs / "job.json"
        job_path.write_text(json.dumps(job), encoding="utf-8")
        dry = " -DryRun" if dry_run else ""
        override = "" if dry_run else f" -CliPathOverride '{cli}'"
        if not shutil.which("powershell"):
            self.skipTest("powershell not present; Windows worker script tests run on Windows")
        command = (
            f"$job = Get-Content -Raw -LiteralPath '{job_path}' | ConvertFrom-Json; "
            f"& '{WORKER / 'Invoke-NeewaCursorCall.ps1'}' -Job $job "
            f"-JobsDir '{jobs}'{override}{dry} | ConvertTo-Json -Depth 8"
        )
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertTrue(completed.stdout.strip(), completed.stderr)
        return json.loads(completed.stdout)

    def test_path_traversal_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs = Path(tmp)
            result = self._run(
                {
                    "job_id": "JOB-TEST-TRAVERSAL",
                    "prompt": "list files",
                    "repo": r"C:\Development\Workspace\NEEWA-OS\..\OratsUtil",
                    "write": False,
                },
                jobs,
            )
        self.assertEqual(result["status"], "BLOCKED")

    def test_expected_path_escape_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs = Path(tmp)
            result = self._run(
                {
                    "job_id": "JOB-TEST-ESCAPE",
                    "prompt": "write a file",
                    "repo": r"C:\Development\Workspace\NEEWA-OS",
                    "write": True,
                    "expected_paths": [r"..\OratsUtil\secret.txt"],
                },
                jobs,
            )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("escape", result["reason"].lower())

    def test_successful_cli_without_expected_file_is_failed_not_completed(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs = Path(tmp)
            result = self._run(
                {
                    "job_id": "JOB-TEST-VALIDATE",
                    "prompt": "create missing-file-for-validation.py",
                    "repo": r"C:\Development\Workspace\NEEWA-OS",
                    "write": True,
                    "expected_paths": ["missing-file-for-validation.py"],
                },
                jobs,
                dry_run=True,
            )
        self.assertEqual(result["status"], "FAILED")
        self.assertNotEqual(result["status"], "COMPLETED")
        self.assertIn("validation", result["reason"].lower())

    def test_read_only_args_use_ask_not_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs = Path(tmp)
            result = self._run(
                {
                    "job_id": "JOB-TEST-ASK",
                    "prompt": "summarize README only",
                    "repo": r"C:\Development\Workspace\NEEWA-OS",
                    "write": False,
                },
                jobs,
                dry_run=True,
            )
            args = (jobs / "JOB-TEST-ASK-cursor-call.args.txt").read_text(encoding="utf-8")
        self.assertIn("--mode", args)
        self.assertIn("ask", args)
        self.assertNotIn("--force", args)
        self.assertEqual(result["status"], "COMPLETED")


    def test_stack_label_expected_path_is_malformed_not_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs = Path(tmp)
            result = self._run(
                {
                    "job_id": "JOB-TEST-STACK-LABEL",
                    "prompt": "add a negative-path test",
                    "repo": r"C:\Development\Workspace\NEEWA-OS",
                    "write": True,
                    "expected_paths": ["FastAPI/Next.js"],
                },
                jobs,
                dry_run=True,
            )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result.get("failure_class"), "MALFORMED_EXPECTED_PATH")
        self.assertNotEqual(result["status"], "COMPLETED")
        self.assertIn("malformed", result["reason"].lower())


if __name__ == "__main__":
    unittest.main()
