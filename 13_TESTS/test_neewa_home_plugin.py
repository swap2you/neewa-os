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
        self.assertIn("voice.toggle", self.src)
        self.assertIn("session.interrupt", self.src)
        self.assertIn("wake.pause", self.src)
        self.assertIn("hermes:composer-voice-toggle", self.src)
        self.assertIn("startListening", self.src)
        self.assertIn("Start listening", self.src)
        self.assertIn("approval.pending", self.src)
        self.assertNotIn("host.request('config.get'", self.src)
        self.assertNotIn("stopAndRearm", self.src)

    def test_backup_listen_uses_desktop_conversation_not_server_record(self):
        start = self.src.index("async function startListening")
        end = self.src.index("async function stopConversation")
        body = self.src[start:end]
        self.assertIn("wake.pause", body)
        self.assertIn("hermes:composer-voice-toggle", body)
        self.assertNotIn("voice.record", body)
        self.assertIn("Start listening", self.src)

    def test_wake_aliases_and_negatives(self):
        self.assertIn("hey niva", self.src)
        self.assertIn("hey neeva", self.src)
        self.assertIn("hey neva", self.src)
        self.assertNotIn("hey nina", self.src)
        self.assertNotIn("hey nio", self.src)

    def test_telemetry_labels_are_honest(self):
        self.assertIn("telemetry unavailable", self.src)
        self.assertIn("verified", self.src)
        self.assertIn("service unavailable", self.src)

    def test_no_secret_material(self):
        lower = self.src.lower()
        self.assertNotIn("sk-", self.src)
        self.assertNotIn("api_key=", lower)
        self.assertNotIn("voice_tools_openai_key", lower)
        self.assertNotIn("begin private key", lower)

    def test_privacy_and_hud_surfaces(self):
        self.assertIn("MIC OFF", self.src)
        self.assertIn("READY", self.src)
        self.assertIn("NO AUDIO", self.src)
        self.assertIn("Open HUD", self.src)
        self.assertIn("hermesDesktop", self.src)
        self.assertIn("prefers-reduced-motion", self.src)

    def test_wake_states_are_not_optimistic(self):
        self.assertIn("audio_silent", self.src)
        self.assertIn("stream_inactive", self.src)
        self.assertIn("useCaptureProbe", self.src)
        self.assertIn("enumerateDevices", self.src)
        self.assertIn("NEVER open getUserMedia", self.src)
        self.assertIn("armedAt", self.src)
        self.assertIn("iriun", self.src.lower())
        self.assertIn("return 'unknown'", self.src)
        self.assertNotIn("useState('armed')", self.src)
        self.assertNotIn("getUserMedia({", self.src)

    def test_no_public_bind(self):
        self.assertNotIn("0.0.0.0", self.src)
        self.assertNotIn("tailscale funnel", self.src.lower())


if __name__ == "__main__":
    unittest.main()
