#!/usr/bin/env python3
"""Tests for neewa_os.py CLI and release-state action semantics."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / "neewa_os.py"
SEM = ROOT / "12_SCRIPTS" / "neewa_action_semantics.py"


class NeewaOsCliTests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(ROOT),
        )

    def test_missing_input_exits_nonzero_with_stderr(self):
        missing = ROOT / "does-not-exist-neewa-os-input.txt"
        completed = self._run(str(missing))
        self.assertNotEqual(completed.returncode, 0)
        self.assertTrue(completed.stderr.strip())
        self.assertIn("not found", completed.stderr.lower())

    def test_no_args_exits_nonzero_with_stderr(self):
        completed = self._run()
        self.assertNotEqual(completed.returncode, 0)
        self.assertTrue(completed.stderr.strip())

    def test_authorize_release_state_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "objective.txt"
            path.write_text(
                "read-only verification of an already released version and release state",
                encoding="utf-8",
            )
            completed = self._run(str(path))
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout.strip())
            self.assertTrue(payload["allowed"])
            self.assertIn(payload["needed"], {"A0", "A1"})
            self.assertEqual(payload["reason"], "ALLOW")
            self.assertNotIn("deploy", payload.get("requested_families") or [])
            self.assertNotIn("release", payload.get("requested_families") or [])

    def test_authorize_consequential_release_is_gated(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "objective.txt"
            path.write_text("cut a release for version 2.0", encoding="utf-8")
            completed = self._run(str(path))
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout.strip())
            self.assertFalse(payload["allowed"])
            self.assertEqual(payload["needed"], "A2")
            self.assertIn("release", payload.get("requested_families") or [])


class ReleaseStateSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.sem = SourceFileLoader("neewa_os_sem", str(SEM)).load_module()

    def test_inspection_wording(self):
        for text in (
            "inspect the release state of the deployed build",
            "verify the deployed release state read-only",
            "confirm the published version matches the tag",
        ):
            analysis = self.sem.analyze_objective(text)
            self.assertEqual(analysis["needed"], "A0", text)
            self.assertEqual(analysis["requested_families"], [], text)

    def test_consequential_gate(self):
        analysis = self.sem.analyze_objective("release this version to production")
        self.assertEqual(analysis["needed"], "A2")
        self.assertIn("release", analysis["requested_families"])

    def test_negated_release(self):
        analysis = self.sem.analyze_objective(
            "do not release this version; only verify the released version"
        )
        self.assertEqual(analysis["needed"], "A0")
        self.assertIn("release", analysis["prohibited_actions"])
        self.assertNotIn("release", analysis["requested_families"])


if __name__ == "__main__":
    unittest.main()
