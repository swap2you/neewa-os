import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "12_SCRIPTS" / "neewa_ops.py"
SPEC = importlib.util.spec_from_file_location("neewa_ops", MODULE_PATH)
ops = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(ops)


class RepositoryValidationTests(unittest.TestCase):
    def test_repository_contracts_pass_without_manifest_precondition(self):
        result = ops.validate_repository(require_manifest=False)
        self.assertTrue(result["passed"], result)

    def test_manifest_matches_complete_working_tree(self):
        expected = sorted(p.relative_to(ops.ROOT).as_posix() for p in ops.manifest_source_files())
        self.assertEqual(expected, ops.manifest_entries())
        self.assertFalse(any(entry.startswith("evidence/") for entry in expected))
        self.assertFalse(any(entry.startswith("evidence/") for entry in ops.manifest_entries()))
        evidence = [p for p in ops.repo_files() if "evidence" in p.relative_to(ops.ROOT).parts]
        self.assertTrue(evidence, "valuable evidence must remain in the working tree")
        self.assertIsInstance(ops.scan_secrets(), list)

    def test_no_secret_signatures_in_repository(self):
        self.assertEqual([], ops.scan_secrets())

    def test_governance_hierarchy_exists(self):
        for relative in ops.REQUIRED_GOVERNANCE:
            self.assertTrue((ops.ROOT / relative).is_file(), relative)

    def test_secret_scanner_detects_quoted_json_password(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = "abcdefghijkl" + "mnop"
            (root / "fixture.json").write_text(json.dumps({"password": value}))
            findings = ops.scan_secrets(root)
            self.assertEqual("generic_secret_assignment", findings[0]["pattern"])

    def test_secret_scanner_detects_compact_later_json_property(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = "abcdefghijkl" + "mnop"
            (root / "fixture.json").write_text(json.dumps({"safe": 1, "password": value}, separators=(",", ":")))
            findings = ops.scan_secrets(root)
            self.assertEqual("generic_secret_assignment", findings[0]["pattern"])

    def test_secret_scanner_detects_array_wrapped_json_object(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = "abcdefghijkl" + "mnop"
            (root / "fixture.json").write_text(json.dumps([{"password": value}], separators=(",", ":")))
            findings = ops.scan_secrets(root)
            self.assertEqual("generic_secret_assignment", findings[0]["pattern"])

    def test_secret_scanner_allows_environment_references(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "fixture.yaml").write_text("api_key: os.environ/OPENAI_API_KEY\n")
            self.assertEqual([], ops.scan_secrets(root))



class JobLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "11_CONFIG").mkdir()
        for filename in ["runtime.json", "budgets.json", "projects.json"]:
            (self.root / "11_CONFIG" / filename).write_bytes((ops.ROOT / "11_CONFIG" / filename).read_bytes())
        self.originals = (ops.ROOT, ops.RUNTIME, ops.BUDGETS, ops.PROJECTS)
        ops.ROOT = self.root
        ops.RUNTIME = self.root / "11_CONFIG/runtime.json"
        ops.BUDGETS = self.root / "11_CONFIG/budgets.json"
        ops.PROJECTS = self.root / "11_CONFIG/projects.json"
        self.state_dir = self.root / "jobs"

    def tearDown(self):
        ops.ROOT, ops.RUNTIME, ops.BUDGETS, ops.PROJECTS = self.originals
        self.temp.cleanup()

    def create(self, risk="low", budget=1.0, approval_level=None):
        return ops.create_job("PRJ-NEEWA", "test objective", risk, budget, self.state_dir, approval_level)

    def test_valid_lifecycle_reaches_validation(self):
        path = self.create()
        for state in ["TRIAGED", "PLANNED", "EXECUTING", "VALIDATING"]:
            job = ops.transition_job(path, state)
        self.assertEqual("VALIDATING", job["state"])

    def test_invalid_transition_is_rejected(self):
        path = self.create()
        with self.assertRaisesRegex(ValueError, "invalid transition"):
            ops.transition_job(path, "DONE")

    def test_budget_above_autonomous_default_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "exceeds autonomous default"):
            self.create(budget=5.01)

    def test_pause_blocks_new_jobs(self):
        runtime = ops.load_json(ops.RUNTIME)
        runtime["mode"] = "PAUSE"
        ops.save_json(ops.RUNTIME, runtime)
        with self.assertRaisesRegex(ValueError, "blocked"):
            self.create()

    def test_done_gate_rejects_missing_evidence(self):
        path = self.create()
        for state in ["TRIAGED", "PLANNED", "EXECUTING", "VALIDATING"]:
            ops.transition_job(path, state)
        passed, failures = ops.gate_job(path, self.root)
        self.assertFalse(passed)
        self.assertIn("evidence is missing", failures)
        self.assertEqual("VALIDATING", ops.load_json(path)["state"])

    def test_done_gate_accepts_complete_low_risk_job(self):
        path = self.create()
        for state in ["TRIAGED", "PLANNED", "EXECUTING", "VALIDATING"]:
            ops.transition_job(path, state)
        evidence = self.root / "evidence" / "evidence.txt"
        evidence.parent.mkdir()
        evidence.write_text("verified\n")
        job = ops.load_json(path)
        job["automated_checks"] = [{"name": "unit", "status": "passed"}]
        job["evidence"] = ["evidence/evidence.txt"]
        ops.save_json(path, job)
        passed, failures = ops.gate_job(path, self.root)
        self.assertTrue(passed, failures)
        self.assertEqual("DONE", ops.load_json(path)["state"])

    def test_medium_risk_requires_independent_review(self):
        path = self.create(risk="medium")
        for state in ["TRIAGED", "PLANNED", "EXECUTING", "VALIDATING"]:
            ops.transition_job(path, state)
        evidence = self.root / "evidence" / "evidence.txt"
        evidence.parent.mkdir()
        evidence.write_text("verified\n")
        job = ops.load_json(path)
        job["automated_checks"] = [{"name": "unit", "status": "passed"}]
        job["evidence"] = ["evidence/evidence.txt"]
        ops.save_json(path, job)
        passed, failures = ops.gate_job(path, self.root)
        self.assertFalse(passed)
        self.assertIn("independent review missing or failed", failures)


    def test_critical_job_requires_a3_owner_gate(self):
        path = self.create(risk="critical")
        job = ops.load_json(path)
        self.assertEqual("A3", job["approval_level"])
        self.assertEqual({"required": True, "status": "pending"}, job["owner_gate"])

    def test_high_risk_cannot_downgrade_approval(self):
        with self.assertRaisesRegex(ValueError, "requires at least A2"):
            self.create(risk="high", approval_level="A1")

    def test_done_gate_rejects_absolute_evidence_path(self):
        path = self.create()
        for state in ["TRIAGED", "PLANNED", "EXECUTING", "VALIDATING"]:
            ops.transition_job(path, state)
        job = ops.load_json(path)
        job["automated_checks"] = [{"name": "unit", "status": "passed"}]
        # Use an absolute path valid on the current OS so the "is_absolute()"
        # rejection is exercised portably (a leading-slash POSIX path is NOT
        # absolute under pathlib on Windows, which would mask this check).
        abs_evidence = r"C:\Windows\System32\drivers\etc\hosts" if os.name == "nt" else "/etc/hosts"
        job["evidence"] = [abs_evidence]
        ops.save_json(path, job)
        passed, failures = ops.gate_job(path, self.root)
        self.assertFalse(passed)
        self.assertTrue(
            any(f.startswith("invalid evidence path:") for f in failures),
            failures,
        )

    @unittest.skipIf(
        os.name == "nt",
        "POSIX symlink creation needs elevated privilege on Windows (WinError 1314); "
        "the symlink-escape rejection is exercised on Linux/CI where the server runs.",
    )
    def test_done_gate_rejects_symlink_escape(self):
        path = self.create()
        for state in ["TRIAGED", "PLANNED", "EXECUTING", "VALIDATING"]:
            ops.transition_job(path, state)
        evidence_dir = self.root / "evidence"
        evidence_dir.mkdir()
        (evidence_dir / "escape").symlink_to("/etc/hosts")
        job = ops.load_json(path)
        job["automated_checks"] = [{"name": "unit", "status": "passed"}]
        job["evidence"] = ["evidence/escape"]
        ops.save_json(path, job)
        passed, failures = ops.gate_job(path, self.root)
        self.assertFalse(passed)
        self.assertIn("evidence outside configured directory: evidence/escape", failures)

    def test_third_rework_is_rejected(self):
        path = self.create()
        ops.transition_job(path, "TRIAGED")
        ops.transition_job(path, "PLANNED")
        ops.transition_job(path, "EXECUTING")
        for cycle in range(2):
            ops.transition_job(path, "REWORK")
            ops.transition_job(path, "EXECUTING")
        with self.assertRaisesRegex(ValueError, "remediation limit exceeded"):
            ops.transition_job(path, "REWORK")


if __name__ == "__main__":
    unittest.main()
