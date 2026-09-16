# NEEWA Jarvis V1 — Acceptance

Updated 2026-09-16 16:50 America/New_York after the Home/voice integration patch.
Physical speech/speaker gates are **not** PASS.

## Environment

- Git: see RELEASE_REPORT for HEAD after this push.
- Desktop: packed `Hermes.exe` rebuilt from local Hermes source branch `neewa/keep-chat-mounted` (keep ChatView mounted). Plugin at `%LOCALAPPDATA%\hermes\desktop-plugins\neewa-command-center\`.
- Remote: Tailscale SSH `ubuntu@neewa-core-01`. No Serve/Funnel.
- Wake: `start_new_session=false`, capture=client, aliases hey niva/neeva/neva.
- TTS: **nous / coral**, `voice.auto_tts=true`, mode **chained**.
- STT: local faster-whisper **base**, language **en**. Hindi/Marathi not verified.
- GPT-Live: off. Direct OpenAI key: unconfigured.

## Root cause (owner-facing)

Wake detection was real. NEEWA Home is a plugin route. Hermes 0.21.3 **unmounted** the only composer that owns STT/TTS when that route was active. The plugin then navigated to `#/` (`NEW_CHAT_ROUTE`), which is New Chat — that is why the generic Conversation screen appeared and extra sessions were created. MIC OFF after wake was a badge bug (listener pause ≠ mute).

## Gates

| ID | Status | Evidence |
| --- | --- | --- |
| A01 login autostart | PENDING_PHYSICAL | Startup shortcut exists. |
| A02 private backend | PASS | Source neewa / Tailscale SSH. No Funnel. |
| A03 no-click arm | PASS (infra) / PENDING_PHYSICAL | wake.start gui + client capture. |
| A04 wake phrase | PENDING_PHYSICAL | Do not pass from screenshots alone. |
| A05 speech → remote task on **Home** | PENDING_PHYSICAL | Keep-mounted ChatView + plugin no longer navigates to `/`. Spoken confirm remaining. |
| A06 3 continuous turns same session | PENDING_PHYSICAL | `start_new_session=false`; wake no longer mints a draft unless explicitly true. |
| A07 chosen voice on speakers | PENDING_PHYSICAL | auto_tts true, nous coral. Unmute speaker icon. |
| A08 stop | PASS (infra) / PENDING_PHYSICAL | Stop = voice.toggle off + interrupt + rearm. |
| A09 NEEWA Home owns voice UI | PASS (infra) | Home stays the route; composer stays mounted hidden. Conversation is optional. |
| A10 honest states | PASS (infra) | Missing `audio_silent` + no PCM frames = UNKNOWN, not READY. |
| A11 HUD | PASS (infra) | In-app HUD = compact overlay of the same identity. Native Ctrl+Shift+H is a separate window. |
| A12 CoS task | PENDING_PHYSICAL | |
| A13 operational data | PASS (infra) | Jobs/model/privacy labels. |
| A14 persistence | PARTIAL | personalSessionId localStorage pin. Restart of packed asar not spoken-tested. |
| A15 budget/fallback | PASS | Chained; GPT-Live off; Edge fallback remains. |
| A16 security | PASS | No public listener; secret scan 0; worker allowlisted; employer files UNSUPPORTED. |
| A17 installer | PARTIAL | Plugin + Desktop asar patched locally. ZIP not rebuilt this turn. |
| A18 source/test | PASS pending this push | 60 tests, 1 skipped; secret scan 0. |
| A19 workday | PENDING_PHYSICAL | Owner must quit/relaunch packed Hermes and speak on Home. |

## Release decision

**PARTIAL.** Home now owns the voice controller in software. Not ACCEPTED until the owner spoken session on Home passes (wake, three turns, audible reply, Stop, rearm).
