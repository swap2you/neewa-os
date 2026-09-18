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
                    "authorized_remote": "https://github.com/swap2you/probe.git",
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

    def _live(self, number="1", sha=None):
        return {"number": number, "headRefOid": sha or self.sha, "state": "OPEN"}

    def _receipt(self, **kwargs):
        row = GIT.VAL.build_receipt(
            repository_identity=kwargs.get("repository_identity", "https://github.com/swap2you/probe.git"),
            pr_number=kwargs.get("pr_number", "1"),
            head_sha=kwargs.get("head_sha", self.sha),
            test_command=kwargs.get("test_command", "python -m unittest"),
            test_exit_code=kwargs.get("test_exit_code", 0),
            tests_passed=kwargs.get("tests_passed", True),
            executor=kwargs.get("executor", GIT.VAL.VALIDATOR_EXECUTOR),
            revoked=kwargs.get("revoked", False),
            approval_expires_at=kwargs.get("approval_expires_at"),
        )
        if "result" in kwargs:
            row["result"] = kwargs["result"]
            row["fingerprint"] = GIT.VAL.fingerprint(row)
        if kwargs.get("tamper"):
            row["result"] = "PASS"
        path = self.tmp / f"{row['receipt_id']}.json"
        path.write_text(json.dumps(row), encoding="utf-8")
        return path, row

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
                "_live_pr": self._live(),
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

    def test_merge_rejects_caller_pass_stale_fail_and_wrong_identity(self):
        caller_pass = GIT.dispatch(
            {
                "action": "git_merge_approved_pull_request",
                "repo": str(self.repo),
                "pr_number": "1",
                "independent_rerun": "PASS",
                "_live_pr": self._live(),
            }
        )
        self.assertEqual(caller_pass["failure_reason"], "INDEPENDENT_VALIDATION_REQUIRED")
        conflict = GIT.dispatch(
            {
                "action": "git_merge_approved_pull_request",
                "repo": str(self.repo),
                "pr_number": "1",
                "independent_rerun": "PASS",
                "independent_validation": "FAIL",
            }
        )
        self.assertEqual(conflict["failure_reason"], "CONFLICTING_VALIDATION_FIELDS")
        path, _ = self._receipt(tests_passed=False, test_exit_code=1)
        failed = GIT.dispatch(
            {
                "action": "git_merge_approved_pull_request",
                "repo": str(self.repo),
                "pr_number": "1",
                "validation_receipt_path": str(path),
                "repository_identity": "https://github.com/swap2you/probe.git",
                "_live_pr": self._live(),
            }
        )
        self.assertEqual(failed["failure_reason"], "INDEPENDENT_VALIDATION_FAILED")
        stale_path, _ = self._receipt(head_sha="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef")
        stale = GIT.dispatch(
            {
                "action": "git_merge_approved_pull_request",
                "repo": str(self.repo),
                "pr_number": "1",
                "validation_receipt_path": str(stale_path),
                "repository_identity": "https://github.com/swap2you/probe.git",
                "_live_pr": self._live(),
            }
        )
        self.assertEqual(stale["failure_reason"], "RECEIPT_SHA_MISMATCH")
        wrong_pr, _ = self._receipt(pr_number="99")
        mismatch = GIT.dispatch(
            {
                "action": "git_merge_approved_pull_request",
                "repo": str(self.repo),
                "pr_number": "1",
                "validation_receipt_path": str(wrong_pr),
                "repository_identity": "https://github.com/swap2you/probe.git",
                "_live_pr": self._live(),
            }
        )
        self.assertEqual(mismatch["failure_reason"], "RECEIPT_PR_MISMATCH")
        revoked_path, _ = self._receipt(revoked=True)
        revoked = GIT.dispatch(
            {
                "action": "git_merge_approved_pull_request",
                "repo": str(self.repo),
                "pr_number": "1",
                "validation_receipt_path": str(revoked_path),
                "repository_identity": "https://github.com/swap2you/probe.git",
                "_live_pr": self._live(),
            }
        )
        self.assertEqual(revoked["failure_reason"], "VALIDATION_REVOKED")
        sha_job = GIT.dispatch(
            {
                "action": "git_merge_approved_pull_request",
                "repo": str(self.repo),
                "pr_number": "1",
                "expected_local_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "_live_pr": self._live(),
            }
        )
        self.assertEqual(sha_job["failure_reason"], "PR_SHA_MISMATCH")
        inside = self.repo / "fake-receipt.json"
        good_path, row = self._receipt()
        inside.write_text(good_path.read_text(encoding="utf-8"), encoding="utf-8")
        in_repo = GIT.dispatch(
            {
                "action": "git_merge_approved_pull_request",
                "repo": str(self.repo),
                "pr_number": "1",
                "validation_receipt_path": str(inside),
                "repository_identity": "https://github.com/swap2you/probe.git",
                "_live_pr": self._live(),
            }
        )
        self.assertEqual(in_repo["failure_reason"], "RECEIPT_IN_REPOSITORY")


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
