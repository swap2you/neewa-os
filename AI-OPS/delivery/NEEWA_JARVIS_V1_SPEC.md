# NEEWA Jarvis V1 — Delivery Spec (verified truth)

Updated 2026-09-16 from installed Hermes 0.21.3 + this repo (HEAD is not pinned;
confirm `git rev-parse HEAD`).

## Architecture

- **Windows PC:** Hermes Desktop is the face (mic, speakers, NEEWA Home/HUD).
  Cursor is the sole Git writer, installer, and release owner.
- **`neewa-core-01`:** remote Hermes brain over Tailscale SSH. Sherpa wake,
  faster-whisper STT, TTS, jobs, memory. Docker repo/status mounts stay
  read-only.

## Product surfaces

Plugin: `16_WINDOWS_CLIENT/assets/neewa-command-center/plugin.js`

| Surface | How |
| --- | --- |
| NEEWA Home `/neewa-home` | ROUTES_AREA; cold-start navigation from `/` |
| Compact HUD `/neewa-hud` | In-app slim Home |
| Native HUD | Installed `hermesDesktop.hud.open` / `Ctrl+Shift+H` — movable always-on-top chat overlay; re-opens the main window on close |
| Sidebar / palette / chip | NEEWA Home, NEEWA HUD, `Ctrl+Alt+N` |

**Persona:** original abstract feminine-coded luminous presence (canvas). Motion
binds to `host.state`, `wake.status`, and `host.onEvent` (wake/stt/tts). Idle
breath only; reduced-motion is a still. No lip-sync claim, no fabricated metrics.

**Controls:** Mute (`wake.stop`), Stop (stop then rearm), Rearm (`wake.start`
surface=gui, client_capture). Privacy badge: MIC OFF / LIVE / ARMED.

## Wake / voice

- Phrase `hey neewa`, Sherpa, `surface=gui`, `capture=client`.
- Auto-arm on gateway ready (Desktop `armWakeWord`). `start_new_session=false`.
- Chained voice. GPT-Live deferred (needs owner budget).
- TTS: Edge fallback; OpenAI available if `VOICE_TOOLS_OPENAI_KEY` is present
  on the server — owner picks the voice at acceptance. See
  `VOICE_PROVIDER_MATRIX.md`.

## Chief of Staff

Voice intents and job states: `CHIEF_OF_STAFF.md`. Durable jobs live under
`04_MEMORY/jobs/`. A2/A3 gates stay intact.
