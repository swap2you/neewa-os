"""Tests for the context-aware morning brief: host vs sandbox, and failure cases.

These exercise snapshot consumption without invoking host-only binaries, and
assert the invariant that a service is never reported healthy when unknown."""
import datetime as dt
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "12_SCRIPTS" / "morning_brief.py"


def load_module(status_dir: Path, max_age_s: str = "1200"):
    os.environ["NEEWA_STATUS_DIR"] = str(status_dir)
    os.environ["NEEWA_SNAPSHOT_MAX_AGE_S"] = max_age_s
    spec = importlib.util.spec_from_file_location("morning_brief", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def write_snapshot(status_dir: Path, *, age_s: int = 0, services: dict | None = None,
                   omit_generated_at: bool = False, malformed: bool = False,
                   repository: dict | None = None):
    status_dir.mkdir(parents=True, exist_ok=True)
    path = status_dir / "latest.json"
    if malformed:
        path.write_text("{not json", encoding="utf-8")
        return path
    ts = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=age_s)
    payload = {
        "services": services if services is not None else {
            "hermes_gateway": "active", "docker": "active",
            "tailscaled": "active", "ollama": "active",
        },
        "repository": repository or {"branch": "main", "head": "abc1234", "state": "clean"},
        "provider": {"primary_model": "openai/gpt-5.6-luna", "provider": "nous", "fallback_entries": 1},
    }
    if not omit_generated_at:
        payload["generated_at"] = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class MorningBriefTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.status_dir = Path(self.tmp.name) / "status"

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, mod):
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = mod.main()
        return code, buf.getvalue()

    def test_sandbox_fresh_snapshot_all_active_passes(self):
        write_snapshot(self.status_dir, age_s=10)
        mod = load_module(self.status_dir)
        # Force sandbox mode regardless of the machine running the test.
        mod.on_host = lambda: False
        code, out = self.run_main(mod)
        self.assertEqual(code, 0, out)
        self.assertIn("Context: sandbox", out)
        self.assertIn("hermes_gateway=active", out)
        self.assertIn("fresh", out)

    def test_missing_snapshot_reports_unavailable_and_fails(self):
        mod = load_module(self.status_dir)
        mod.on_host = lambda: False
        code, out = self.run_main(mod)
        self.assertEqual(code, 1)
        self.assertIn("UNAVAILABLE", out)
        # Unknown services must not be reported active.
        self.assertIn("hermes_gateway=unknown", out)

    def test_malformed_snapshot_reports_unavailable_and_fails(self):
        write_snapshot(self.status_dir, malformed=True)
        mod = load_module(self.status_dir)
        mod.on_host = lambda: False
        code, out = self.run_main(mod)
        self.assertEqual(code, 1)
        self.assertIn("malformed", out.lower())

    def test_stale_snapshot_treated_as_unknown_and_fails(self):
        write_snapshot(self.status_dir, age_s=5000)  # older than default 1200s
        mod = load_module(self.status_dir)
        mod.on_host = lambda: False
        code, out = self.run_main(mod)
        self.assertEqual(code, 1)
        self.assertIn("STALE", out)
        self.assertIn("hermes_gateway=unknown", out)

    def test_partial_snapshot_missing_service_is_unknown_not_healthy(self):
        write_snapshot(self.status_dir, age_s=10, services={"hermes_gateway": "active", "docker": "active"})
        mod = load_module(self.status_dir)
        mod.on_host = lambda: False
        code, out = self.run_main(mod)
        self.assertEqual(code, 1)  # tailscaled/ollama unknown -> not all active
        self.assertIn("tailscaled=unknown", out)
        self.assertIn("ollama=unknown", out)

    def test_inactive_service_fails(self):
        write_snapshot(self.status_dir, age_s=10, services={
            "hermes_gateway": "active", "docker": "active",
            "tailscaled": "active", "ollama": "inactive"})
        mod = load_module(self.status_dir)
        mod.on_host = lambda: False
        code, out = self.run_main(mod)
        self.assertEqual(code, 1)
        self.assertIn("ollama=inactive", out)

    def test_snapshot_without_timestamp_is_stale(self):
        write_snapshot(self.status_dir, omit_generated_at=True)
        mod = load_module(self.status_dir)
        mod.on_host = lambda: False
        code, out = self.run_main(mod)
        self.assertEqual(code, 1)
        self.assertIn("STALE", out)

    def test_never_invokes_host_binaries_in_sandbox(self):
        # If the code tried systemctl/swapon, it would import subprocess.run;
        # assert the sandbox path produces a brief without raising even when
        # host binaries are absent (simulated by sandbox mode).
        write_snapshot(self.status_dir, age_s=10)
        mod = load_module(self.status_dir)
        mod.on_host = lambda: False
        called = {"run": False}
        real_run = mod.subprocess.run
        def guard(*a, **k):
            called["run"] = True
            return real_run(*a, **k)
        mod.subprocess.run = guard
        code, _ = self.run_main(mod)
        self.assertEqual(code, 0)
        self.assertFalse(called["run"], "sandbox path must not shell out")


if __name__ == "__main__":
    unittest.main()
