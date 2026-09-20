import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "12_SCRIPTS" / "deploy_sync.sh"
UNIT = ROOT / "12_SCRIPTS" / "systemd" / "neewa-autonomy-runner.service"
INSTALL = ROOT / "12_SCRIPTS" / "install_neewa_autonomy_runner.sh"


def bash_path(path: Path | str) -> str:
    text = str(path)
    if os.name == "nt" and len(text) >= 2 and text[1] == ":":
        drive = text[0].lower()
        rest = text[2:].replace("\\", "/")
        if not rest.startswith("/"):
            rest = "/" + rest
        return f"/mnt/{drive}{rest}"
    return Path(path).as_posix()


class DeploySyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SCRIPT.read_text(encoding="utf-8")
        cls.unit = UNIT.read_text(encoding="utf-8")
        cls.install = INSTALL.read_text(encoding="utf-8")

    def test_shell_syntax(self):
        for script in (SCRIPT, INSTALL):
            result = subprocess.run(["bash", "-n", bash_path(script)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_requires_immutable_sha_and_service(self):
        self.assertIn("--sha SHA", self.text)
        self.assertIn("--service UNIT", self.text)

    def test_user_versus_system_systemd_scope(self):
        self.assertIn('SYSTEMCTL_BIN="${SYSTEMCTL_BIN:-systemctl --user}"', self.text)
        self.assertIn("deploy_sync requires user-scoped systemctl", self.text)
        self.assertIn('SYSTEMCTL_BIN="${SYSTEMCTL_BIN:-systemctl --user}"', self.install)
        self.assertIn("installer requires user-scoped systemctl", self.install)
        self.assertNotIn('SYSTEMCTL_BIN="${SYSTEMCTL_BIN:-systemctl}"', self.text)
        self.assertNotIn('systemctl "$SERVICE" restart', self.text)

    def test_installed_user_unit_path(self):
        self.assertIn('UNIT_DIR="${NEEWA_USER_UNIT_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user}"', self.text)
        self.assertIn('UNIT_DIR="${NEEWA_USER_UNIT_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user}"', self.install)
        self.assertIn('unit_path="$UNIT_DIR/$SERVICE"', self.text)
        self.assertIn("installed user unit missing", self.text)
        self.assertIn("FragmentPath=$unit_path", self.text)
        self.assertIn('UNIT_DST="$UNIT_DIR/$UNIT_NAME"', self.install)
        self.assertIn("~/.config/systemd/user", self.unit)

    def test_stable_checkout_and_exec_paths(self):
        self.assertIn("-p ExecStart -p WorkingDirectory -p FragmentPath", self.text)
        self.assertIn("service must reference current symlink path", self.text)
        self.assertIn("/opt/neewa/neewa-os-current", self.unit)
        self.assertIn("WorkingDirectory=/opt/neewa/neewa-os-current", self.unit)
        self.assertIn("ExecStart=/bin/bash /opt/neewa/neewa-os-current/12_SCRIPTS/neewa_autonomy_runner.sh", self.unit)
        self.assertNotIn("WorkingDirectory=/opt/neewa/neewa-os\n", self.unit)
        self.assertNotIn("NEEWA_OS_ROOT=/opt/neewa/neewa-os\n", self.unit)
        self.assertIn('STABLE="${NEEWA_CURRENT_LINK:-/opt/neewa/neewa-os-current}"', self.install)
        self.assertIn('ROOT="${NEEWA_OS_ROOT:-$STABLE}"', self.install)

    def test_existing_install_migration(self):
        self.assertIn("legacy/checksum-named path", self.install)
        self.assertIn("/[0-9a-f]{40}(/|$)", self.install)
        self.assertIn("/opt/neewa/neewa-os([^[:alnum:]-]|$)", self.install)
        self.assertIn("created current symlink", self.install)
        self.assertIn('LEGACY="${NEEWA_LEGACY_ROOT:-/opt/neewa/neewa-os}"', self.install)

    def test_environment_and_lingering(self):
        self.assertIn("XDG_RUNTIME_DIR must be set", self.text)
        self.assertIn("LOGINCTL_BIN", self.text)
        self.assertIn("Linger=yes", self.text)
        self.assertIn("user lingering is not enabled", self.text)
        self.assertIn("user lingering is not enabled", self.install)
        self.assertIn("systemctl --user", self.install)

    def test_ownership_permissions_checks(self):
        self.assertIn("require_owner_mode", self.text)
        self.assertIn("group/world-writable", self.text)
        self.assertIn("not owned by deploying user", self.text)
        self.assertIn("chmod 0644", self.install)
        self.assertIn("installed user unit not owned by deploying user", self.install)
        self.assertIn("installed user unit is group/world-writable", self.install)

    def test_service_reload_enable_restart(self):
        self.assertIn('run_systemctl daemon-reload', self.text)
        self.assertIn('run_systemctl enable "$SERVICE"', self.text)
        self.assertIn('run_systemctl restart "$SERVICE"', self.text)
        self.assertIn('run_systemctl is-active --quiet "$SERVICE"', self.text)
        self.assertIn("run_systemctl daemon-reload", self.install)
        self.assertIn('run_systemctl enable --now "$UNIT_NAME"', self.install)
        self.assertIn('run_systemctl restart "$UNIT_NAME"', self.install)

    def test_refuses_real_current_target(self):
        self.assertIn("current target is not a symlink", self.text)
        self.assertIn("current target is not a symlink", self.install)

    def test_atomic_switch_and_rollback(self):
        self.assertIn("mv -Tf \"$tmp_link\" \"$CURRENT_LINK\"", self.text)
        self.assertIn("rollback()", self.text)
        self.assertIn('run_systemctl restart "$SERVICE"', self.text)

    def test_health_and_receipt(self):
        self.assertIn("HEALTH_FILE", self.text)
        self.assertIn("versions.get('sha')", self.text)
        self.assertIn('"result": sys.argv[2]', self.text)
        self.assertIn("heartbeat SHA did not verify", self.text)

    def test_retention_protects_active_and_rollback(self):
        self.assertIn("protected=\"$release${old:+ $old}\"", self.text)
        self.assertIn("case \" $protected \"", self.text)


if __name__ == "__main__":
    unittest.main()
