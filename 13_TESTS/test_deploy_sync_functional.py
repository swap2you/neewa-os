import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "12_SCRIPTS" / "deploy_sync.sh"


class DeploySyncFunctionalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "12_SCRIPTS").mkdir()
        (self.source / "13_TESTS").mkdir()
        (self.source / "12_SCRIPTS" / "neewa_ops.py").write_text("print('passed')\n", encoding="utf-8")
        (self.source / "13_TESTS" / "test_smoke.py").write_text(
            "import unittest\nclass Smoke(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "init", "-q"], cwd=self.source, check=True)
        subprocess.run(["git", "config", "user.email", "test@local"], cwd=self.source, check=True)
        subprocess.run(["git", "config", "user.name", "test"], cwd=self.source, check=True)
        subprocess.run(["git", "add", "."], cwd=self.source, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=self.source, check=True)
        self.sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.source, text=True).strip()
        self.releases = self.root / "releases"
        self.current = self.root / "current"
        self.health = self.root / "health.json"
        self.receipt = self.root / "receipt.json"
        self.fakebin = self.root / "bin"
        self.fakebin.mkdir()
        self.systemctl = self.fakebin / "systemctl"
        self.systemctl.write_text(
            "#!/usr/bin/env bash\n"
            "case \"$1\" in\n"
            " show) printf 'ExecStart=%s/service\nWorkingDirectory=%s\nUser=test\n' \"$CURRENT_LINK\" \"$CURRENT_LINK\";;\n"
            " restart) [[ \"${FAKE_RESTART_FAIL:-0}\" == 1 ]] && exit 1 || exit 0;;\n"
            " is-active) [[ \"${FAKE_INACTIVE:-0}\" == 1 ]] && exit 3 || exit 0;;\n"
            " *) exit 1;;\n"
            "esac\n",
            encoding="utf-8",
        )
        self.systemctl.chmod(0o755)
        self.env = os.environ.copy()
        self.env.update({
            "PATH": f"{self.fakebin}:{self.env['PATH']}",
            "CURRENT_LINK": str(self.current),
            "NEEWA_HEALTH_ATTEMPTS": "1",
            "NEEWA_HEALTH_SLEEP": "0",
        })

    def tearDown(self):
        self.tmp.cleanup()

    def write_health(self, sha):
        self.health.write_text(json.dumps({"versions": {"sha": sha}}), encoding="utf-8")

    def run_deploy(self, **extra):
        self.systemctl.chmod(0o755)
        args = ["bash", str(SCRIPT), "--sha", self.sha, "--repo-url", str(self.source),
                "--release-root", str(self.releases), "--current-link", str(self.current),
                "--service", "neewa-test.service", "--health-file", str(self.health),
                "--receipt", str(self.receipt), "--keep", "2"]
        env = dict(self.env)
        env.update({k: str(v) for k, v in extra.items()})
        env["SYSTEMCTL_BIN"] = f"bash {self.systemctl}"
        return subprocess.run(args, capture_output=True, text=True, env=env)

    def test_first_deployment_and_idempotent_redeployment(self):
        self.write_health(self.sha)
        first = self.run_deploy()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(self.current.resolve(), self.releases / self.sha)
        second = self.run_deploy()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(json.loads(self.receipt.read_text())["result"], "PASS")

    def test_restart_failure(self):
        self.write_health(self.sha)
        result = self.run_deploy(FAKE_RESTART_FAIL=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(self.receipt.read_text())["result"], "FAILED")

    def test_inactive_service(self):
        self.write_health(self.sha)
        result = self.run_deploy(FAKE_INACTIVE=1)
        self.assertNotEqual(result.returncode, 0)

    def test_heartbeat_mismatch_rolls_back(self):
        old = self.releases / ("a" * 40)
        old.mkdir(parents=True)
        self.current.symlink_to(old)
        self.health.write_text(json.dumps({"versions": {"sha": "0" * 40}}), encoding="utf-8")
        result = self.run_deploy()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.current.resolve(), old)

    def test_non_symlink_target_refused(self):
        self.current.mkdir(parents=True)
        self.write_health(self.sha)
        result = self.run_deploy()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a symlink", result.stderr)

    def test_retention_preserves_active_and_rollback(self):
        old = self.releases / ("b" * 40)
        old.mkdir(parents=True)
        self.current.symlink_to(old)
        for char in "12345":
            (self.releases / (char * 40)).mkdir(parents=True)
        self.write_health(self.sha)
        result = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.releases / self.sha).is_dir())
        self.assertTrue(old.is_dir())


if __name__ == "__main__":
    unittest.main()
