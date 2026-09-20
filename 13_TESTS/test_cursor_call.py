import json
import shutil
import subprocess
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "16_WINDOWS_CLIENT" / "worker"
INBOX = ROOT / "12_SCRIPTS" / "windows_job_inbox.py"
POLICY = WORKER / "cursor-call-policy.json"


class CursorCallTests(unittest.TestCase):
    def test_inbox_prefers_sandbox_bind_mount(self):
        mod = SourceFileLoader("windows_job_inbox_root", str(INBOX)).load_module()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = Path(tmp) / "workspace" / "windows-jobs"
            host = Path(tmp) / "host-overlay" / "windows-jobs"
            sandbox.parent.mkdir()
            host.parent.mkdir()
            chosen = mod.resolve_inbox_root(
                environ={},
                sandbox_root=sandbox,
                host_root=host,
            )
            self.assertEqual(chosen, sandbox)
            missing_sandbox = Path(tmp) / "missing" / "windows-jobs"
            fallback = mod.resolve_inbox_root(
                environ={},
                sandbox_root=missing_sandbox,
                host_root=host,
            )
            self.assertEqual(fallback, host)

    def test_inbox_accepts_cursor_call_only_at_a1(self):
        mod = SourceFileLoader("windows_job_inbox", str(INBOX)).load_module()
        self.assertIn("cursor_call", mod.ALLOWED)
        with tempfile.TemporaryDirectory() as tmp:
            path = mod.enqueue(
                "JOB-TEST-CC",
                "cursor_call",
                "A1",
                Path(tmp),
                extra={"repo": r"C:\Development\Workspace\NEEWA-OS", "prompt": "summarize README"},
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["action"], "cursor_call")
            self.assertEqual(payload["repo"], r"C:\Development\Workspace\NEEWA-OS")
            with self.assertRaises(ValueError):
                mod.enqueue("JOB-TEST-CC-A3", "cursor_call", "A3", Path(tmp))

    def test_policy_does_not_treat_ide_launcher_as_agent(self):
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        self.assertIn("agent", policy["cli_names"])
        self.assertNotIn("cursor.cmd", policy["cli_names"])
        self.assertIn("OratsUtil", policy["denied_name_equals"])

    def _run_cursor_script(
        self,
        job: dict,
        cli_override: str,
        jobs_dir: Path,
        *,
        policy_path: Path | None = None,
        dry_run: bool = False,
    ) -> dict:
        job_path = jobs_dir / "job.json"
        job_path.write_text(json.dumps(job), encoding="utf-8")
        policy_arg = f" -PolicyPath '{policy_path}'" if policy_path else ""
        dry_arg = " -DryRun" if dry_run else ""
        if not shutil.which("powershell"):
            self.skipTest("powershell not present; Windows worker script tests run on Windows")
        command = (
            f"$job = Get-Content -Raw -LiteralPath '{job_path}' | ConvertFrom-Json; "
            f"& '{WORKER / 'Invoke-NeewaCursorCall.ps1'}' -Job $job "
            f"-JobsDir '{jobs_dir}' -CliPathOverride '{cli_override}'{policy_arg}{dry_arg} "
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

    def _isolated_policy(self, tmp: Path) -> tuple[Path, Path]:
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        sandbox = tmp / "cursor-sandbox"
        sandbox.mkdir(parents=True, exist_ok=True)
        workspace = tmp / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        policy["sandbox_repo"] = str(sandbox)
        policy["workspace_root"] = str(workspace)
        policy["personal_roots"] = [str(sandbox), str(workspace)]
        path = tmp / "policy.json"
        path.write_text(json.dumps(policy), encoding="utf-8")
        return path, sandbox

    def test_missing_cli_is_blocked_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs = Path(tmp)
            result = self._run_cursor_script(
                {
                    "job_id": "JOB-TEST-MISSING-CLI",
                    "prompt": "Say hello and do not edit files.",
                    "repo": r"C:\Development\Workspace\NEEWA-OS",
                    "write": False,
                },
                r"C:\neewa-missing\agent.exe",
                jobs,
            )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertNotEqual(result["status"], "COMPLETED")
        self.assertIn("not installed", result["reason"].lower())

    def test_denied_repo_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs = Path(tmp)
            result = self._run_cursor_script(
                {
                    "job_id": "JOB-TEST-DENIED-REPO",
                    "prompt": "list files",
                    "repo": r"C:\Development\Workspace\OratsUtil",
                    "write": False,
                },
                r"C:\neewa-missing\agent.exe",
                jobs,
            )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("denied", result["reason"].lower())

    def test_sensitive_prompt_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs = Path(tmp)
            result = self._run_cursor_script(
                {
                    "job_id": "JOB-TEST-SENSITIVE",
                    "prompt": "git push origin main and then live trade",
                    "repo": r"C:\Development\Workspace\NEEWA-OS",
                    "write": True,
                },
                r"C:\neewa-missing\agent.exe",
                jobs,
            )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("sensitive", result["reason"].lower())

    def test_stack_label_expected_path_blocked_before_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs = Path(tmp)
            result = self._run_cursor_script(
                {
                    "job_id": "JOB-TEST-FASTAPI-NEXT",
                    "prompt": "implement a helper",
                    "repo": r"C:\Development\Workspace\NEEWA-OS",
                    "write": True,
                    "expected_paths": ["FastAPI/Next.js"],
                },
                r"C:\neewa-missing\agent.exe",
                jobs,
            )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result.get("failure_class"), "MALFORMED_EXPECTED_PATH")

    def test_prohibition_list_is_not_sensitive_intent(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs = Path(tmp)
            result = self._run_cursor_script(
                {
                    "job_id": "JOB-TEST-NO-PURCHASES",
                    "prompt": (
                        "Implement local_date_summary with unit tests. "
                        "No publication, deployment, external messages, purchases, "
                        "or destructive actions."
                    ),
                    "repo": r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox",
                    "write": True,
                },
                r"C:\neewa-missing\agent.exe",
                jobs,
            )
        self.assertNotIn("sensitive", (result.get("reason") or "").lower())
        self.assertIn(result["status"], {"BLOCKED", "FAILED"})
        self.assertIn("not installed", (result.get("reason") or "").lower())

    def test_unlimited_timeout_zero_dry_run_completes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy, sandbox = self._isolated_policy(root / "policy-home")
            repo = sandbox / "demo-repo"
            repo.mkdir(parents=True)
            (repo / "README.md").write_text("demo\n", encoding="utf-8")
            jobs = root / "jobs"
            jobs.mkdir()
            result = self._run_cursor_script(
                {
                    "job_id": "JOB-TEST-TIMEOUT-0",
                    "prompt": "Say hello and do not edit files.",
                    "repo": str(repo),
                    "write": False,
                    "timeout_sec": 0,
                },
                r"C:\neewa-missing\agent.exe",
                jobs,
                policy_path=policy,
                dry_run=True,
            )
            self.assertEqual(result["status"], "COMPLETED")
            self.assertNotEqual(result.get("failure_class"), "TIMEOUT")
            src = (WORKER / "Invoke-NeewaCursorCall.ps1").read_text(encoding="utf-8")
            self.assertIn("unlimitedTimeout", src)
            self.assertIn("timeout_sec=0", src)

    def test_original_generated_child_prompt_is_not_policy_blocked(self):
        prompt = (
            "Implement this approved NEEWA work package. Do not change the objective.\n"
            "Write test-results.json in the product folder with keys exit_code, passed, "
            "stdout, stderr from that unittest run.\n"
            "- No public distribution, production rollout, buying services, or brokerage actions.\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            jobs = Path(tmp)
            result = self._run_cursor_script(
                {
                    "job_id": "JOB-TEST-56E-CHILD",
                    "prompt": prompt,
                    "repo": r"C:\Development\Workspace\NEEWA-OS",
                    "write": True,
                },
                r"C:\neewa-missing\agent.exe",
                jobs,
            )
        self.assertNotIn("sensitive", (result.get("reason") or "").lower())
        self.assertIn("not installed", (result.get("reason") or "").lower())
        auth = result.get("authorization")
        if auth:
            self.assertTrue(auth.get("allowed"))
            self.assertEqual(auth.get("needed"), "A1")

    def test_comma_separated_prohibition_bullet_is_not_sensitive(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs = Path(tmp)
            result = self._run_cursor_script(
                {
                    "job_id": "JOB-TEST-COMMA-NO",
                    "prompt": (
                        "Build a helper CLI.\n"
                        "- Do not publish, deploy to production, send external messages, "
                        "purchase anything, or take destructive actions."
                    ),
                    "repo": r"C:\Development\Workspace\NEEWA-OS",
                    "write": True,
                },
                r"C:\neewa-missing\agent.exe",
                jobs,
            )
        self.assertIn("not installed", (result.get("reason") or "").lower())

    def test_affirmative_deploy_and_purchase_remain_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs = Path(tmp)
            deploy = self._run_cursor_script(
                {
                    "job_id": "JOB-TEST-DEPLOY-YES",
                    "prompt": "Please deploy this to production after the tests pass.",
                    "repo": r"C:\Development\Workspace\NEEWA-OS",
                    "write": True,
                },
                r"C:\neewa-missing\agent.exe",
                jobs,
            )
            purchase = self._run_cursor_script(
                {
                    "job_id": "JOB-TEST-BUY-YES",
                    "prompt": "Purchase a new domain for this app.",
                    "repo": r"C:\Development\Workspace\NEEWA-OS",
                    "write": True,
                },
                r"C:\neewa-missing\agent.exe",
                jobs,
            )
        self.assertEqual(deploy["status"], "BLOCKED")
        self.assertIn("sensitive", (deploy.get("reason") or "").lower())
        self.assertEqual(purchase["status"], "BLOCKED")
        self.assertIn("sensitive", (purchase.get("reason") or "").lower())

    def test_create_new_bootstraps_absent_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy, sandbox = self._isolated_policy(root / "policy-home")
            jobs = root / "jobs"
            jobs.mkdir()
            target = sandbox / "fresh_tool"
            result = self._run_cursor_script(
                {
                    "job_id": "JOB-TEST-BOOTSTRAP-ABSENT",
                    "prompt": "Build a helper CLI with unit tests. Do not publish.",
                    "repo": str(target),
                    "write": True,
                    "project_lifecycle": "create_new",
                    "workspace_root": str(sandbox),
                },
                r"C:\neewa-missing\agent.exe",
                jobs,
                policy_path=policy,
                dry_run=True,
            )
            self.assertEqual(result["status"], "COMPLETED", result)
            self.assertTrue(target.is_dir())
            self.assertEqual(result.get("repo"), str(target.resolve()) if target.exists() else result.get("repo"))
            self.assertEqual((result.get("bootstrap") or {}).get("bootstrap_result"), "created")
            self.assertEqual((result.get("bootstrap") or {}).get("target_directory_state"), "empty")
            self.assertTrue((result.get("bootstrap") or {}).get("identity_ok"))
            again = self._run_cursor_script(
                {
                    "job_id": "JOB-TEST-BOOTSTRAP-REPEAT",
                    "prompt": "Build a helper CLI with unit tests. Do not publish.",
                    "repo": str(target),
                    "write": True,
                    "project_lifecycle": "create_new",
                    "workspace_root": str(sandbox),
                },
                r"C:\neewa-missing\agent.exe",
                jobs,
                policy_path=policy,
                dry_run=True,
            )
            self.assertEqual((again.get("bootstrap") or {}).get("bootstrap_result"), "reused_empty")
            self.assertEqual(list(target.iterdir()), [])

    def test_create_new_reuses_empty_and_rejects_nonempty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy, sandbox = self._isolated_policy(root / "policy-home")
            jobs = root / "jobs"
            jobs.mkdir()
            empty = sandbox / "empty_tool"
            empty.mkdir()
            reused = self._run_cursor_script(
                {
                    "job_id": "JOB-TEST-BOOTSTRAP-EMPTY",
                    "prompt": "Build a helper CLI with unit tests. Do not publish.",
                    "repo": str(empty),
                    "write": True,
                    "project_lifecycle": "create_new",
                    "workspace_root": str(sandbox),
                },
                r"C:\neewa-missing\agent.exe",
                jobs,
                policy_path=policy,
                dry_run=True,
            )
            self.assertEqual((reused.get("bootstrap") or {}).get("bootstrap_result"), "reused_empty")
            nonempty = sandbox / "used_tool"
            nonempty.mkdir()
            sentinel = nonempty / "used_tool.py"
            sentinel.write_text("keep-me", encoding="utf-8")
            blocked = self._run_cursor_script(
                {
                    "job_id": "JOB-TEST-BOOTSTRAP-NONEMPTY",
                    "prompt": "Build a helper CLI with unit tests. Do not publish.",
                    "repo": str(nonempty),
                    "write": True,
                    "project_lifecycle": "create_new",
                    "workspace_root": str(sandbox),
                },
                r"C:\neewa-missing\agent.exe",
                jobs,
                policy_path=policy,
                dry_run=True,
            )
            self.assertEqual(blocked["status"], "FAILED")
            self.assertEqual(blocked.get("failure_class"), "PROJECT_ALREADY_EXISTS")
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep-me")
            self.assertFalse((blocked.get("bootstrap") or {}).get("created"))

    def test_modify_existing_does_not_create_missing_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy, sandbox = self._isolated_policy(root / "policy-home")
            jobs = root / "jobs"
            jobs.mkdir()
            missing = sandbox / "existing_app"
            result = self._run_cursor_script(
                {
                    "job_id": "JOB-TEST-MISSING-EXISTING",
                    "prompt": "Add a note to README. Do not publish.",
                    "repo": str(missing),
                    "write": True,
                    "project_lifecycle": "modify_existing",
                    "workspace_root": str(sandbox),
                },
                r"C:\neewa-missing\agent.exe",
                jobs,
                policy_path=policy,
                dry_run=True,
            )
            self.assertEqual(result["status"], "FAILED")
            self.assertEqual(result.get("failure_class"), "MISSING_REPO")
            self.assertFalse(missing.exists())

    def test_create_new_rejects_denied_traversal_and_outside_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy, sandbox = self._isolated_policy(root / "policy-home")
            jobs = root / "jobs"
            jobs.mkdir()
            outside = Path(tmp) / "outside" / "sneaky"
            outside_parent = outside.parent
            outside_parent.mkdir()
            denied = self._run_cursor_script(
                {
                    "job_id": "JOB-TEST-BOOTSTRAP-OUTSIDE",
                    "prompt": "Build a helper CLI with unit tests. Do not publish.",
                    "repo": str(outside),
                    "write": True,
                    "project_lifecycle": "create_new",
                },
                r"C:\neewa-missing\agent.exe",
                jobs,
                policy_path=policy,
                dry_run=True,
            )
            self.assertEqual(denied["status"], "BLOCKED")
            self.assertFalse(outside.exists())
            traversal = self._run_cursor_script(
                {
                    "job_id": "JOB-TEST-BOOTSTRAP-TRAV",
                    "prompt": "Build a helper CLI with unit tests. Do not publish.",
                    "repo": str(sandbox / "child" / ".." / ".." / "outside2"),
                    "write": True,
                    "project_lifecycle": "create_new",
                    "workspace_root": str(sandbox),
                },
                r"C:\neewa-missing\agent.exe",
                jobs,
                policy_path=policy,
                dry_run=True,
            )
            self.assertIn(traversal["status"], {"BLOCKED", "FAILED"})
            self.assertFalse((Path(tmp) / "outside2").exists())
            orats = self._run_cursor_script(
                {
                    "job_id": "JOB-TEST-BOOTSTRAP-DENIED",
                    "prompt": "Build a helper CLI with unit tests. Do not publish.",
                    "repo": r"C:\Development\Workspace\OratsUtil\new_tool",
                    "write": True,
                    "project_lifecycle": "create_new",
                },
                r"C:\neewa-missing\agent.exe",
                jobs,
                policy_path=policy,
                dry_run=True,
            )
            self.assertEqual(orats["status"], "BLOCKED")

    def _seed_implemented_project(self, target: Path) -> Path:
        target.mkdir(parents=True, exist_ok=True)
        (target / "sample.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        (target / "test_sample.py").write_text(
            "import unittest\nimport sample\n\n"
            "class SampleTests(unittest.TestCase):\n"
            "    def test_add(self):\n"
            "        self.assertEqual(sample.add(1, 2), 3)\n",
            encoding="utf-8",
        )
        sentinel = target / "keep-me.txt"
        sentinel.write_text("keep-me", encoding="utf-8")
        return sentinel

    def test_independent_validation_accepts_nonempty_implemented_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy, sandbox = self._isolated_policy(root / "policy-home")
            jobs = root / "jobs"
            jobs.mkdir()
            target = sandbox / "validated_tool"
            sentinel = self._seed_implemented_project(target)
            before = {path.name: path.read_text(encoding="utf-8") for path in target.iterdir() if path.is_file()}
            job = {
                "job_id": "JOB-TEST-VALIDATE-OK",
                "prompt": "Independently rerun tests. Do not publish.",
                "repo": str(target),
                "write": False,
                "project_lifecycle": "create_new",
                "execution_phase": "independent_validation",
                "workspace_root": str(sandbox),
                "implementation_completed": True,
                "implementation_repo": str(target.resolve()),
                "expected_paths": ["sample.py", "test_sample.py"],
                "test_command": "python -m unittest",
            }
            result = self._run_cursor_script(
                job,
                r"C:\neewa-missing\agent.exe",
                jobs,
                policy_path=policy,
            )
            self.assertEqual(result["status"], "COMPLETED", result)
            self.assertEqual(result.get("execution_phase"), "independent_validation")
            self.assertEqual((result.get("bootstrap") or {}).get("bootstrap_result"), "validation_existing")
            self.assertFalse((result.get("bootstrap") or {}).get("created"))
            self.assertTrue((result.get("independent_test") or {}).get("passed"), result)
            self.assertEqual((result.get("independent_test") or {}).get("command"), "python -m unittest")
            self.assertEqual((result.get("independent_test") or {}).get("exit_code"), 0)
            self.assertIs(result.get("cursor_started"), False)
            again = self._run_cursor_script(
                {**job, "job_id": "JOB-TEST-VALIDATE-REPEAT"},
                r"C:\neewa-missing\agent.exe",
                jobs,
                policy_path=policy,
            )
            self.assertEqual((again.get("bootstrap") or {}).get("bootstrap_result"), "validation_existing")
            self.assertFalse((again.get("bootstrap") or {}).get("created"))
            after = {path.name: path.read_text(encoding="utf-8") for path in target.iterdir() if path.is_file()}
            self.assertEqual(before, after)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep-me")

    def test_independent_validation_rejects_missing_mismatch_and_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy, sandbox = self._isolated_policy(root / "policy-home")
            jobs = root / "jobs"
            jobs.mkdir()
            target = sandbox / "validated_tool"
            self._seed_implemented_project(target)
            missing = sandbox / "never_made"
            missing_result = self._run_cursor_script(
                {
                    "job_id": "JOB-TEST-VALIDATE-MISSING",
                    "prompt": "Independently rerun tests. Do not publish.",
                    "repo": str(missing),
                    "write": False,
                    "project_lifecycle": "create_new",
                    "execution_phase": "independent_validation",
                    "workspace_root": str(sandbox),
                    "implementation_completed": True,
                    "implementation_repo": str(missing),
                    "expected_paths": ["sample.py"],
                },
                r"C:\neewa-missing\agent.exe",
                jobs,
                policy_path=policy,
            )
            self.assertEqual(missing_result["status"], "FAILED")
            self.assertEqual(missing_result.get("failure_class"), "MISSING_REPO")
            self.assertFalse(missing.exists())
            mismatch = self._run_cursor_script(
                {
                    "job_id": "JOB-TEST-VALIDATE-MISMATCH",
                    "prompt": "Independently rerun tests. Do not publish.",
                    "repo": str(target),
                    "write": False,
                    "project_lifecycle": "create_new",
                    "execution_phase": "independent_validation",
                    "workspace_root": str(sandbox),
                    "implementation_completed": True,
                    "implementation_repo": str(sandbox / "other_tool"),
                    "expected_paths": ["sample.py", "test_sample.py"],
                },
                r"C:\neewa-missing\agent.exe",
                jobs,
                policy_path=policy,
            )
            self.assertEqual(mismatch["status"], "FAILED")
            self.assertEqual(mismatch.get("failure_class"), "PROJECT_PATH_MISMATCH")
            incomplete = self._run_cursor_script(
                {
                    "job_id": "JOB-TEST-VALIDATE-INCOMPLETE",
                    "prompt": "Independently rerun tests. Do not publish.",
                    "repo": str(target),
                    "write": True,
                    "project_lifecycle": "create_new",
                    "execution_phase": "independent_validation",
                    "workspace_root": str(sandbox),
                    "implementation_completed": False,
                    "expected_paths": ["sample.py", "test_sample.py"],
                },
                r"C:\neewa-missing\agent.exe",
                jobs,
                policy_path=policy,
            )
            self.assertEqual(incomplete["status"], "FAILED")
            self.assertEqual(incomplete.get("failure_class"), "INCOMPLETE_IMPLEMENTATION")
            self.assertEqual((target / "keep-me.txt").read_text(encoding="utf-8"), "keep-me")


if __name__ == "__main__":
    unittest.main()
