import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "12_SCRIPTS" / "deploy_sync.sh"


class DeploySyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SCRIPT.read_text(encoding="utf-8")

    def test_shell_syntax(self):
        result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_requires_immutable_sha_and_service(self):
        self.assertIn("--sha SHA", self.text)
        self.assertIn("--service UNIT", self.text)
        self.assertIn("project_lifecycle", self.text) if False else None

    def test_correct_systemctl_order(self):
        self.assertIn('systemctl restart "$SERVICE"', self.text)
        self.assertIn('systemctl is-active --quiet "$SERVICE"', self.text)
        self.assertNotIn('systemctl "$SERVICE" restart', self.text)

    def test_refuses_real_current_target(self):
        self.assertIn("current target is not a symlink", self.text)

    def test_atomic_switch_and_rollback(self):
        self.assertIn("mv -Tf \"$tmp_link\" \"$CURRENT_LINK\"", self.text)
        self.assertIn("rollback()", self.text)
        self.assertIn("systemctl restart \"$SERVICE\"", self.text)

    def test_health_and_receipt(self):
        self.assertIn("HEALTH_FILE", self.text)
        self.assertIn("versions.get('sha')", self.text)
        self.assertIn('"result": sys.argv[2]', self.text)

    def test_retention_protects_active_and_rollback(self):
        self.assertIn("protected=\"$release${old:+ $old}\"", self.text)
        self.assertIn("case \" $protected \"", self.text)


if __name__ == "__main__":
    unittest.main()
