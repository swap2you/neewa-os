import json
import shutil
import subprocess
import tempfile
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
        self.assertIn("create_scoped_repair_workspace", data["actions"])
        self.assertEqual(data["actions"]["create_scoped_repair_workspace"], "A1")
        self.assertIn("review_scoped_repair_patch", data["actions"])
        self.assertEqual(data["actions"]["review_scoped_repair_patch"], "A0")
        self.assertIn("apply_scoped_repair_patch", data["actions"])
        self.assertEqual(data["actions"]["apply_scoped_repair_patch"], "A1")
        self.assertIn("cleanup_scoped_repair_workspace", data["actions"])
        self.assertEqual(data["actions"]["cleanup_scoped_repair_workspace"], "A1")
        self.assertIn("git_push_feature_branch", data["actions"])
        self.assertEqual(data["actions"]["git_push_feature_branch"], "A2")
        self.assertEqual(data["actions"]["home_mission_submit"], "A1")
        self.assertEqual(data["actions"]["home_mission_status"], "A0")
        self.assertIn("git_verify_remote_state", data["actions"])
        self.assertEqual(data["cursor_call"]["ide_launcher_is_not_this"], "cursor.cmd")
        self.assertIn("employer repositories and documents", data["denied_roots"])
        self.assertIn(r"C:\Development\Workspace\api-fintech-automation-platform", data["denied_roots"])

    def test_scripts_exist(self):
        for name in (
            "Install-CuaDriverFromGitHub.ps1",
            "Install-NeewaWindowsWorker.ps1",
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
            "Invoke-NeewaScopedRepair.ps1",
            "Invoke-NeewaGovernedGit.ps1",
            "NeewaPersonalWorkspace.ps1",
            "Resolve-NeewaResultFolder.ps1",
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
        self.assertIn("create_scoped_repair_workspace", src)
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
        self.assertIn("Resolve-NeewaResultFolder", worker)
        self.assertIn("done", Path(WORKER / "Resolve-NeewaResultFolder.ps1").read_text(encoding="utf-8"))

    def test_result_folder_routes_completed_failed_and_blocked(self):
        if not shutil.which("powershell"):
            self.skipTest("powershell not present")
        script = WORKER / "Resolve-NeewaResultFolder.ps1"
        cases = (
            ('{"status":"COMPLETED"}', "done"),
            ('{"status":"complete"}', "done"),
            ('{"status":"FAILED"}', "failed"),
            ('{"status":"BLOCKED"}', "failed"),
        )
        for payload, expected in cases:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-File", str(script), payload],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(completed.stdout.strip(), expected, completed.stderr or payload)
        array_json = '[{"noise":true},{"status":"COMPLETED"}]'
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f". '{script}'; Resolve-NeewaResultFolder ('{array_json}' | ConvertFrom-Json)",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(completed.stdout.strip(), "done", completed.stderr)

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
        self.assertIn("'create_scoped_repair_workspace'", invoke)
        self.assertIn("Invoke-NeewaScopedRepair.ps1", invoke)

    def test_repo_preflight_identifies_neewa_os(self):
        if not shutil.which("powershell"):
            self.skipTest("powershell not present")
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
        if not shutil.which("powershell"):
            self.skipTest("powershell not present")
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

    def _run_preflight(self, job: dict, out_dir: Path, policy: Path) -> dict:
        if not shutil.which("powershell"):
            self.skipTest("powershell not present; Windows worker script tests run on Windows")
        job_path = out_dir / "job.json"
        job_path.write_text(json.dumps(job), encoding="utf-8")
        command = (
            f"& '{WORKER / 'Invoke-NeewaRepoPreflight.ps1'}' "
            f"-JobFile '{job_path}' -OutDir '{out_dir}' -PolicyFile '{policy}' "
            f"| ConvertTo-Json -Depth 8"
        )
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertTrue(completed.stdout.strip(), completed.stderr)
        return json.loads(completed.stdout)

    def test_repo_preflight_create_new_does_not_require_git(self):
        if not shutil.which("powershell"):
            self.skipTest("powershell not present")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sandbox = root / "cursor-sandbox"
            sandbox.mkdir()
            workspace = root / "workspace"
            workspace.mkdir()
            policy = json.loads((WORKER / "cursor-call-policy.json").read_text(encoding="utf-8"))
            policy["sandbox_repo"] = str(sandbox)
            policy["workspace_root"] = str(workspace)
            policy["personal_roots"] = [str(sandbox), str(workspace)]
            policy_path = root / "policy.json"
            policy_path.write_text(json.dumps(policy), encoding="utf-8")
            out = root / "pf"
            out.mkdir()
            target = sandbox / "preflight_new"
            first = self._run_preflight(
                {
                    "job_id": "JOB-TEST-PF-CREATE",
                    "action": "repo_preflight",
                    "repo": str(target),
                    "project_lifecycle": "create_new",
                    "workspace_root": str(sandbox),
                },
                out,
                policy_path,
            )
            self.assertEqual(first["status"], "COMPLETED", first)
            self.assertTrue(first["preflight"]["identity_ok"])
            self.assertFalse(first["preflight"]["git_ok"])
            self.assertTrue(target.is_dir())
            second = self._run_preflight(
                {
                    "job_id": "JOB-TEST-PF-CREATE-2",
                    "action": "repo_preflight",
                    "repo": str(target),
                    "project_lifecycle": "create_new",
                    "workspace_root": str(sandbox),
                },
                out,
                policy_path,
            )
            self.assertEqual(second["preflight"]["bootstrap_result"], "reused_empty")
            missing_existing = self._run_preflight(
                {
                    "job_id": "JOB-TEST-PF-MISSING-EXISTING",
                    "action": "repo_preflight",
                    "repo": str(sandbox / "never_made"),
                    "project_lifecycle": "modify_existing",
                },
                out,
                policy_path,
            )
            self.assertEqual(missing_existing["status"], "FAILED")
            self.assertEqual(missing_existing.get("failure_class"), "MISSING_REPO")
            self.assertFalse((sandbox / "never_made").exists())


if __name__ == "__main__":
    unittest.main()
