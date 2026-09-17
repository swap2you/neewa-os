import json
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

    def _run_cursor_script(self, job: dict, cli_override: str, jobs_dir: Path) -> dict:
        job_path = jobs_dir / "job.json"
        job_path.write_text(json.dumps(job), encoding="utf-8")
        command = (
            f"$job = Get-Content -Raw -LiteralPath '{job_path}' | ConvertFrom-Json; "
            f"& '{WORKER / 'Invoke-NeewaCursorCall.ps1'}' -Job $job "
            f"-JobsDir '{jobs_dir}' -CliPathOverride '{cli_override}' | ConvertTo-Json -Depth 8"
        )
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertTrue(completed.stdout.strip(), completed.stderr)
        return json.loads(completed.stdout)

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


if __name__ == "__main__":
    unittest.main()
