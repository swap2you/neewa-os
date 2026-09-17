import json
import subprocess
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
            "personal_a1_except_denied",
        )
        self.assertIn("workspace_inventory", data["actions"])
        self.assertEqual(data["actions"]["workspace_inventory"], "A0")
        self.assertIn("cursor_call", data["actions"])
        self.assertEqual(data["actions"]["cursor_call"], "A1")
        self.assertIn("repo_preflight", data["actions"])
        self.assertEqual(data["actions"]["repo_preflight"], "A0")
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
            "Invoke-NeewaRepoPreflight.ps1",
            "NeewaPersonalWorkspace.ps1",
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
        self.assertIn("repo_preflight", src)
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

    def test_cursor_call_keeps_approved_child_workspace(self):
        src = (WORKER / "Invoke-NeewaCursorCall.ps1").read_text(encoding="utf-8")
        shared = (WORKER / "NeewaPersonalWorkspace.ps1").read_text(encoding="utf-8")
        self.assertIn("NeewaPersonalWorkspace.ps1", src)
        self.assertIn("KidsProjects\\ScienceQuest", src)
        self.assertIn("return $fullRequested", shared)

    def test_cursor_call_rejects_stack_label_expected_path(self):
        src = (WORKER / "Invoke-NeewaCursorCall.ps1").read_text(encoding="utf-8")
        self.assertIn("Test-MalformedExpectedPath", src)
        self.assertIn("MALFORMED_EXPECTED_PATH", src)
        self.assertIn("FastAPI/Next.js", src)

    def test_repo_preflight_does_not_use_linux_exists_here(self):
        src = (WORKER / "Invoke-NeewaRepoPreflight.ps1").read_text(encoding="utf-8")
        self.assertNotRegex(src, r"\$exists_here")
        self.assertIn("identity_ok", src)
        self.assertIn("A missing path on the Linux core host is not consulted", src)
        invoke = (WORKER / "Invoke-NeewaWindowsJob.ps1").read_text(encoding="utf-8")
        self.assertIn("'repo_preflight'", invoke)

    def test_repo_preflight_identifies_neewa_os(self):
        import json
        import subprocess
        import tempfile
        jobs = Path(tempfile.mkdtemp())
        job_path = jobs / "job.json"
        job_path.write_text(
            json.dumps(
                {
                    "job_id": "JOB-TEST-PREFLIGHT-NEEWA",
                    "action": "repo_preflight",
                    "repo": r"C:\Development\Workspace\NEEWA-OS",
                    "markers": ["12_SCRIPTS", "16_WINDOWS_CLIENT"],
                }
            ),
            encoding="utf-8",
        )
        command = (
            f"& '{WORKER / 'Invoke-NeewaRepoPreflight.ps1'}' "
            f"-JobFile '{job_path}' -OutDir '{jobs}' | ConvertTo-Json -Depth 8"
        )
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertTrue(completed.stdout.strip(), completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "COMPLETED")
        self.assertTrue(result["preflight"]["identity_ok"])
        self.assertTrue(result["preflight"]["exists"])
        self.assertTrue(result["preflight"]["git_ok"])

    def test_personal_workspace_resolver_allows_unlisted_and_denies_employer(self):
        command = (
            "$here = '%s'; "
            "$policy = Get-Content -Raw -LiteralPath (Join-Path $here 'cursor-call-policy.json') | ConvertFrom-Json; "
            ". (Join-Path $here 'NeewaPersonalWorkspace.ps1'); "
            "$ok = Resolve-ApprovedRepo 'C:\\Development\\Workspace\\BrandNewPersonalApp'; "
            "$denied = Resolve-ApprovedRepo 'C:\\Development\\Workspace\\OratsUtil'; "
            "$root = Resolve-ApprovedRepo 'C:\\Development\\Workspace'; "
            "[pscustomobject]@{ ok = $ok; denied = $denied; root = $root } | ConvertTo-Json"
            % str(WORKER).replace("'", "''")
        )
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertTrue(completed.stdout.strip(), completed.stderr)
        data = json.loads(completed.stdout)
        self.assertTrue(data["ok"])
        self.assertIn("BrandNewPersonalApp", data["ok"])
        self.assertFalse(data["denied"])
        self.assertFalse(data["root"])


if __name__ == "__main__":
    unittest.main()
