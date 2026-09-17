"""Generate a project health report from sample project metrics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "sample.json"
DEFAULT_OUTPUT = ROOT / "health_report.json"


def pass_rate(tests_passed: int, tests_failed: int) -> float:
    total = tests_passed + tests_failed
    if total == 0:
        return 0.0
    return round(100.0 * tests_passed / total, 2)


def health_status(tests_failed: int, coverage: float) -> str:
    if tests_failed == 0 and coverage >= 80:
        return "healthy"
    if tests_failed <= 3 and coverage >= 70:
        return "warning"
    return "critical"


def build_report(projects: list[dict[str, Any]]) -> dict[str, Any]:
    entries = []
    for project in projects:
        passed = int(project["tests_passed"])
        failed = int(project["tests_failed"])
        coverage = float(project["coverage"])
        entries.append(
            {
                "name": project["name"],
                "tests_passed": passed,
                "tests_failed": failed,
                "coverage": coverage,
                "pass_rate": pass_rate(passed, failed),
                "status": health_status(failed, coverage),
            }
        )
    return {
        "project_count": len(entries),
        "projects": entries,
    }


def generate_report(
    input_path: Path = DEFAULT_INPUT,
    output_path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    with input_path.open(encoding="utf-8") as handle:
        projects = json.load(handle)
    report = build_report(projects)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    return report


def main() -> None:
    report = generate_report()
    print(f"Wrote health report for {report['project_count']} projects to {DEFAULT_OUTPUT}")


if __name__ == "__main__":
    main()
