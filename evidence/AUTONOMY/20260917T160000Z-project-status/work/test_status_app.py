import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parent / "status_app.py"


class StatusAppTests(unittest.TestCase):
    def test_happy_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sample = Path(tmp) / "ok.json"
            sample.write_text(
                json.dumps([{"name": "NEEWA", "status": "healthy"}]),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [sys.executable, str(APP), str(sample)],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("NEEWA: healthy", completed.stdout)
        self.assertIn("count=1", completed.stdout)

    def test_malformed_json_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sample = Path(tmp) / "bad.json"
            sample.write_text("{not json", encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(APP), str(sample)],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("invalid status file", completed.stderr)


if __name__ == "__main__":
    unittest.main()
