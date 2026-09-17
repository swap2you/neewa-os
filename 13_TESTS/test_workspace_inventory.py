import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "16_WINDOWS_CLIENT" / "worker"
POLICY = WORKER / "workspace-inventory-policy.json"
INBOX = ROOT / "12_SCRIPTS" / "windows_job_inbox.py"


class WorkspaceInventoryTests(unittest.TestCase):
    def test_inbox_accepts_workspace_inventory_only_at_a1(self):
        from importlib.machinery import SourceFileLoader

        mod = SourceFileLoader("windows_job_inbox", str(INBOX)).load_module()
        self.assertIn("workspace_inventory", mod.ALLOWED)
        with tempfile.TemporaryDirectory() as tmp:
            path = mod.enqueue("JOB-TEST-WS", "workspace_inventory", "A1", Path(tmp))
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["action"], "workspace_inventory")
            with self.assertRaises(ValueError):
                mod.enqueue("JOB-TEST-A3", "workspace_inventory", "A3", Path(tmp))

    def test_generator_produces_personal_metadata_and_skips_denied(self):
        script = WORKER / "New-WorkspaceInventory.ps1"
        if not Path(r"C:\Development\Workspace").is_dir():
            self.skipTest("workspace root not present")
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
            check=True,
            capture_output=True,
            text=True,
        )
        report_path = Path(completed.stdout.strip().splitlines()[-1])
        self.assertTrue(report_path.is_file())
        self.assertEqual(report_path.parent, Path.home() / "NEEWA-Personal" / "inventory")
        data = json.loads(report_path.read_text(encoding="utf-8-sig"))
        self.assertTrue(data["mode"] == "read_only_metadata")
        self.assertFalse(data["write_access"])
        self.assertFalse(data["file_contents_read"])
        by_name = {row["name"]: row for row in data["projects"]}
        self.assertEqual(by_name["NEEWA-OS"]["classification"], "personal")
        self.assertTrue(by_name["NEEWA-OS"]["inventoried"])
        self.assertIn("top_level", by_name["NEEWA-OS"])
        self.assertEqual(by_name["api-fintech-automation-platform"]["classification"], "denied")
        self.assertFalse(by_name["api-fintech-automation-platform"]["inventoried"])
        self.assertNotIn("top_level", by_name["api-fintech-automation-platform"])
        if "Udemy-Yutube-repos" in by_name:
            self.assertEqual(by_name["Udemy-Yutube-repos"]["classification"], "personal")
            self.assertTrue(by_name["Udemy-Yutube-repos"]["inventoried"])
        self.assertNotIn(".git", by_name["NEEWA-OS"]["top_level"])
        blob = json.dumps(data)
        self.assertNotIn("BEGIN PRIVATE KEY", blob)
        self.assertNotIn("sk-", blob)
        self.assertNotIn("AppData\\Local\\Google\\Chrome", blob)

    def test_invoke_workspace_inventory_end_to_end_read_only(self):
        invoke = WORKER / "Invoke-NeewaWindowsJob.ps1"
        if not Path(r"C:\Development\Workspace").is_dir():
            self.skipTest("workspace root not present")
        job_id = "JOB-20260917-E2E-WS"
        stamp = Path.home() / "NEEWA-Personal" / "jobs" / f"{job_id}.done.json"
        if stamp.exists():
            stamp.unlink()
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp) / f"{job_id}.json"
            job.write_text(
                json.dumps({"job_id": job_id, "action": "workspace_inventory", "approval": "A1"}) + "\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(invoke),
                    "-JobPath",
                    str(job),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        self.assertIn(job_id, completed.stdout)
        self.assertIn("complete", completed.stdout.lower())
        artifact = Path.home() / "NEEWA-Personal" / "jobs" / f"{job_id}-workspace-inventory.json"
        self.assertTrue(artifact.is_file())
        data = json.loads(artifact.read_text(encoding="utf-8-sig"))
        self.assertFalse(data["write_access"])
        self.assertFalse(data["file_contents_read"])


if __name__ == "__main__":
    unittest.main()
