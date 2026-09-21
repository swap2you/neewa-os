"""Receipt-backed A2 authorization: structured fields and hashes, not prompt text."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTH = SourceFileLoader(
    "neewa_a2_receipt_auth_test",
    str(ROOT / "12_SCRIPTS" / "neewa_a2_receipt_auth.py"),
).load_module()
SEM = SourceFileLoader(
    "neewa_action_semantics_a2_test",
    str(ROOT / "12_SCRIPTS" / "neewa_action_semantics.py"),
).load_module()
INBOX = SourceFileLoader(
    "windows_job_inbox_a2_test",
    str(ROOT / "12_SCRIPTS" / "windows_job_inbox.py"),
).load_module()
WORKER = ROOT / "16_WINDOWS_CLIENT" / "worker"

APPROVED_WORKSPACE = r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox\neewa-phase-b-cc03"
APPROVED_REMOTE = "https://github.com/swap2you/neewa-os.git"
APPROVED_COMMIT = "ed2f847f9cd55edd8d71ec0faa97e2849f4be42b"
APPROVED_TARGET = "ubuntu@neewa-core-01"
MISSION = "MISSION-20260920T114537Z-A86131C4"
PARENT = "JOB-20260920T114610Z-B77BD201-AUTO"
SCOPE = [
    "final pre-merge validation",
    "mark PR #11 ready and merge after passing checks",
    "capture exact merged main SHA",
    "create release and rollback targets",
    "deploy exact merged SHA",
    "atomically update /opt/neewa/neewa-os-current",
    "reload/restart approved NEEWA user services",
    "complete post-deployment and voice acceptance testing",
    "automatically roll back if verification fails",
]
APPROVAL_PATH = "/workspace/windows-jobs/autonomy/JOB-20260920T114610Z-B77BD201-AUTO-A2-approval.json"
BINDING_PATH = "/workspace/windows-jobs/autonomy/JOB-20260920T114610Z-B77BD201-AUTO-A2-binding-receipt.json"


def _dumps(payload: dict) -> bytes:
    return (json.dumps(payload, indent=2) + "\n").encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _approval(**overrides) -> dict:
    body = {
        "approval_type": "A2",
        "status": "GRANTED",
        "mission_id": MISSION,
        "parent_job_id": PARENT,
        "repository": APPROVED_REMOTE,
        "pr": 11,
        "validated_head": APPROVED_COMMIT,
        "target": APPROVED_TARGET,
        "authorized_scope": list(SCOPE),
        "constraints": [
            "CC16 remains immutable",
            "exactly one sequential successor",
            "do not expose credentials",
            "do not use Nous Portal or Qwen",
        ],
        "recorded_at": "2026-09-21T15:24:00Z",
        "source": "owner conversation",
        "workspace_path": APPROVED_WORKSPACE,
    }
    body.update(overrides)
    return body


def _binding(**overrides) -> dict:
    body = {
        "generated_at": "2026-09-21T15:46:45Z",
        "positive": {
            "approval_granted": True,
            "workspace_exact": True,
            "remote_exact": True,
            "head_exact": True,
            "pr_exact": True,
            "target_exact": True,
            "github_head_exact": True,
            "github_branch_expected": True,
            "github_base_main": True,
            "github_open": True,
        },
        "negative_workspace": {
            "approval_granted": True,
            "workspace_exact": False,
            "remote_exact": True,
            "head_exact": True,
            "pr_exact": True,
            "target_exact": True,
            "github_head_exact": True,
            "github_branch_expected": True,
            "github_base_main": True,
            "github_open": True,
        },
        "github": {
            "baseRefName": "main",
            "headRefName": "repair/phase-b-user-systemd-cc04",
            "headRefOid": APPROVED_COMMIT,
            "state": "OPEN",
        },
        "positive_pass": True,
        "negative_pass": True,
        "workspace_path": APPROVED_WORKSPACE,
    }
    body.update(overrides)
    return body


def _auth_object(approval_sha: str, binding_sha: str, **overrides) -> dict:
    body = {
        "approval_level": "A2",
        "approval_receipt_path": APPROVAL_PATH,
        "approval_receipt_sha256": approval_sha,
        "binding_receipt_path": BINDING_PATH,
        "binding_receipt_sha256": binding_sha,
        "mission_id": MISSION,
        "parent_id": PARENT,
        "repository_remote": APPROVED_REMOTE,
        "workspace_path": APPROVED_WORKSPACE,
        "pr_number": 11,
        "approved_commit": APPROVED_COMMIT,
        "deployment_target": APPROVED_TARGET,
        "authorized_actions": [
            "final pre-merge validation",
            "deploy exact merged SHA",
        ],
    }
    body.update(overrides)
    return body


def _job(auth: dict, **overrides) -> dict:
    body = {
        "job_id": "JOB-TEST-A2-VALID",
        "action": "cursor_call",
        "approval": "A2",
        "prompt": "Run final pre-merge validation in the approved workspace.",
        "repo": APPROVED_WORKSPACE,
        "workspace_path": APPROVED_WORKSPACE,
        "write": True,
        "authorization": auth,
    }
    body.update(overrides)
    return body


class ReceiptStore:
    def __init__(self, approval: dict, binding: dict) -> None:
        self.approval_raw = _dumps(approval)
        self.binding_raw = _dumps(binding)
        self.approval_sha = _sha(self.approval_raw)
        self.binding_sha = _sha(self.binding_raw)
        self.missing = False
        self.disable_ssh = False

    def fetch(self, path: str) -> bytes:
        if self.disable_ssh:
            raise AUTH.ReceiptFetchError("MISSING_SSH", "disabled")
        if self.missing:
            raise AUTH.ReceiptFetchError("MISSING_RECEIPT", path)
        mapped = AUTH.map_receipt_path(path)
        if path.endswith("approval.json") or mapped.endswith("approval.json"):
            return self.approval_raw
        if path.endswith("binding-receipt.json") or mapped.endswith("binding-receipt.json"):
            return self.binding_raw
        raise AUTH.ReceiptFetchError("MISSING_RECEIPT", path)


class A2ReceiptAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name) / "authorizations"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _decide(self, store: ReceiptStore, job: dict):
        return AUTH.authorize_job(job, fetch=store.fetch, cache_dir=self.cache)

    def test_exact_valid_authorization_accepted(self):
        store = ReceiptStore(_approval(), _binding())
        job = _job(_auth_object(store.approval_sha, store.binding_sha))
        result = self._decide(store, job)
        self.assertTrue(result["allowed"], result)
        self.assertEqual(result["decision"], AUTH.AUTHORIZED)
        self.assertEqual(result["reason"], "A2_RECEIPT_AUTHORIZED")
        self.assertEqual(result["approval_sha256"], store.approval_sha)
        self.assertEqual(result["binding_sha256"], store.binding_sha)
        self.assertFalse(result.get("replay"))

    def test_altered_workspace_rejected(self):
        store = ReceiptStore(_approval(), _binding())
        other = r"C:\Development\Workspace\NEEWA-OS"
        auth = _auth_object(store.approval_sha, store.binding_sha, workspace_path=other)
        result = self._decide(store, _job(auth, repo=other, workspace_path=other))
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "ALTERED_WORKSPACE")

    def test_altered_repository_rejected(self):
        store = ReceiptStore(_approval(), _binding())
        auth = _auth_object(
            store.approval_sha,
            store.binding_sha,
            repository_remote="https://github.com/evil/neewa-os.git",
        )
        result = self._decide(store, _job(auth))
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "ALTERED_REPOSITORY")

    def test_altered_commit_rejected(self):
        store = ReceiptStore(_approval(), _binding())
        auth = _auth_object(
            store.approval_sha,
            store.binding_sha,
            approved_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )
        result = self._decide(store, _job(auth))
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "ALTERED_COMMIT")

    def test_altered_pr_rejected(self):
        store = ReceiptStore(_approval(), _binding())
        auth = _auth_object(store.approval_sha, store.binding_sha, pr_number=99)
        result = self._decide(store, _job(auth))
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "ALTERED_PR")

    def test_altered_host_rejected(self):
        store = ReceiptStore(_approval(), _binding())
        auth = _auth_object(
            store.approval_sha,
            store.binding_sha,
            deployment_target="ubuntu@evil-host",
        )
        result = self._decide(store, _job(auth))
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "ALTERED_HOST")

    def test_altered_mission_and_parent_rejected(self):
        store = ReceiptStore(_approval(), _binding())
        mission = self._decide(
            store,
            _job(_auth_object(store.approval_sha, store.binding_sha, mission_id="MISSION-OTHER")),
        )
        parent = self._decide(
            store,
            _job(_auth_object(store.approval_sha, store.binding_sha, parent_id="JOB-OTHER")),
        )
        self.assertEqual(mission["reason"], "ALTERED_MISSION")
        self.assertEqual(parent["reason"], "ALTERED_PARENT")
        self.assertFalse(mission["allowed"])
        self.assertFalse(parent["allowed"])

    def test_broader_requested_scope_rejected(self):
        store = ReceiptStore(_approval(), _binding())
        auth = _auth_object(
            store.approval_sha,
            store.binding_sha,
            authorized_actions=["deploy exact merged SHA", "force_push"],
        )
        result = self._decide(store, _job(auth))
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "SCOPE_EXCEEDED")

    def test_receipt_hash_mismatch_rejected(self):
        store = ReceiptStore(_approval(), _binding())
        auth = _auth_object(
            "0" * 64,
            store.binding_sha,
        )
        result = self._decide(store, _job(auth))
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "HASH_MISMATCH")

    def test_missing_ssh_and_missing_receipt_rejected(self):
        store = ReceiptStore(_approval(), _binding())
        auth = _auth_object(store.approval_sha, store.binding_sha)
        store.disable_ssh = True
        missing_ssh = self._decide(store, _job(auth, job_id="JOB-TEST-A2-SSH"))
        self.assertFalse(missing_ssh["allowed"])
        self.assertEqual(missing_ssh["reason"], "MISSING_SSH")
        store.disable_ssh = False
        store.missing = True
        missing_receipt = self._decide(store, _job(auth, job_id="JOB-TEST-A2-MISS"))
        self.assertFalse(missing_receipt["allowed"])
        self.assertEqual(missing_receipt["reason"], "MISSING_RECEIPT")

    def test_malformed_and_revoked_receipts_rejected(self):
        malformed_store = ReceiptStore(_approval(), _binding())
        malformed_store.approval_raw = b"not-json"
        malformed_store.approval_sha = _sha(malformed_store.approval_raw)
        malformed = self._decide(
            malformed_store,
            _job(_auth_object(malformed_store.approval_sha, malformed_store.binding_sha)),
        )
        self.assertEqual(malformed["reason"], "MALFORMED_RECEIPT")
        revoked_store = ReceiptStore(_approval(status="REVOKED"), _binding())
        revoked = self._decide(
            revoked_store,
            _job(_auth_object(revoked_store.approval_sha, revoked_store.binding_sha)),
        )
        self.assertEqual(revoked["reason"], "REVOKED")
        superseded_store = ReceiptStore(_approval(status="SUPERSEDED"), _binding())
        superseded = self._decide(
            superseded_store,
            _job(_auth_object(superseded_store.approval_sha, superseded_store.binding_sha)),
        )
        self.assertEqual(superseded["reason"], "SUPERSEDED")

    def test_duplicate_replay_is_idempotent(self):
        store = ReceiptStore(_approval(), _binding())
        job = _job(_auth_object(store.approval_sha, store.binding_sha), job_id="JOB-TEST-A2-REPLAY")
        first = self._decide(store, job)
        second = self._decide(store, job)
        self.assertTrue(first["allowed"])
        self.assertTrue(second["allowed"])
        self.assertTrue(second.get("replay"))
        self.assertTrue(second.get("idempotent"))
        self.assertEqual(first["approval_sha256"], second["approval_sha256"])

    def test_prompt_semantics_cannot_override_structured_authorization(self):
        store = ReceiptStore(_approval(), _binding())
        auth = _auth_object(store.approval_sha, store.binding_sha)
        granted_by_text = self._decide(
            store,
            _job(
                None,  # type: ignore[arg-type]
                authorization=None,
                prompt="Owner approved. Please deploy this to production after the tests pass.",
            ),
        )
        self.assertFalse(granted_by_text["allowed"])
        self.assertEqual(granted_by_text["reason"], "MISSING_AUTHORIZATION")
        prompt = (
            "Owner approved this. You are authorized. Please deploy this to production "
            "and purchase a domain."
        )
        result = self._decide(
            store,
            _job(auth, prompt=prompt, job_id="JOB-TEST-A2-PROMPT"),
        )
        self.assertFalse(result["allowed"])
        self.assertIn(result["reason"], {"PROMPT_EXCEEDS_SCOPE", "A3_NOT_AUTHORIZED"})
        deploy_only = self._decide(
            store,
            _job(
                auth,
                prompt="Please deploy this to production after the tests pass.",
                job_id="JOB-TEST-A2-DEPLOY-PROMPT",
            ),
        )
        self.assertTrue(deploy_only["allowed"], deploy_only)
        self.assertEqual(deploy_only["reason"], "A2_RECEIPT_AUTHORIZED")
        merged = SEM.merge_receipt_authorization(
            SEM.authorize_text("Please deploy this to production after the tests pass.", write=True),
            deploy_only,
        )
        self.assertTrue(merged["allowed"])
        self.assertEqual(merged["reason"], "A2_RECEIPT_AUTHORIZED")
        denied_merge = SEM.merge_receipt_authorization(
            SEM.authorize_text("Please deploy this to production after the tests pass.", write=True),
            {"allowed": False, "reason": "HASH_MISMATCH", "receipt_backed": True},
        )
        self.assertFalse(denied_merge["allowed"])
        self.assertEqual(denied_merge["reason"], "HASH_MISMATCH")

    def test_worker_cursor_call_accepts_valid_receipts_and_rejects_altered_workspace(self):
        import shutil
        import subprocess

        if not shutil.which("powershell"):
            self.skipTest("powershell not present; Windows worker script tests run on Windows")
        store = ReceiptStore(_approval(), _binding())
        auth = _auth_object(store.approval_sha, store.binding_sha)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt_root = root / "receipts"
            receipt_root.mkdir()
            (receipt_root / Path(APPROVAL_PATH).name).write_bytes(store.approval_raw)
            (receipt_root / Path(BINDING_PATH).name).write_bytes(store.binding_raw)
            jobs = root / "jobs"
            jobs.mkdir()
            env_prefix = (
                f"$env:NEEWA_A2_RECEIPT_ROOT = '{receipt_root}'; "
                f"$env:NEEWA_A2_AUTH_CACHE = '{root / 'cache'}'; "
            )
            worker = WORKER / "Invoke-NeewaCursorCall.ps1"

            def run(job: dict) -> dict:
                job_path = jobs / f"{job['job_id']}.json"
                job_path.write_text(json.dumps(job), encoding="utf-8")
                command = (
                    env_prefix
                    + f"$job = Get-Content -Raw -LiteralPath '{job_path}' | ConvertFrom-Json; "
                    + f"& '{worker}' -Job $job -JobsDir '{jobs}' "
                    + r"-CliPathOverride 'C:\neewa-missing\agent.exe' -DryRun | ConvertTo-Json -Depth 8"
                )
                completed = subprocess.run(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertTrue(completed.stdout.strip(), completed.stderr)
                return json.loads(completed.stdout)

            accepted = run(
                _job(
                    auth,
                    prompt="Please deploy this to production after the tests pass.",
                    job_id="JOB-TEST-A2-PS-OK",
                )
            )
            self.assertEqual(accepted["status"], "COMPLETED", accepted)
            self.assertTrue((accepted.get("authorization") or {}).get("allowed"), accepted)
            self.assertEqual((accepted.get("authorization") or {}).get("reason"), "A2_RECEIPT_AUTHORIZED")
            other = r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox\other"
            denied = run(
                _job(
                    _auth_object(store.approval_sha, store.binding_sha, workspace_path=other),
                    repo=other,
                    workspace_path=other,
                    prompt="Please deploy this to production after the tests pass.",
                    job_id="JOB-TEST-A2-PS-WS",
                )
            )
            self.assertEqual(denied["status"], "BLOCKED")
            self.assertIn("ALTERED_WORKSPACE", denied.get("reason") or "")
            repo_denied = run(
                _job(
                    _auth_object(
                        store.approval_sha,
                        store.binding_sha,
                        repository_remote="https://github.com/evil/neewa-os.git",
                    ),
                    prompt="Please deploy this to production after the tests pass.",
                    job_id="JOB-TEST-A2-PS-REPO",
                )
            )
            self.assertEqual(repo_denied["status"], "BLOCKED")
            self.assertIn("ALTERED_REPOSITORY", repo_denied.get("reason") or "")
            commit_denied = run(
                _job(
                    _auth_object(
                        store.approval_sha,
                        store.binding_sha,
                        approved_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    ),
                    prompt="Please deploy this to production after the tests pass.",
                    job_id="JOB-TEST-A2-PS-COMMIT",
                )
            )
            self.assertEqual(commit_denied["status"], "BLOCKED")
            self.assertIn("ALTERED_COMMIT", commit_denied.get("reason") or "")
            host_denied = run(
                _job(
                    _auth_object(
                        store.approval_sha,
                        store.binding_sha,
                        deployment_target="ubuntu@evil-host",
                    ),
                    prompt="Please deploy this to production after the tests pass.",
                    job_id="JOB-TEST-A2-PS-HOST",
                )
            )
            self.assertEqual(host_denied["status"], "BLOCKED")
            self.assertIn("ALTERED_HOST", host_denied.get("reason") or "")

    def test_a2_cannot_exceed_authorized_action_set(self):
        store = ReceiptStore(_approval(), _binding())
        auth = _auth_object(
            store.approval_sha,
            store.binding_sha,
            authorized_actions=["final pre-merge validation"],
        )
        result = self._decide(
            store,
            _job(
                auth,
                prompt="Please deploy this to production after the tests pass.",
                job_id="JOB-TEST-A2-EXCEED",
            ),
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "PROMPT_EXCEEDS_SCOPE")
        financial = self._decide(
            store,
            _job(
                _auth_object(store.approval_sha, store.binding_sha),
                prompt="Place a live trade after deploy.",
                job_id="JOB-TEST-A2-A3",
            ),
        )
        self.assertFalse(financial["allowed"])
        self.assertEqual(financial["reason"], "A3_NOT_AUTHORIZED")

    def test_live_shaped_receipts_without_workspace_field_bind_job_workspace(self):
        approval = _approval()
        approval.pop("workspace_path")
        binding = _binding()
        binding.pop("workspace_path")
        store = ReceiptStore(approval, binding)
        result = self._decide(store, _job(_auth_object(store.approval_sha, store.binding_sha)))
        self.assertTrue(result["allowed"], result)
        other = r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox\other"
        altered = self._decide(
            store,
            _job(
                _auth_object(store.approval_sha, store.binding_sha),
                repo=other,
                workspace_path=other,
                job_id="JOB-TEST-A2-LIVE-WS",
            ),
        )
        self.assertFalse(altered["allowed"])
        self.assertEqual(altered["reason"], "ALTERED_WORKSPACE")

    def test_inbox_accepts_structured_a2_without_standing_registry(self):
        store = ReceiptStore(_approval(), _binding())
        auth = _auth_object(store.approval_sha, store.binding_sha)
        with tempfile.TemporaryDirectory() as tmp:
            path = INBOX.enqueue(
                "JOB-TEST-A2-INBOX",
                "cursor_call",
                "A2",
                Path(tmp),
                extra={
                    "repo": APPROVED_WORKSPACE,
                    "prompt": "Run final pre-merge validation.",
                    "authorization": auth,
                },
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["approval"], "A2")
            self.assertEqual(payload["authorization"]["approved_commit"], APPROVED_COMMIT)
            with self.assertRaises(ValueError):
                INBOX.enqueue(
                    "JOB-TEST-A2-INBOX-NOAUTH",
                    "cursor_call",
                    "A2",
                    Path(tmp),
                    extra={"repo": APPROVED_WORKSPACE, "prompt": "owner approved deploy"},
                )

    def test_worker_module_copy_matches_scripts(self):
        scripts = (ROOT / "12_SCRIPTS" / "neewa_a2_receipt_auth.py").read_bytes()
        worker = (WORKER / "neewa_a2_receipt_auth.py").read_bytes()
        self.assertEqual(_sha(scripts), _sha(worker))
        installer = (WORKER / "Install-NeewaWindowsWorker.ps1").read_text(encoding="utf-8")
        self.assertIn(".py", installer)
        self.assertIn("neewa_a2_receipt_auth.py", installer)

    def test_no_wildcard_authorization_in_source(self):
        src = (ROOT / "12_SCRIPTS" / "neewa_a2_receipt_auth.py").read_text(encoding="utf-8")
        self.assertNotIn("WILDCARD", src)
        self.assertNotIn("approval_level = '*'", src)
        policy = json.loads((WORKER / "cursor-call-policy.json").read_text(encoding="utf-8"))
        self.assertFalse(policy.get("a2_receipt_authorization", {}).get("wildcard_authorization", True))
        self.assertTrue(policy["a2_receipt_authorization"]["prompt_text_is_not_authorization"])


if __name__ == "__main__":
    unittest.main()
