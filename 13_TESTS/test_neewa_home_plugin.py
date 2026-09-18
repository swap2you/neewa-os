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
        self.assertIn("session.interrupt", self.src)
        self.assertIn("wake.pause", self.src)
        self.assertIn("__NEEWA_VOICE__", self.src)
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
        self.assertIn("voiceApi()", body)
        self.assertIn("api.start", body)
        self.assertIn("result.recording", body)
        self.assertNotIn("hermes:composer-voice-toggle", body)
        self.assertNotIn("voice.record", body)
        self.assertNotIn("NEEWA is listening on Home", body)
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
        self.assertIn("Close HUD", self.src)
        self.assertIn("Go Home", self.src)
        self.assertIn("closeHudSurface", self.src)
        self.assertIn("keepChatMounted", self.src)
        self.assertIn("openTranscript", self.src)
        self.assertIn("neewa.personalSessionId", self.src)
        self.assertIn("audioSilentKnown", self.src)
        self.assertIn("__NEEWA_WAKE_HEALTH__", self.src)
        self.assertIn("__NEEWA_VOICE__", self.src)
        self.assertIn("hermes:neewa-voice", self.src)
        self.assertIn("hermes:neewa-clap", self.src)
        self.assertNotIn("ensureConversationAfterWake", self.src)
        self.assertIn("conversational", self.src)
        self.assertIn("hermesDesktop", self.src)
        self.assertIn("prefers-reduced-motion", self.src)
        self.assertIn("Recording did not start", self.src)
        self.assertNotIn("Wake detected · listening", self.src)

    def test_home_does_not_navigate_to_new_chat_on_wake_or_listen(self):
        start = self.src.index("async function startListening")
        end = self.src.index("async function stopConversation")
        body = self.src[start:end]
        self.assertNotIn("host.navigate('/'", body)
        self.assertNotIn('host.navigate("/")', body)
        self.assertIn("Do NOT navigate to '/'", self.src)
        self.assertIn("NEW_CHAT_ROUTE", self.src)

    def test_ready_requires_positive_audio_evidence(self):
        derive_start = self.src.index("function derivePersona")
        derive_end = self.src.index("function usePersonaState")
        body = self.src[derive_start:derive_end]
        self.assertIn("audioSilentKnown", body)
        self.assertIn("pcmFrames", body)
        self.assertIn("return 'unknown'", body)
        self.assertNotRegex(body, r"if \(wake\.audioSilent\) return 'stream_inactive'\s+if \(wake\.armedAt")

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

    def test_mic_live_requires_recording_not_wake_detect(self):
        badge_start = self.src.index("function PrivacyBadge")
        badge_end = self.src.index("function CommandRail")
        badge = self.src[badge_start:badge_end]
        self.assertIn("persona === 'listening' || persona === 'transcribing'", badge)
        self.assertNotIn("persona === 'detected') { label = 'MIC LIVE'", badge)
        self.assertIn("label = 'WAKE'", badge)
        start = self.src.index("async function startListening")
        end = self.src.index("async function stopConversation")
        body = self.src[start:end]
        self.assertIn("result.recording", body)
        self.assertNotIn("host.notify({ kind: 'info', message: 'NEEWA is listening on Home", body)

    def test_no_public_bind(self):
        self.assertNotIn("0.0.0.0", self.src)
        self.assertNotIn("tailscale funnel", self.src.lower())

    def test_mission_panel_does_not_bypass_authorization(self):
        self.assertIn("function MissionPanel", self.src)
        self.assertIn("Submit engineering objectives through Conversation", self.src)
        self.assertIn("Home does not bypass authorization", self.src)
        self.assertIn("__NEEWA_MISSION_SNAPSHOT__", self.src)
        self.assertIn("neewa.mission.submit", self.src)
        self.assertIn("window.hermesDesktop && window.hermesDesktop.neewa", self.src)
        self.assertIn("submitMission", self.src)
        self.assertIn("missionStatus", self.src)
        self.assertIn("hermes:neewa:mission", Path(__file__).resolve().parents[1].joinpath("16_WINDOWS_CLIENT", "hermes-desktop-patches", "electron", "neewa-mission-ipc.ts").read_text(encoding="utf-8"))
        self.assertIn("Submit mission", self.src)
        self.assertIn("This text does not grant A2/A3", self.src)
        self.assertIn("captureUiIncident", self.src)
        self.assertIn("privileged: false", self.src)
        self.assertNotIn("owner_decision: 'approved'", self.src)


if __name__ == "__main__":
    unittest.main()
