import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "11_CONFIG" / "projects.json"
POLICY = ROOT / "16_WINDOWS_CLIENT" / "worker" / "workspace-inventory-policy.json"
PORTFOLIO = ROOT / "evidence" / "PROJECT_PORTFOLIO"


class ProjectPortfolioTests(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.policy = json.loads(POLICY.read_text(encoding="utf-8"))
        self.projects = self.registry["projects"]
        self.by_id = {row["id"]: row for row in self.projects}

    def test_ids_are_unique(self):
        ids = [row["id"] for row in self.projects]
        self.assertEqual(len(ids), len(set(ids)))

    def test_each_inventoried_personal_project_has_exactly_one_registry_record(self):
        personal = list(self.policy["personal_projects"])
        names = [row.get("workspace_name") for row in self.projects if row.get("kind") == "inventoried_personal"]
        self.assertEqual(sorted(personal), sorted(names))
        self.assertEqual(len(personal), len(set(names)))

    def test_each_project_has_one_isolated_evidence_location(self):
        paths = []
        for row in self.projects:
            rel = row["evidence_path"]
            folder = ROOT / rel
            self.assertTrue(folder.is_dir(), rel)
            self.assertTrue((folder / "record.json").is_file(), rel)
            self.assertTrue((folder / "CONTEXT.md").is_file(), rel)
            record = json.loads((folder / "record.json").read_text(encoding="utf-8"))
            self.assertEqual(record["id"], row["id"])
            self.assertEqual(record["evidence_path"], rel)
            self.assertIn("do not mix", (folder / "CONTEXT.md").read_text(encoding="utf-8").lower())
            paths.append(rel)
        self.assertEqual(len(paths), len(set(paths)))

    def test_skipped_denied_and_unclassified_are_recorded(self):
        skipped = {row["name"]: row for row in self.registry["skipped"]}
        for name in self.policy["denied_name_equals"]:
            self.assertEqual(skipped[name]["classification"], "denied")
            self.assertIn("not recursed", skipped[name]["reason"])
        self.assertEqual(skipped["Udemy-Yutube-repos"]["classification"], "unclassified")
        self.assertIn("not inventoried", skipped["Udemy-Yutube-repos"]["reason"])

    def test_no_denied_name_is_a_workspace_project(self):
        names = {row.get("workspace_name") for row in self.projects}
        for denied in self.policy["denied_name_equals"]:
            self.assertNotIn(denied, names)
        self.assertNotIn("Udemy-Yutube-repos", names)

    def test_records_do_not_contain_secret_payloads(self):
        blob = "\n".join(
            path.read_text(encoding="utf-8")
            for path in PORTFOLIO.rglob("*")
            if path.is_file()
        )
        self.assertNotIn("BEGIN PRIVATE KEY", blob)
        self.assertNotIn("BEGIN OPENSSH PRIVATE KEY", blob)
        self.assertNotIn("AKIA", blob)

    def test_charters_exist_for_registry_paths(self):
        for row in self.projects:
            self.assertTrue((ROOT / row["path"] / "PROJECT.md").is_file(), row["id"])


if __name__ == "__main__":
    unittest.main()
