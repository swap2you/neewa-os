import json
import os
import subprocess
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GIT = SourceFileLoader("neewa_git_ops_test", str(ROOT / "12_SCRIPTS" / "neewa_git_ops.py")).load_module()
AUTH = SourceFileLoader("neewa_authorization_git_test", str(ROOT / "12_SCRIPTS" / "neewa_authorization.py")).load_module()


def git(args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True, timeout=30)


class GovernedGitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "probe"
        self.repo.mkdir()
        git(["init"], cwd=self.repo)
        git(["config", "user.email", "git-ops-test@local"], cwd=self.repo)
        git(["config", "user.name", "git ops test"], cwd=self.repo)
        git(["config", "commit.gpgsign", "false"], cwd=self.repo)
        (self.repo / "src").mkdir()
        (self.repo / "src" / "hello.py").write_text("VALUE = 1\n", encoding="utf-8")
        git(["add", "src/hello.py"], cwd=self.repo)
        git(["commit", "-m", "init"], cwd=self.repo)
        self.sha = git(["rev-parse", "HEAD"], cwd=self.repo).stdout.strip()
        registry = {
            "denied_name_equals": ["OratsUtil"],
            "repositories": [
                {
                    "id": "probe",
                    "authorized_local_path": str(self.repo),
                    "authorized_remote": "",
                    "permitted_feature_branch_prefixes": ["feat/", "fix/"],
                    "protected_branches": ["main"],
                    "standing_operations": [
                        "git_fetch",
                        "git_commit_scoped_changes",
                        "git_push_feature_branch",
                        "git_verify_remote_state",
                        "git_create_feature_branch",
                        "git_merge_approved_pull_request",
                    ],
                    "always_denied_operations": ["force_push"],
                }
            ],
        }
        self.reg = self.tmp / "registry.json"
        self.reg.write_text(json.dumps(registry), encoding="utf-8")
        os.environ["NEEWA_REPO_AUTH_PATH"] = str(self.reg)

    def tearDown(self):
        os.environ.pop("NEEWA_REPO_AUTH_PATH", None)

    def test_commit_scoped_changes_and_reject_secrets_and_traversal(self):
        (self.repo / "src" / "hello.py").write_text("VALUE = 2\n", encoding="utf-8")
        ok = GIT.dispatch(
            {
                "action": "git_commit_scoped_changes",
                "job_id": "GIT-TEST-COMMIT",
                "repo": str(self.repo),
                "files": ["src/hello.py"],
                "message": "test: scoped commit",
                "source_branch": "feat/probe",
            }
        )
        self.assertEqual(ok["status"], "COMPLETED", ok)
        self.assertNotEqual(ok["destination_sha"], self.sha)
        secret = GIT.dispatch(
            {
                "action": "git_commit_scoped_changes",
                "repo": str(self.repo),
                "files": [".env"],
            }
        )
        self.assertEqual(secret["status"], "BLOCKED")
        self.assertEqual(secret["failure_reason"], "SECRET_FILE")
        traversal = GIT.dispatch(
            {
                "action": "git_commit_scoped_changes",
                "repo": str(self.repo),
                "files": ["../secret.py"],
            }
        )
        self.assertEqual(traversal["status"], "BLOCKED")

    def test_force_flags_are_rejected(self):
        with self.assertRaises(ValueError):
            GIT.run_git(["push", "--force", "origin", "HEAD"], self.repo)

    def test_push_to_main_is_blocked_by_authorization(self):
        blocked = GIT.dispatch(
            {
                "action": "git_push_feature_branch",
                "repo": str(self.repo),
                "source_branch": "main",
                "destination_branch": "main",
                "expected_local_sha": self.sha,
            }
        )
        self.assertEqual(blocked["status"], "BLOCKED")

    def test_merge_rejects_implementer_claimed(self):
        blocked = GIT.dispatch(
            {
                "action": "git_merge_approved_pull_request",
                "repo": str(self.repo),
                "pr_number": "1",
                "independent_rerun": "IMPLEMENTER_CLAIMED",
            }
        )
        self.assertEqual(blocked["status"], "BLOCKED")
        self.assertEqual(blocked["failure_reason"], "IMPLEMENTER_CLAIMED_INSUFFICIENT")

    def test_merge_rejects_claimed_alias_and_missing_validation(self):
        alias = GIT.dispatch(
            {
                "action": "git_merge_approved_pull_request",
                "repo": str(self.repo),
                "pr_number": "1",
                "independent_validation": "IMPLEMENTER_CLAIMED",
            }
        )
        self.assertEqual(alias["status"], "BLOCKED")
        self.assertEqual(alias["failure_reason"], "IMPLEMENTER_CLAIMED_INSUFFICIENT")
        missing = GIT.dispatch(
            {
                "action": "git_merge_approved_pull_request",
                "repo": str(self.repo),
                "pr_number": "1",
            }
        )
        self.assertEqual(missing["status"], "BLOCKED")
        self.assertEqual(missing["failure_reason"], "INDEPENDENT_VALIDATION_REQUIRED")
        hold = GIT.dispatch(
            {
                "action": "git_merge_approved_pull_request",
                "repo": str(self.repo),
                "pr_number": "1",
                "independent_rerun": "PASS",
                "council": {"roles": {"RELEASE_CONTROLLER": {"decision": "HOLD_FOR_INDEPENDENT_VALIDATION"}}},
            }
        )
        self.assertEqual(hold["status"], "BLOCKED")
        self.assertEqual(hold["failure_reason"], "COUNCIL_HOLD")

    def test_receipt_has_required_fields(self):
        row = GIT.receipt(operation="git_fetch", status="COMPLETED", repository=str(self.repo))
        for key in (
            "operation_id",
            "mission_id",
            "repository",
            "operation",
            "authorization",
            "executor",
            "source_sha",
            "destination_sha",
            "status",
            "created_at",
            "verification",
            "failure_reason",
        ):
            self.assertIn(key, row)
