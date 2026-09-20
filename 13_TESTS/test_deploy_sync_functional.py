import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "12_SCRIPTS" / "deploy_sync.sh"
INSTALL = ROOT / "12_SCRIPTS" / "install_neewa_autonomy_runner.sh"
UNIT = ROOT / "12_SCRIPTS" / "systemd" / "neewa-autonomy-runner.service"


def bash_path(path: Path | str) -> str:
    """Translate Windows paths for WSL bash while leaving POSIX paths unchanged."""
    text = str(path)
    if os.name == "nt" and len(text) >= 2 and text[1] == ":":
        drive = text[0].lower()
        rest = text[2:].replace("\\", "/")
        if not rest.startswith("/"):
            rest = "/" + rest
        return f"/mnt/{drive}{rest}"
    return Path(path).as_posix()


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
        self.unit_dir = self.root / "systemd-user"
        self.unit_dir.mkdir()
        self.service = "neewa-test.service"
        self.unit_path = self.unit_dir / self.service
        self.unit_path.write_text(
            "[Service]\n"
            f"WorkingDirectory={self.current}\n"
            f"ExecStart=/bin/bash {self.current}/service\n",
            encoding="utf-8",
        )
        self.unit_path.chmod(0o644)
        self.fakebin = self.root / "bin"
        self.fakebin.mkdir()
        self.systemctl_log = self.root / "systemctl.log"
        self.systemctl = self.fakebin / "systemctl"
        self.systemctl.write_text(
            "#!/usr/bin/env bash\n"
            'if [[ "${1:-}" == "--user" ]]; then shift; fi\n'
            'if [[ -n "${FAKE_SYSTEMCTL_LOG:-}" ]]; then printf "%s\\n" "$*" >> "$FAKE_SYSTEMCTL_LOG"; fi\n'
            "case \"$1\" in\n"
            " show)\n"
            "   printf 'ExecStart={ path=/bin/bash ; argv[]=/bin/bash %s/service }\\n' \"$CURRENT_LINK\"\n"
            "   printf 'WorkingDirectory=%s\\n' \"$CURRENT_LINK\"\n"
            "   printf 'FragmentPath=%s\\n' \"$NEEWA_USER_UNIT_DIR/$SERVICE_NAME\"\n"
            "   ;;\n"
            " daemon-reload) [[ \"${FAKE_RELOAD_FAIL:-0}\" == 1 ]] && exit 1 || exit 0;;\n"
            " enable) [[ \"${FAKE_ENABLE_FAIL:-0}\" == 1 ]] && exit 1 || exit 0;;\n"
            " restart) [[ \"${FAKE_RESTART_FAIL:-0}\" == 1 ]] && exit 1 || exit 0;;\n"
            " is-active) [[ \"${FAKE_INACTIVE:-0}\" == 1 ]] && exit 3 || exit 0;;\n"
            " status) exit 0;;\n"
            " *) exit 1;;\n"
            "esac\n",
            encoding="utf-8",
        )
        self.systemctl.chmod(0o755)
        self.loginctl = self.fakebin / "loginctl"
        self.loginctl.write_text(
            "#!/usr/bin/env bash\n"
            "case \"$1\" in\n"
            " show-user)\n"
            "   [[ \"${FAKE_LINGER_NO:-0}\" == 1 ]] && { echo 'Linger=no'; exit 0; }\n"
            "   echo 'Linger=yes'\n"
            "   ;;\n"
            " *) exit 1;;\n"
            "esac\n",
            encoding="utf-8",
        )
        self.loginctl.chmod(0o755)
        self.runtime = self.root / "runtime"
        self.runtime.mkdir()
        self.env = os.environ.copy()
        self.env.update({
            "PATH": f"{bash_path(self.fakebin)}:{self.env.get('PATH', '')}",
            "CURRENT_LINK": bash_path(self.current),
            "NEEWA_USER_UNIT_DIR": bash_path(self.unit_dir),
            "SERVICE_NAME": self.service,
            "XDG_RUNTIME_DIR": bash_path(self.runtime),
            "NEEWA_HEALTH_ATTEMPTS": "1",
            "NEEWA_HEALTH_SLEEP": "0",
            "LOGINCTL_BIN": f"bash {bash_path(self.loginctl)}",
            "FAKE_SYSTEMCTL_LOG": bash_path(self.systemctl_log),
        })

    def tearDown(self):
        self.tmp.cleanup()

    def write_health(self, sha):
        self.health.write_text(json.dumps({"versions": {"sha": sha}}), encoding="utf-8")

    def systemctl_commands(self):
        if not self.systemctl_log.exists():
            return []
        return [line for line in self.systemctl_log.read_text(encoding="utf-8").splitlines() if line]

    def run_deploy(self, **extra):
        self.systemctl.chmod(0o755)
        self.loginctl.chmod(0o755)
        args = [
            "bash", bash_path(SCRIPT), "--sha", self.sha,
            "--repo-url", bash_path(self.source),
            "--release-root", bash_path(self.releases),
            "--current-link", bash_path(self.current),
            "--service", self.service,
            "--health-file", bash_path(self.health),
            "--receipt", bash_path(self.receipt),
            "--keep", "2",
        ]
        env = dict(self.env)
        for key, value in extra.items():
            if key in {"NEEWA_USER_UNIT_DIR", "CURRENT_LINK", "XDG_RUNTIME_DIR"} and value:
                env[key] = bash_path(value)
            else:
                env[key] = str(value)
        env["SYSTEMCTL_BIN"] = f"bash {bash_path(self.systemctl)} --user"
        return subprocess.run(args, capture_output=True, text=True, env=env)

    def test_first_deployment_and_idempotent_redeployment(self):
        self.write_health(self.sha)
        first = self.run_deploy()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(self.current.resolve(), self.releases / self.sha)
        second = self.run_deploy()
        self.assertEqual(second.returncode, 0, second.stderr)
        receipt = json.loads(self.receipt.read_text(encoding="utf-8"))
        self.assertEqual(receipt["result"], "PASS")
        self.assertEqual(receipt["deployed_sha"], self.sha)
        self.assertEqual(receipt["service"], self.service)
        self.assertTrue(receipt["current_link"].endswith("current") or receipt["current_link"] == bash_path(self.current))

    def test_reload_enable_restart_order(self):
        self.write_health(self.sha)
        result = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = [line for line in self.systemctl_commands() if not line.startswith("show")]
        self.assertIn("daemon-reload", commands)
        self.assertIn(f"enable {self.service}", commands)
        self.assertIn(f"restart {self.service}", commands)
        self.assertLess(commands.index("daemon-reload"), commands.index(f"enable {self.service}"))
        self.assertLess(commands.index(f"enable {self.service}"), commands.index(f"restart {self.service}"))

    def test_restart_failure(self):
        self.write_health(self.sha)
        result = self.run_deploy(FAKE_RESTART_FAIL=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(self.receipt.read_text(encoding="utf-8"))["result"], "FAILED")

    def test_enable_failure_rolls_back(self):
        old = self.releases / ("c" * 40)
        old.mkdir(parents=True)
        self.current.symlink_to(old)
        self.write_health(self.sha)
        result = self.run_deploy(FAKE_ENABLE_FAIL=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("service enable failed", result.stderr)
        self.assertEqual(self.current.resolve(), old)
        self.assertEqual(json.loads(self.receipt.read_text(encoding="utf-8"))["result"], "FAILED")

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
        receipt = json.loads(self.receipt.read_text(encoding="utf-8"))
        self.assertEqual(receipt["result"], "FAILED")
        self.assertIn("heartbeat SHA did not verify", result.stderr)
        self.assertEqual(receipt["deployed_sha"], self.sha)

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

    def test_missing_user_unit_refused(self):
        self.unit_path.unlink()
        self.write_health(self.sha)
        result = self.run_deploy()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("installed user unit missing", result.stderr)

    def test_world_writable_unit_refused(self):
        self.unit_path.chmod(0o666)
        self.write_health(self.sha)
        result = self.run_deploy()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("group/world-writable", result.stderr)

    def test_linger_disabled_refused(self):
        self.write_health(self.sha)
        result = self.run_deploy(FAKE_LINGER_NO=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("lingering is not enabled", result.stderr)

    def test_missing_runtime_dir_refused(self):
        self.write_health(self.sha)
        args = [
            "bash", bash_path(SCRIPT), "--sha", self.sha,
            "--repo-url", bash_path(self.source),
            "--release-root", bash_path(self.releases),
            "--current-link", bash_path(self.current),
            "--service", self.service,
            "--health-file", bash_path(self.health),
            "--receipt", bash_path(self.receipt),
            "--keep", "2",
        ]
        env = dict(self.env)
        env.pop("XDG_RUNTIME_DIR", None)
        env["SYSTEMCTL_BIN"] = f"bash {bash_path(self.systemctl)} --user"
        result = subprocess.run(args, capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 2)
        self.assertIn("XDG_RUNTIME_DIR", result.stderr)

    def test_systemctl_without_user_scope_refused(self):
        self.write_health(self.sha)
        args = [
            "bash", bash_path(SCRIPT), "--sha", self.sha,
            "--repo-url", bash_path(self.source),
            "--release-root", bash_path(self.releases),
            "--current-link", bash_path(self.current),
            "--service", self.service,
            "--health-file", bash_path(self.health),
            "--receipt", bash_path(self.receipt),
            "--keep", "2",
        ]
        env = dict(self.env)
        env["SYSTEMCTL_BIN"] = f"bash {bash_path(self.systemctl)}"
        result = subprocess.run(args, capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 2)
        self.assertIn("user-scoped systemctl", result.stderr)

    def test_missing_unit_dir_override_refused(self):
        self.write_health(self.sha)
        result = self.run_deploy(NEEWA_USER_UNIT_DIR=str(self.root / "other-units"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("installed user unit missing", result.stderr)

    def test_exec_paths_must_include_current_link(self):
        self.systemctl.write_text(
            "#!/usr/bin/env bash\n"
            'if [[ "${1:-}" == "--user" ]]; then shift; fi\n'
            "case \"$1\" in\n"
            " show)\n"
            "   printf 'ExecStart=/opt/neewa/neewa-os/service\\n'\n"
            "   printf 'WorkingDirectory=/opt/neewa/neewa-os\\n'\n"
            "   printf 'FragmentPath=%s\\n' \"$NEEWA_USER_UNIT_DIR/$SERVICE_NAME\"\n"
            "   ;;\n"
            " daemon-reload) exit 0;;\n"
            " enable) exit 0;;\n"
            " restart) exit 0;;\n"
            " is-active) exit 0;;\n"
            " *) exit 1;;\n"
            "esac\n",
            encoding="utf-8",
        )
        self.systemctl.chmod(0o755)
        self.write_health(self.sha)
        result = self.run_deploy()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("current/release path", result.stderr)


class AutonomyRunnerInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.checkout = self.root / "checkout-aaaaaaaabbbbbbbbccccccccdddddddd11111111"
        unit_dir = self.checkout / "12_SCRIPTS" / "systemd"
        unit_dir.mkdir(parents=True)
        unit_dir.joinpath("neewa-autonomy-runner.service").write_text(
            UNIT.read_text(encoding="utf-8"), encoding="utf-8"
        )
        self.stable = self.root / "neewa-os-current"
        self.legacy = self.root / "neewa-os"
        self.unit_dir = self.root / "systemd-user"
        self.inbox = self.root / "inbox"
        self.runtime = self.root / "runtime"
        self.runtime.mkdir()
        self.fakebin = self.root / "bin"
        self.fakebin.mkdir()
        self.systemctl_log = self.root / "systemctl.log"
        self.systemctl = self.fakebin / "systemctl"
        self.systemctl.write_text(
            "#!/usr/bin/env bash\n"
            'if [[ "${1:-}" == "--user" ]]; then shift; fi\n'
            'if [[ -n "${FAKE_SYSTEMCTL_LOG:-}" ]]; then printf "%s\\n" "$*" >> "$FAKE_SYSTEMCTL_LOG"; fi\n'
            "case \"$1\" in\n"
            " daemon-reload|enable|restart|status) exit 0;;\n"
            " *) exit 1;;\n"
            "esac\n",
            encoding="utf-8",
        )
        self.systemctl.chmod(0o755)
        self.loginctl = self.fakebin / "loginctl"
        self.loginctl.write_text(
            "#!/usr/bin/env bash\n"
            "case \"$1\" in\n"
            " show-user) echo 'Linger=yes';;\n"
            " *) exit 1;;\n"
            "esac\n",
            encoding="utf-8",
        )
        self.loginctl.chmod(0o755)
        self.env = os.environ.copy()
        self.env.update({
            "HOME": bash_path(self.home),
            "XDG_RUNTIME_DIR": bash_path(self.runtime),
            "NEEWA_OS_ROOT": bash_path(self.checkout),
            "NEEWA_CURRENT_LINK": bash_path(self.stable),
            "NEEWA_LEGACY_ROOT": bash_path(self.legacy),
            "NEEWA_USER_UNIT_DIR": bash_path(self.unit_dir),
            "NEEWA_WINDOWS_JOB_INBOX": bash_path(self.inbox),
            "SYSTEMCTL_BIN": f"bash {bash_path(self.systemctl)} --user",
            "LOGINCTL_BIN": f"bash {bash_path(self.loginctl)}",
            "FAKE_SYSTEMCTL_LOG": bash_path(self.systemctl_log),
            "PATH": f"{bash_path(self.fakebin)}:{self.env.get('PATH', '')}",
        })

    def tearDown(self):
        self.tmp.cleanup()

    def run_install(self, **extra):
        env = dict(self.env)
        env.update({k: str(v) for k, v in extra.items()})
        return subprocess.run(
            ["bash", bash_path(INSTALL)],
            capture_output=True,
            text=True,
            env=env,
        )

    def installed_unit(self):
        return self.unit_dir / "neewa-autonomy-runner.service"

    def test_installs_user_unit_and_creates_stable_symlink(self):
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        unit = self.installed_unit()
        self.assertTrue(unit.is_file())
        self.assertEqual(unit.stat().st_mode & 0o777, 0o644)
        text = unit.read_text(encoding="utf-8")
        self.assertIn("WorkingDirectory=/opt/neewa/neewa-os-current", text)
        self.assertIn("ExecStart=/bin/bash /opt/neewa/neewa-os-current/12_SCRIPTS/neewa_autonomy_runner.sh", text)
        self.assertTrue(self.stable.is_symlink())
        self.assertEqual(self.stable.resolve(), self.checkout.resolve())
        commands = self.systemctl_log.read_text(encoding="utf-8").splitlines()
        self.assertIn("daemon-reload", commands)
        self.assertTrue(any(cmd.startswith("enable --now neewa-autonomy-runner.service") for cmd in commands))
        self.assertIn(f"installed {bash_path(unit)}", result.stdout)

    def test_migrates_legacy_and_checksum_named_unit(self):
        self.unit_dir.mkdir()
        sha_path = "/opt/neewa/releases/neewa-os/" + ("d" * 40)
        self.installed_unit().write_text(
            "[Service]\n"
            "WorkingDirectory=/opt/neewa/neewa-os\n"
            f"ExecStart=/bin/bash {sha_path}/12_SCRIPTS/neewa_autonomy_runner.sh\n",
            encoding="utf-8",
        )
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.installed_unit().read_text(encoding="utf-8")
        self.assertIn("WorkingDirectory=/opt/neewa/neewa-os-current", text)
        self.assertNotIn("WorkingDirectory=/opt/neewa/neewa-os\n", text)
        self.assertNotIn("d" * 40, text)
        self.assertIn("migrated existing user unit from legacy/checksum-named path", result.stdout)
        commands = self.systemctl_log.read_text(encoding="utf-8").splitlines()
        self.assertIn("daemon-reload", commands)
        self.assertTrue(any(cmd.startswith("enable --now ") for cmd in commands))
        self.assertIn("restart neewa-autonomy-runner.service", commands)

    def test_refuses_system_scope_systemctl(self):
        result = self.run_install(SYSTEMCTL_BIN=f"bash {bash_path(self.systemctl)}")
        self.assertEqual(result.returncode, 2)
        self.assertIn("user-scoped systemctl", result.stderr)
        self.assertFalse(self.installed_unit().exists())

    def test_refuses_non_symlink_current_target(self):
        self.stable.mkdir()
        result = self.run_install()
        self.assertEqual(result.returncode, 2)
        self.assertIn("not a symlink", result.stderr)


if __name__ == "__main__":
    unittest.main()
