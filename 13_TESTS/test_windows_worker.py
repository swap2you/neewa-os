import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "16_WINDOWS_CLIENT" / "worker"


class WindowsWorkerTests(unittest.TestCase):
    def test_allowlist_refuses_shell_and_a2(self):
        data = json.loads((WORKER / "allowlist.json").read_text(encoding="utf-8"))
        self.assertNotIn("shell", data["actions"])
        self.assertNotIn("computer_use_unrestricted", data["actions"])
        self.assertEqual(data["public_listener"], False)
        self.assertEqual(data["tailscale_funnel"], False)
        self.assertIn(r"%USERPROFILE%\NEEWA-Personal", data["approved_roots"])
        self.assertIn(r"C:\Development\Workspace", data["approved_roots"])
        self.assertEqual(
            data["approved_root_modes"][r"C:\Development\Workspace"],
            "inventory_readonly_cursor_a1_approved_repos_only",
        )
        self.assertIn("workspace_inventory", data["actions"])
        self.assertEqual(data["actions"]["workspace_inventory"], "A0")
        self.assertIn("cursor_call", data["actions"])
        self.assertEqual(data["actions"]["cursor_call"], "A1")
        self.assertEqual(data["cursor_call"]["ide_launcher_is_not_this"], "cursor.cmd")
        self.assertIn("employer repositories and documents", data["denied_roots"])
        self.assertIn(r"C:\Development\Workspace\api-fintech-automation-platform", data["denied_roots"])

    def test_scripts_exist(self):
        for name in (
            "Install-CuaDriverFromGitHub.ps1",
            "Start-CuaDriver.ps1",
            "Start-NeewaWindowsWorker.ps1",
            "Invoke-NeewaWindowsJob.ps1",
            "Register-NeewaWindowsStartup.ps1",
            "capability-manifest.yaml",
            "allowlist.json",
            "New-WorkspaceInventory.ps1",
            "workspace-inventory-policy.json",
            "cursor-call-policy.json",
            "Invoke-NeewaCursorCall.ps1",
        ):
            self.assertTrue((WORKER / name).is_file(), name)

    def test_no_public_bind_or_funnel_in_worker(self):
        text = "\n".join(
            p.read_text(encoding="utf-8", errors="ignore")
            for p in WORKER.rglob("*")
            if p.is_file() and p.suffix in {".ps1", ".json", ".md", ".yaml", ".py"}
        ).lower()
        self.assertNotIn("0.0.0.0", text)
        self.assertNotIn("tailscale funnel", text)
        self.assertNotIn("irm https://cua.ai", text)

    def test_github_installer_skips_cua_ai(self):
        src = (WORKER / "Install-CuaDriverFromGitHub.ps1").read_text(encoding="utf-8")
        self.assertIn("github.com/trycua/cua/releases/download", src)
        self.assertIn("_install-common.psm1", src)
        self.assertIn("Get-FileHash", src)
        self.assertNotIn("https://cua.ai", src)

    def test_capability_manifest_is_narrow(self):
        src = (WORKER / "capability-manifest.yaml").read_text(encoding="utf-8")
        self.assertIn("version: 3", src)
        self.assertIn("NEEWA-Personal", src)
        self.assertNotIn("ApplicationFrameHost.exe", src)
        self.assertIn("display: false", src)

    def test_inbox_script_blocks_a3(self):
        src = (ROOT / "12_SCRIPTS" / "windows_job_inbox.py").read_text(encoding="utf-8")
        self.assertIn("A2/A3", src)
        self.assertIn("personal_artifact", src)
        self.assertIn("workspace_inventory", src)
        self.assertIn("cursor_call", src)
        self.assertNotIn("0.0.0.0", src)

    def test_workspace_inventory_is_read_only_and_excludes_employer(self):
        policy = json.loads((WORKER / "workspace-inventory-policy.json").read_text(encoding="utf-8"))
        script = (WORKER / "New-WorkspaceInventory.ps1").read_text(encoding="utf-8")
        invoke = (WORKER / "Invoke-NeewaWindowsJob.ps1").read_text(encoding="utf-8")
        self.assertEqual(policy["mode"], "read_only_metadata")
        self.assertEqual(policy["workspace_root"], r"C:\Development\Workspace")
        self.assertIn("NEEWA-OS", policy["personal_projects"])
        self.assertIn("api-fintech-automation-platform", policy["denied_name_equals"])
        self.assertIn("ChakraOptionsWatch", policy["denied_name_equals"])
        self.assertIn(".env", policy["skip_file_names"])
        self.assertIn("Get-Content -Raw -LiteralPath $policyPath", script)
        self.assertNotIn("Get-Content", script.replace("Get-Content -Raw -LiteralPath $policyPath", ""))
        self.assertIn("NEEWA-Personal\\inventory", script)
        self.assertIn("'workspace_inventory'", invoke)
        self.assertNotIn("C:\\Users\\", policy["personal_projects"])
        self.assertIn(".git", policy["skip_dir_names"])
        self.assertIn("User Data", policy["skip_dir_names"])
        self.assertIn("trading", policy["denied_name_contains"])
        worker = (WORKER / "Start-NeewaWindowsWorker.ps1").read_text(encoding="utf-8")
        self.assertIn("poll", worker.lower())
        self.assertIn("ssh", worker.lower())
        self.assertNotIn("0.0.0.0", worker)
        allow = json.loads((WORKER / "allowlist.json").read_text(encoding="utf-8"))
        self.assertEqual(allow["git_writer"], "Cursor")
        self.assertFalse(allow["unrestricted_shell"])
        self.assertFalse(allow["public_listener"])


if __name__ == "__main__":
    unittest.main()
