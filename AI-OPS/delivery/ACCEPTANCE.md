# NEEWA Jarvis V1 — Acceptance

Updated 2026-09-16 17:20 America/New_York after Home voice-handoff repair.
Physical speech/speaker gates are **not** PASS. Windows remote-to-local artifact remains PASS.

## Environment

- Git: see RELEASE_REPORT for HEAD after this push.
- Desktop: packed `Hermes.exe` rebuilt from local Hermes source branch `neewa/keep-chat-mounted`. Running renderer `--app-path` is `release\win-unpacked\resources\app.asar` (SHA256 `C3AF7E22…1B1EE`, 62 967 237 bytes, 2026-09-16 17:18). Backup `app.asar.bak-neewa-20260916T171702`.
- Plugin: `%LOCALAPPDATA%\hermes\desktop-plugins\neewa-command-center\plugin.js` SHA256 `5175E80F…CD3AD7` matches repo source.
- Remote: Tailscale SSH `ubuntu@neewa-core-01`. No Serve/Funnel. Latest packed launch: backend ready 2026-09-16T21:19:22Z.
- Wake: `start_new_session=false`, capture=client, aliases hey niva/neeva/neva.
- TTS: **nous / coral**, `voice.auto_tts=true`, mode **chained**.
- STT: local faster-whisper **base**, language **en**.
- GPT-Live: off.

## Root cause (owner-facing)

Wake detection was real. Conversation worked because ChatView was visible. Home failed because:

1. The plugin set **MIC LIVE** from `wake.detected` / `wake.pause` without a recording start acknowledgment.
2. `startListening()` dispatched unacked `hermes:composer-voice-toggle` (a toggle — it can stop an already-started conversation) and notified success immediately.
3. The keep-mounted ChatView used `visibility:hidden`, which is the Conversation-vs-Home difference Chromium can use to starve capture/TTS.

Fix: cover ChatView instead of hiding it; Home/HUD subscribe to `window.__NEEWA_VOICE__`; MIC LIVE only when `recording === true`.

## Gates

| ID | Status | Evidence |
| --- | --- | --- |
| A01 login autostart | PENDING_PHYSICAL | Startup shortcut exists. |
| A02 private backend | PASS | Packed launch 21:19Z remote backend ready. No Funnel. |
| A03 no-click arm | PASS (infra) / PENDING_PHYSICAL | wake.start gui + client capture. |
| A04 wake phrase | PENDING_PHYSICAL | One consolidated spoken Home session remaining. |
| A05 speech → remote task on **Home** | PENDING_PHYSICAL | Overlay composer + `__NEEWA_VOICE__.start` ack. Spoken confirm remaining. |
| A06 3 continuous turns same session | PENDING_PHYSICAL | Personal session pin/reuse; no navigate to `/`. |
| A07 chosen voice on speakers | PENDING_PHYSICAL | auto_tts true, nous coral. Unmute speaker icon. |
| A08 stop | PASS (infra) / PENDING_PHYSICAL | Stop calls controller.stop and only notifies after ok; then rearm. |
| A09 NEEWA Home owns voice UI | PASS (infra) | Home stays the route; ChatView `mounted-overlay` (not CSS-hidden). |
| A10 honest states | PASS (infra) | MIC LIVE requires recording. Missing audio_silent = UNKNOWN. |
| A11 HUD | PASS (infra) | Same controller as Home. |
| A12 CoS task | PENDING_PHYSICAL / PARTIAL | Spoken CoS pending. JOB-20260916-004 worker PASS. |
| A13 operational data | PASS (infra) | Jobs/model/privacy labels. Approvals uses pinned/stored session when runtime focus is empty. |
| A14 persistence | PARTIAL | Packed asar loaded by running process this turn. Spoken restart untested. |
| A15 budget/fallback | PASS | Chained; GPT-Live off. |
| A16 security | PASS | Secret scan 0; no public listener; worker allowlisted. |
| A17 installer | PARTIAL | Plugin + Desktop asar patched locally. ZIP not rebuilt. |
| A18 source/test | PASS pending this push | 67 unittest OK + 1 skip; Hermes vitest 8 passed; validate secret_scan 0. |
| A19 workday | PENDING_PHYSICAL | One Home spoken session after this relaunch. |

## Windows computer-use gates

| ID | Status | Evidence |
| --- | --- | --- |
| CUA_INSTALLATION | PASS | cua-driver 0.28.2 |
| CUA_DOCTOR | PASS | `cua-driver doctor --json` ok this turn (session 2 interactive). |
| CUA_DAEMON | PASS | Named pipe / interactive desktop. |
| WINDOWS_APPLICATION_DISCOVERY | PASS | Prior list_windows / Calculator UIA. |
| REAL_CALCULATOR_TEST | PASS | Prior 6 × 7 → Display is 42. |
| LOCAL_HERMES_COMPUTER_USE | PASS | Prior local `hermes chat -t computer_use`. |
| PRIVATE_WINDOWS_WORKER | PASS | Outbound SSH poll; mutex; allowlist. |
| REMOTE_NEEWA_DELEGATION | PASS | JOB-20260916-004 complete. |
| ACTUAL_LOCAL_ARTIFACT | PASS | `%USERPROFILE%\NEEWA-Personal\jobs\JOB-20260916-004-personal-artifact.txt` |
| PERMISSION_BOUNDARIES | PASS | Shell and A3 FAILED; employer files UNSUPPORTED. |
| STARTUP_RECOVERY | PARTIAL | Packed Hermes relaunch this turn recovered SSH. Reboot/sleep untested. |
| SECURITY | PASS | No Funnel; secrets not committed. |
| GIT_SYNCHRONIZATION | pending this push | |

## Evidence matrix

| ID | Status | Notes |
| --- | --- | --- |
| HOME_STAYS_VISIBLE | PASS (infra) | Overlay cover; no navigate to `/`. PENDING_PHYSICAL for spoken stay-on-Home. |
| VOICE_EVENT_ACKNOWLEDGED | PASS (infra) | `__NEEWA_VOICE__.start` waits for recording. |
| MIC_RECORDING_STARTED | PENDING_PHYSICAL | Controller publishes only on `conversation.status === 'listening'`. |
| TRANSCRIPT_RECEIVED | PENDING_PHYSICAL | |
| REMOTE_AGENT_RESPONDED | PENDING_PHYSICAL | |
| AUDIO_PLAYED | PENDING_PHYSICAL | |
| SESSION_REUSED | PASS (infra) | `ensurePersonalVoiceSession` + pin. PENDING_PHYSICAL for three turns. |
| THREE_TURN_CONTINUITY | PENDING_PHYSICAL | |
| STOP_WORKS | PASS (infra) / PENDING_PHYSICAL | No unconditional success. |
| REARM_WORKS | PASS (infra) / PENDING_PHYSICAL | Rearm only after accepted `wake.start`. |
| WINDOWS_WORKER | PASS | |
| REMOTE_LOCAL_DELEGATION | PASS | |
| SECURITY | PASS | |
| GIT_SYNCHRONIZED | pending this push | |

## Release decision

**PARTIAL.** Do not report complete until the owner speaks to NEEWA from Home and hears a reply while Home stays visible.

**PENDING_PHYSICAL — one consolidated test:** Stay on Home after this packed relaunch. Wait for READY. Say **Hey Neewa, are you there?** then two follow-ups. Confirm MIC LIVE only while speaking, audible reply, Stop, Rearm. Do not switch to Conversation.
