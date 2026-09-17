"""Unit tests for project_health."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import project_health


class ProjectHealthTests(unittest.TestCase):
    def test_pass_rate(self) -> None:
        self.assertEqual(project_health.pass_rate(42, 2), 95.45)
        self.assertEqual(project_health.pass_rate(30, 0), 100.0)
        self.assertEqual(project_health.pass_rate(0, 0), 0.0)

    def test_health_status(self) -> None:
        self.assertEqual(project_health.health_status(0, 92.0), "healthy")
        self.assertEqual(project_health.health_status(2, 87.5), "warning")
        self.assertEqual(project_health.health_status(5, 61.25), "critical")

    def test_build_report(self) -> None:
        projects = [
            {
                "name": "demo",
                "tests_passed": 10,
                "tests_failed": 0,
                "coverage": 85.0,
            }
        ]
        report = project_health.build_report(projects)
        self.assertEqual(report["project_count"], 1)
        self.assertEqual(report["projects"][0]["status"], "healthy")
        self.assertEqual(report["projects"][0]["pass_rate"], 100.0)

    def test_generate_report_writes_file(self) -> None:
        sample = [
            {
                "name": "alpha-api",
                "tests_passed": 42,
                "tests_failed": 2,
                "coverage": 87.5,
            },
            {
                "name": "beta-web",
                "tests_passed": 30,
                "tests_failed": 0,
                "coverage": 92.0,
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "sample.json"
            output_path = Path(tmp) / "health_report.json"
            input_path.write_text(json.dumps(sample), encoding="utf-8")

            report = project_health.generate_report(input_path, output_path)

            self.assertTrue(output_path.exists())
            loaded = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded, report)
            self.assertEqual(loaded["project_count"], 2)
            self.assertEqual(loaded["projects"][1]["status"], "healthy")
            self.assertEqual(loaded["projects"][0]["status"], "warning")

    def test_sample_json_round_trip(self) -> None:
        sample_path = Path(__file__).resolve().parent / "sample.json"
        self.assertTrue(sample_path.exists())
        with sample_path.open(encoding="utf-8") as handle:
            projects = json.load(handle)
        report = project_health.build_report(projects)
        self.assertEqual(report["project_count"], 3)
        names = [p["name"] for p in report["projects"]]
        self.assertEqual(names, ["alpha-api", "beta-web", "gamma-cli"])


if __name__ == "__main__":
    unittest.main()
