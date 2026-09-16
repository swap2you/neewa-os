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
        self.assertIn("employer repositories and documents", data["denied_roots"])

    def test_scripts_exist(self):
        for name in (
            "Install-CuaDriverFromGitHub.ps1",
            "Start-CuaDriver.ps1",
            "Start-NeewaWindowsWorker.ps1",
            "Invoke-NeewaWindowsJob.ps1",
            "Register-NeewaWindowsStartup.ps1",
            "capability-manifest.yaml",
            "allowlist.json",
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
        self.assertNotIn("0.0.0.0", src)


if __name__ == "__main__":
    unittest.main()
