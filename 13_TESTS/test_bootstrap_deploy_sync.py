import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "12_SCRIPTS" / "bootstrap_deploy_sync.sh"


class BootstrapDeploySyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SCRIPT.read_text(encoding="utf-8")

    def test_shell_syntax(self):
        result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_requires_full_commit_and_checksum_before_network(self):
        for args in (["--commit", "short", "--sha256", "0" * 64],
                     ["--commit", "0" * 40, "--sha256", "short"]):
            result = subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("required", result.stderr)

    def test_download_is_commit_pinned_and_verified_before_execution(self):
        self.assertIn("raw.githubusercontent.com/swap2you/neewa-os/$COMMIT/12_SCRIPTS/deploy_sync.sh", self.text)
        self.assertIn('actual="$(sha256sum "$tmp"', self.text)
        self.assertIn('[[ "$actual" == "${SHA256,,}" ]]', self.text)
        self.assertIn('"$DEST" "${deploy_args[@]}"', self.text)

    def test_temp_file_is_cleaned_on_failure(self):
        self.assertIn("trap 'rm -f \"$tmp\"' EXIT", self.text)
        self.assertIn('trap - EXIT', self.text)


if __name__ == "__main__":
    unittest.main()
