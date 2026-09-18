import json
import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "16_WINDOWS_CLIENT" / "worker"
SCRIPTS = ROOT / "12_SCRIPTS"
MOD = SourceFileLoader("neewa_scoped_repair", str(SCRIPTS / "neewa_scoped_repair.py")).load_module()
ORCH = SourceFileLoader("neewa_orchestrate_scoped", str(SCRIPTS / "neewa_orchestrate.py")).load_module()
INBOX = SourceFileLoader("windows_job_inbox_scoped", str(SCRIPTS / "windows_job_inbox.py")).load_module()


def git(args, cwd):
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )


def init_repo(path: Path, files: dict[str, str], name="probe") -> str:
    path.mkdir(parents=True, exist_ok=True)
    git(["init"], cwd=path)
    git(["config", "user.email", "scoped-repair-test@local"], cwd=path)
    git(["config", "user.name", "scoped repair test"], cwd=path)
    git(["config", "commit.gpgsign", "false"], cwd=path)
    for rel, content in files.items():
        dest = path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    git(["add", "-A"], cwd=path)
    git(["commit", "-m", f"init {name}"], cwd=path)
    return git(["rev-parse", "HEAD"], cwd=path).stdout.strip()


class ScopedRepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="neewa-scoped-"))
        self.personal = self.tmp / "workspace"
        self.repair_root = self.tmp / "scoped-repair"
        self.personal.mkdir(parents=True)
        self.repair_root.mkdir(parents=True)
        self.env_stack = (
            os.environ.get("NEEWA_SCOPED_REPAIR_ROOT"),
            os.environ.get("NEEWA_SCOPED_REPAIR_PERSONAL_ROOT"),
        )
        os.environ["NEEWA_SCOPED_REPAIR_ROOT"] = str(self.repair_root)
        os.environ["NEEWA_SCOPED_REPAIR_PERSONAL_ROOT"] = str(self.personal)

    def tearDown(self):
        root, personal = self.env_stack
        if root is None:
            os.environ.pop("NEEWA_SCOPED_REPAIR_ROOT", None)
        else:
            os.environ["NEEWA_SCOPED_REPAIR_ROOT"] = root
        if personal is None:
            os.environ.pop("NEEWA_SCOPED_REPAIR_PERSONAL_ROOT", None)
        else:
            os.environ["NEEWA_SCOPED_REPAIR_PERSONAL_ROOT"] = personal
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _repo(self, name="hello-probe", files=None):
        files = files or {
            "src/hello.py": "VALUE = 1\n",
            "tests/test_hello.py": "from src.hello import VALUE\n\ndef test_value():\n    assert VALUE == 1\n",
        }
        repo = self.personal / name
        sha = init_repo(repo, files, name)
        return repo, sha, files

    def _create(self, repo, sha, files, **kwargs):
        return MOD.create_scoped_repair_workspace(
            repo=str(repo),
            files=files,
            expected_base_sha=sha,
            repair_root=self.repair_root,
            **kwargs,
        )

    def test_01_valid_authorized_scope_creates_workspace(self):
        repo, sha, files = self._repo()
        result = self._create(repo, sha, list(files), repo_id="hello-probe")
        self.assertEqual(result["status"], "COMPLETED", result)
        self.assertTrue(Path(result["workspace_path"]).is_dir())
        self.assertTrue((Path(result["workspace_path"]) / "src" / "hello.py").is_file())
        self.assertTrue((Path(result["workspace_path"]) / "tests" / "test_hello.py").is_file())
        self.assertEqual(result["base_sha"], sha)
        self.assertTrue((Path(result["workspace_path"]) / ".git").exists())

    def test_02_unauthorized_repository_is_rejected(self):
        denied = self.personal / "OratsUtil"
        sha = init_repo(denied, {"src/hello.py": "x = 1\n"}, "denied")
        result = self._create(denied, sha, ["src/hello.py"], repo_id="OratsUtil")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("DENIED", result["failure_reason"])
        outside = self.tmp / "outside-repo"
        sha2 = init_repo(outside, {"src/hello.py": "x = 1\n"}, "outside")
        result2 = self._create(outside, sha2, ["src/hello.py"], repo_id="outside-repo")
        self.assertEqual(result2["status"], "BLOCKED")
        self.assertIn("UNAPPROVED_PATH", result2["failure_reason"])

    def test_03_parent_directory_traversal_is_rejected(self):
        repo, sha, _ = self._repo()
        result = self._create(repo, sha, ["../secret.py"], repo_id="hello-probe")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("PATH_TRAVERSAL", result["failure_reason"])

    def test_04_absolute_or_out_of_root_source_path_is_rejected(self):
        repo, sha, _ = self._repo()
        result = self._create(repo, sha, [str(self.tmp / "secret.py")], repo_id="hello-probe")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("ABSOLUTE_PATH", result["failure_reason"])

    def test_05_symlink_or_junction_escape_is_rejected(self):
        repo, sha, _ = self._repo()
        outside = self.tmp / "outside-secret"
        outside.mkdir()
        (outside / "secret.py").write_text("secret = 1\n", encoding="utf-8")
        escape = repo / "escape"
        try:
            os.symlink(outside, escape, target_is_directory=True)
        except OSError:
            if os.name == "nt":
                completed = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(escape), str(outside)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if completed.returncode != 0:
                    self.skipTest("symlink/junction creation is not permitted")
            else:
                self.skipTest("symlink creation is not permitted")
        result = self._create(repo, sha, ["escape/secret.py"], repo_id="hello-probe")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("SYMLINK_ESCAPE", result["failure_reason"])

    def test_06_invalid_destination_is_rejected(self):
        repo, sha, files = self._repo()
        result = MOD.create_scoped_repair_workspace(
            repo=str(repo),
            files=list(files),
            expected_base_sha=sha,
            destination=str(self.tmp / "evil"),
            repair_root=self.repair_root,
            repo_id="hello-probe",
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("INVALID_DESTINATION", result["failure_reason"])

    def test_07_incorrect_or_stale_base_sha_is_rejected(self):
        repo, sha, files = self._repo()
        result = self._create(repo, "0" * 40, list(files), repo_id="hello-probe")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("STALE_OR_UNKNOWN_BASE_SHA", result["failure_reason"])
        (repo / "src" / "hello.py").write_text("VALUE = 2\n", encoding="utf-8")
        git(["add", "src/hello.py"], cwd=repo)
        git(["commit", "-m", "move head"], cwd=repo)
        stale = self._create(repo, sha, list(files), repo_id="hello-probe")
        self.assertEqual(stale["status"], "BLOCKED")
        self.assertIn("STALE_OR_UNKNOWN_BASE_SHA", stale["failure_reason"])

    def test_08_workspace_creation_does_not_modify_authoritative_repo(self):
        repo, sha, files = self._repo()
        before_status = git(["status", "--porcelain"], cwd=repo).stdout
        before_head = git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()
        result = self._create(repo, sha, list(files), repo_id="hello-probe")
        self.assertEqual(result["status"], "COMPLETED", result)
        after_status = git(["status", "--porcelain"], cwd=repo).stdout
        after_head = git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()
        self.assertEqual(before_status, after_status)
        self.assertEqual(before_head, after_head)

    def test_09_operation_returns_complete_structured_receipt(self):
        repo, sha, files = self._repo()
        result = self._create(repo, sha, list(files), repo_id="hello-probe", operation_id="SCOPED-TEST-RECEIPT")
        self.assertEqual(result["status"], "COMPLETED")
        for key in (
            "operation_id",
            "status",
            "repository_id",
            "authoritative_repo",
            "workspace_path",
            "base_sha",
            "selected_files",
            "created_at",
            "authorization",
            "failure_reason",
        ):
            self.assertIn(key, result)
        self.assertEqual(result["operation_id"], "SCOPED-TEST-RECEIPT")
        self.assertEqual(result["repository_id"], "hello-probe")
        self.assertEqual(result["failure_reason"], None)
        self.assertTrue(result["authorization"]["allowed"])
        blob = json.dumps(result)
        self.assertNotIn("CURSOR_API_KEY", blob)
        self.assertNotIn("BEGIN PRIVATE KEY", blob)

    def test_10_cursor_dispatcher_accepts_valid_scoped_workspace_receipt(self):
        repo, sha, files = self._repo()
        created = self._create(repo, sha, list(files), repo_id="hello-probe")
        gate = MOD.authorize_cursor_workspace(created["workspace_path"], repair_root=self.repair_root)
        self.assertTrue(gate["allowed"], gate)
        self.assertEqual(gate["reason"], "SCOPED_RECEIPT")
        dispatched = MOD.dispatch(
            {
                "action": "authorize_scoped_cursor_workspace",
                "job_id": "JOB-TEST-SCOPED-AUTH",
                "repo": created["workspace_path"],
            },
            repair_root=self.repair_root,
        )
        self.assertEqual(dispatched["status"], "COMPLETED")

    def test_11_cursor_dispatcher_rejects_forged_or_invalid_workspace_reference(self):
        repo, sha, files = self._repo()
        created = self._create(repo, sha, list(files), repo_id="hello-probe")
        forged = self.repair_root / "forged-workspace"
        forged.mkdir()
        (forged / MOD.RECEIPT_NAME).write_text(
            json.dumps(
                {
                    "operation_id": created["operation_id"],
                    "workspace_path": str(forged),
                    "status": "COMPLETED",
                }
            ),
            encoding="utf-8",
        )
        gate = MOD.authorize_cursor_workspace(str(forged), repair_root=self.repair_root)
        self.assertFalse(gate["allowed"])
        self.assertIn(gate["reason"], {"WORKSPACE_RECEIPT_MISMATCH", "MISSING_TRUSTED_RECEIPT"})
        missing = MOD.authorize_cursor_workspace(str(self.repair_root / "no-such"), repair_root=self.repair_root)
        self.assertFalse(missing["allowed"])
        expired = json.loads((self.repair_root / "receipts" / f"{created['operation_id']}.json").read_text(encoding="utf-8"))
        expired["created_at"] = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        (self.repair_root / "receipts" / f"{created['operation_id']}.json").write_text(json.dumps(expired), encoding="utf-8")
        old = MOD.authorize_cursor_workspace(created["workspace_path"], repair_root=self.repair_root)
        self.assertFalse(old["allowed"])
        self.assertEqual(old["reason"], "RECEIPT_EXPIRED")

    def test_12_unexpected_changed_files_are_rejected_during_patch_review(self):
        repo, sha, files = self._repo()
        created = self._create(repo, sha, list(files), repo_id="hello-probe")
        extra = Path(created["workspace_path"]) / "unexpected.py"
        extra.write_text("nope = 1\n", encoding="utf-8")
        review = MOD.review_scoped_repair_patch(operation_id=created["operation_id"], repair_root=self.repair_root)
        self.assertEqual(review["status"], "BLOCKED")
        self.assertEqual(review["failure_reason"], "UNEXPECTED_CHANGED_FILES")
        apply = MOD.apply_scoped_repair_patch(operation_id=created["operation_id"], repair_root=self.repair_root)
        self.assertEqual(apply["status"], "BLOCKED")
        self.assertEqual(apply["failure_reason"], "UNEXPECTED_CHANGED_FILES")

    def test_13_patch_application_detects_git_conflicts(self):
        repo, sha, _ = self._repo(
            files={"src/hello.py": "aaa\nbbb\nccc\n"}
        )
        created = self._create(repo, sha, ["src/hello.py"], repo_id="hello-probe")
        (Path(created["workspace_path"]) / "src" / "hello.py").write_text("aaa\nXXX\nccc\n", encoding="utf-8")
        (repo / "src" / "hello.py").write_text("aaa\nYYY\nccc\n", encoding="utf-8")
        git(["add", "src/hello.py"], cwd=repo)
        git(["commit", "-m", "divergent source"], cwd=repo)
        apply = MOD.apply_scoped_repair_patch(operation_id=created["operation_id"], repair_root=self.repair_root)
        self.assertEqual(apply["status"], "BLOCKED")
        self.assertEqual(apply["failure_reason"], "PATCH_CONFLICT")
        self.assertFalse(apply.get("applied"))

    def test_14_existing_uncommitted_owner_changes_are_preserved(self):
        repo, sha, files = self._repo()
        created = self._create(repo, sha, ["src/hello.py"], repo_id="hello-probe")
        owner = repo / "owner-notes.txt"
        owner.write_text("keep me\n", encoding="utf-8")
        (Path(created["workspace_path"]) / "src" / "hello.py").write_text("VALUE = 9\n", encoding="utf-8")
        apply = MOD.apply_scoped_repair_patch(operation_id=created["operation_id"], repair_root=self.repair_root)
        self.assertEqual(apply["status"], "BLOCKED")
        self.assertEqual(apply["failure_reason"], "UNCOMMITTED_OWNER_CHANGES")
        self.assertEqual(owner.read_text(encoding="utf-8"), "keep me\n")
        self.assertEqual((repo / "src" / "hello.py").read_text(encoding="utf-8"), "VALUE = 1\n")

    def test_15_cleanup_cannot_remove_unrelated_directories(self):
        repo, sha, files = self._repo()
        created = self._create(repo, sha, list(files), repo_id="hello-probe")
        unrelated = self.tmp / "do-not-delete"
        unrelated.mkdir()
        marker = unrelated / "keep.txt"
        marker.write_text("stay\n", encoding="utf-8")
        refused = MOD.cleanup_scoped_repair_workspace(
            operation_id=created["operation_id"],
            target=str(unrelated),
            repair_root=self.repair_root,
        )
        self.assertEqual(refused["status"], "BLOCKED")
        self.assertIn("UNRELATED", refused["failure_reason"])
        self.assertTrue(marker.is_file())
        self.assertTrue(repo.is_dir())
        trusted_path = self.repair_root / "receipts" / f"{created['operation_id']}.json"
        trusted = json.loads(trusted_path.read_text(encoding="utf-8"))
        trusted["workspace_path"] = str(repo)
        trusted_path.write_text(json.dumps(trusted), encoding="utf-8")
        (Path(created["workspace_path"]) / MOD.RECEIPT_NAME).write_text(json.dumps(trusted), encoding="utf-8")
        refused_auth = MOD.cleanup_scoped_repair_workspace(
            operation_id=created["operation_id"],
            repair_root=self.repair_root,
        )
        self.assertEqual(refused_auth["status"], "BLOCKED")
        self.assertTrue(repo.is_dir())
        trusted["workspace_path"] = created["workspace_path"]
        trusted_path.write_text(json.dumps(trusted), encoding="utf-8")
        ok = MOD.cleanup_scoped_repair_workspace(
            operation_id=created["operation_id"],
            repair_root=self.repair_root,
        )
        self.assertEqual(ok["status"], "COMPLETED")
        self.assertFalse(Path(created["workspace_path"]).exists())
        self.assertTrue(repo.is_dir())
        self.assertTrue(unrelated.is_dir())
        reused = MOD.authorize_cursor_workspace(created["workspace_path"], repair_root=self.repair_root)
        self.assertFalse(reused["allowed"])

    def test_16_existing_conversation_and_mission_origin_routing_remain_unaffected(self):
        self.assertEqual(ORCH.CAPABILITY_ROUTE["code_implementation"]["action"], "cursor_call")
        self.assertEqual(ORCH.CAPABILITY_ROUTE["code_review"]["action"], "cursor_call")
        self.assertEqual(ORCH.CAPABILITY_ROUTE["repo_preflight"]["action"], "repo_preflight")
        self.assertIn("cursor_call", INBOX.ALLOWED)
        self.assertIn("repo_preflight", INBOX.ALLOWED)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rec = ORCH.submit(
                job_id="JOB-TEST-SCOPED-CONV-CC",
                capability="code_implementation",
                objective="harmless sandbox task",
                repo=r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox",
                prompt="List files. Do not edit files.",
                inbox_root=root,
            )
            self.assertEqual(rec["state"], "DISPATCHED")
            payload = json.loads((root / "inbox" / "JOB-TEST-SCOPED-CONV-CC.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["action"], "cursor_call")
            pre = ORCH.submit(
                job_id="JOB-TEST-SCOPED-PRE",
                capability="repo_preflight",
                objective="preflight",
                repo=r"C:\Development\Workspace\NEEWA-OS",
                inbox_root=root,
            )
            self.assertEqual(pre["state"], "DISPATCHED")
            scoped = ORCH.submit(
                job_id="JOB-TEST-SCOPED-CREATE",
                capability="scoped_repair_workspace",
                objective="create scoped workspace",
                repo=str(self.personal / "hello-probe"),
                files=["src/hello.py"],
                expected_base_sha="abc1234",
                repository_id="hello-probe",
                inbox_root=root,
            )
            self.assertEqual(scoped["state"], "DISPATCHED")
            scoped_payload = json.loads((root / "inbox" / "JOB-TEST-SCOPED-CREATE.json").read_text(encoding="utf-8"))
            self.assertEqual(scoped_payload["action"], "create_scoped_repair_workspace")
        autonomy = (SCRIPTS / "neewa_autonomy.py").read_text(encoding="utf-8")
        self.assertIn("conversation", autonomy)
        self.assertIn("origin", autonomy)
        mission = (SCRIPTS / "neewa_mission.py").read_text(encoding="utf-8")
        self.assertIn("mission-supervisor", mission)

    def test_neewa_os_identity_requires_markers(self):
        repo, sha, files = self._repo(name="NEEWA-OS")
        result = self._create(repo, sha, list(files), repo_id="NEEWA-OS")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("NOT_NEEWA_OS", result["failure_reason"])

    def test_apply_returns_patch_without_commit_or_push(self):
        repo, sha, _ = self._repo()
        created = self._create(repo, sha, ["src/hello.py"], repo_id="hello-probe")
        (Path(created["workspace_path"]) / "src" / "hello.py").write_text("VALUE = 7\n", encoding="utf-8")
        review = MOD.review_scoped_repair_patch(operation_id=created["operation_id"], repair_root=self.repair_root)
        self.assertEqual(review["status"], "COMPLETED")
        self.assertIn("VALUE = 7", review["patch"])
        applied = MOD.apply_scoped_repair_patch(operation_id=created["operation_id"], repair_root=self.repair_root)
        self.assertEqual(applied["status"], "COMPLETED")
        self.assertTrue(applied["applied"])
        self.assertFalse(applied["committed"])
        self.assertFalse(applied["pushed"])
        self.assertEqual((repo / "src" / "hello.py").read_text(encoding="utf-8"), "VALUE = 7\n")
        porcelain = git(["status", "--porcelain"], cwd=repo).stdout
        self.assertTrue(porcelain.strip())
        head = git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()
        self.assertEqual(head, sha)

    def test_cursor_call_script_gates_scoped_repair_paths(self):
        src = (WORKER / "NeewaPersonalWorkspace.ps1").read_text(encoding="utf-8")
        self.assertIn("Test-ScopedRepairAuthorized", src)
        self.assertIn("authorize-cursor", src)
        self.assertIn("scoped-repair", src)

    def test_isolated_acceptance_on_harmless_personal_repo(self):
        repo, sha, files = self._repo(name="scoped-repair-acceptance")
        created = MOD.dispatch(
            {
                "action": "create_scoped_repair_workspace",
                "job_id": "SCOPED-ACCEPT-01",
                "repo": str(repo),
                "repository_id": "scoped-repair-acceptance",
                "files": list(files),
                "expected_base_sha": sha,
            },
            repair_root=self.repair_root,
        )
        self.assertEqual(created["status"], "COMPLETED", created)
        self.assertEqual(git(["rev-parse", "HEAD"], cwd=repo).stdout.strip(), sha)
        self.assertEqual(git(["status", "--porcelain"], cwd=repo).stdout, "")
        gate = MOD.authorize_cursor_workspace(created["workspace_path"], repair_root=self.repair_root)
        self.assertTrue(gate["allowed"])
        (Path(created["workspace_path"]) / "src" / "hello.py").write_text("VALUE = 3\n", encoding="utf-8")
        review = MOD.review_scoped_repair_patch(operation_id=created["operation_id"], repair_root=self.repair_root)
        self.assertEqual(review["status"], "COMPLETED")
        self.assertTrue(review.get("independent_validation_required"))
        applied = MOD.apply_scoped_repair_patch(operation_id=created["operation_id"], repair_root=self.repair_root)
        self.assertEqual(applied["status"], "COMPLETED")
        self.assertEqual((repo / "src" / "hello.py").read_text(encoding="utf-8"), "VALUE = 3\n")
        cleaned = MOD.cleanup_scoped_repair_workspace(
            operation_id=created["operation_id"], repair_root=self.repair_root
        )
        self.assertEqual(cleaned["status"], "COMPLETED")
        self.assertTrue(repo.is_dir())
        self.assertFalse(Path(created["workspace_path"]).exists())


if __name__ == "__main__":
    unittest.main()
