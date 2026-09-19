import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTO = SourceFileLoader("auto_lifecycle_test", str(ROOT / "12_SCRIPTS" / "neewa_autonomy.py")).load_module()
MISSION = SourceFileLoader("mission_lifecycle_test", str(ROOT / "12_SCRIPTS" / "neewa_mission.py")).load_module()
IDENTITY = SourceFileLoader("identity_lifecycle_test", str(ROOT / "12_SCRIPTS" / "neewa_project_identity.py")).load_module()


class LifecycleBootstrapTests(unittest.TestCase):
    def test_explicit_modify_existing_survives_parent_serialization(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = AUTO.create_parent_job(
                "repair the approved repository",
                project_id="PRJ-NEEWA",
                workspace=r"C:\Development\Workspace\NEEWA-OS",
                root=Path(tmp),
                project_lifecycle="modify_existing",
            )
            self.assertEqual(job["project_lifecycle"], "modify_existing")
            self.assertEqual(job["project_identity"]["lifecycle"], "modify_existing")

    def test_existing_repository_phrase_resolves_modify_existing(self):
        identity = {"workspace_root": r"C:\Development\Workspace", "source": "path_basename"}
        self.assertEqual(
            IDENTITY.resolve_project_lifecycle("repair the existing repository", identity=identity),
            "modify_existing",
        )

    def test_new_empty_request_stays_create_new(self):
        identity = {"workspace_root": r"C:\Development\Workspace", "source": "path_basename"}
        self.assertEqual(
            IDENTITY.resolve_project_lifecycle("create a new isolated project", identity=identity),
            "create_new",
        )

    def test_lifecycle_mismatch_is_recoverable_configuration_defect(self):
        result = MISSION.classify_failure(
            {"state": "FAILED", "failure_class": "PROJECT_ALREADY_EXISTS", "failure_reason": "lifecycle create_new rejected nonempty target"},
            worker_available=True,
        )
        self.assertEqual(result["class"], "CONFIG_DEFECT")
        self.assertTrue(result["recoverable"])

    def test_duplicate_mission_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobs"
            first = MISSION.create_mission(
                "repair the existing repository",
                workspace=r"C:\Development\Workspace\NEEWA-OS",
                project_id="PRJ-NEEWA",
                project_lifecycle="modify_existing",
                root=root,
                auto=AUTO,
            )
            with self.assertRaises(MISSION.DuplicateMission):
                MISSION.create_mission(
                    first["owner_objective"],
                    workspace=first["workspace"],
                    project_id="PRJ-NEEWA",
                    project_lifecycle="modify_existing",
                    root=root,
                    auto=AUTO,
                )


if __name__ == "__main__":
    unittest.main()
