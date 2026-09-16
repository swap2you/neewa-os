import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "16_WINDOWS_CLIENT" / "assets" / "neewa-command-center" / "plugin.js"


class NeewaHomePluginTests(unittest.TestCase):
    def setUp(self):
        self.src = PLUGIN.read_text(encoding="utf-8")

    def test_product_routes_registered(self):
        self.assertIn("'/neewa-home'", self.src)
        self.assertIn("'/neewa-hud'", self.src)
        self.assertIn("area: ROUTES", self.src)
        self.assertIn("SIDEBAR_NAV", self.src)

    def test_wake_controls_use_supported_rpc(self):
        self.assertIn("wake.status", self.src)
        self.assertIn("wake.stop", self.src)
        self.assertIn("wake.start", self.src)
        self.assertIn("cron.manage", self.src)
        self.assertIn("config.get", self.src)

    def test_no_secret_material(self):
        lower = self.src.lower()
        self.assertNotIn("sk-", self.src)
        self.assertNotIn("api_key=", lower)
        self.assertNotIn("voice_tools_openai_key", lower)
        self.assertNotIn("begin private key", lower)

    def test_privacy_and_hud_surfaces(self):
        self.assertIn("MIC OFF", self.src)
        self.assertIn("Open HUD", self.src)
        self.assertIn("hermesDesktop", self.src)
        self.assertIn("prefers-reduced-motion", self.src)

    def test_no_public_bind(self):
        self.assertNotIn("0.0.0.0", self.src)
        self.assertNotIn("tailscale funnel", self.src.lower())


if __name__ == "__main__":
    unittest.main()
