import json
import os
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTH = SourceFileLoader("neewa_authorization_test", str(ROOT / "12_SCRIPTS" / "neewa_authorization.py")).load_module()


class AuthorizationTests(unittest.TestCase):
    def test_standing_push_is_authorized_for_registered_feature_branch(self):
        gate = AUTH.decide(
            operation="git_push_feature_branch",
            repo=r"C:\Development\Workspace\NEEWA-OS",
            source_branch="feat/scoped-repair-workspace",
            destination_branch="feat/scoped-repair-workspace",
            expected_local_sha="f0f6552e9f22cc7e6cdf32919030e4a3a26e628e",
        )
        self.assertEqual(gate["decision"], AUTH.AUTHORIZED)
        self.assertEqual(gate["risk"], "A2")
        self.assertTrue(gate["standing"])

    def test_job_json_owner_decision_does_not_grant_push(self):
        gate = AUTH.decide(
            operation="git_push_feature_branch",
            repo=r"C:\Development\Workspace\OratsUtil",
            source_branch="feat/x",
            owner_authorization="approved",
        )
        self.assertEqual(gate["decision"], AUTH.DENIED)
        self.assertEqual(gate["reason"], "DENIED_REPO")

    def test_force_push_denied(self):
        gate = AUTH.decide(
            operation="force_push",
            repo=r"C:\Development\Workspace\NEEWA-OS",
            source_branch="feat/scoped-repair-workspace",
        )
        self.assertEqual(gate["decision"], AUTH.DENIED)

    def test_protected_main_push_denied(self):
        gate = AUTH.decide(
            operation="git_push_feature_branch",
            repo=r"C:\Development\Workspace\NEEWA-OS",
            source_branch="main",
            destination_branch="main",
        )
        self.assertEqual(gate["decision"], AUTH.DENIED)
        self.assertEqual(gate["reason"], "PROTECTED_BRANCH")

    def test_unregistered_repo_denied(self):
        gate = AUTH.decide(
            operation="git_push_feature_branch",
            repo=r"C:\Temp\random-app",
            source_branch="feat/x",
        )
        self.assertEqual(gate["decision"], AUTH.DENIED)
        self.assertEqual(gate["reason"], "UNREGISTERED_REPOSITORY")

    def test_production_deploy_requires_policy(self):
        gate = AUTH.decide(
            operation="deploy_production",
            repo=r"C:\Development\Workspace\NEEWA-OS",
        )
        self.assertEqual(gate["decision"], AUTH.APPROVAL_REQUIRED)

    def test_inbox_enqueues_standing_a2_git_push(self):
        inbox = SourceFileLoader("windows_job_inbox_auth", str(ROOT / "12_SCRIPTS" / "windows_job_inbox.py")).load_module()
        with tempfile.TemporaryDirectory() as tmp:
            path = inbox.enqueue(
                "JOB-TEST-GIT-PUSH",
                "git_push_feature_branch",
                "A2",
                Path(tmp),
                extra={
                    "repo": r"C:\Development\Workspace\NEEWA-OS",
                    "source_branch": "feat/scoped-repair-workspace",
                    "destination_branch": "feat/scoped-repair-workspace",
                    "expected_local_sha": "f0f6552e9f22cc7e6cdf32919030e4a3a26e628e",
                },
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["action"], "git_push_feature_branch")
            with self.assertRaises(ValueError):
                inbox.enqueue("JOB-TEST-GIT-A3", "cursor_call", "A3", Path(tmp))
