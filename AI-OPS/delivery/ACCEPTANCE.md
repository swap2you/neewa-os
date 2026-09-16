# NEEWA Jarvis V1 — Acceptance

Updated 2026-09-16 17:10 America/New_York after Windows computer-use + worker integration.
Physical speech/speaker gates are **not** PASS. Windows remote-to-local artifact is PASS.

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
| A12 CoS task | PENDING_PHYSICAL / PARTIAL | Spoken CoS still pending. Governed Windows job JOB-20260916-004 completed via worker. |
| A13 operational data | PASS (infra) | Jobs/model/privacy labels. |
| A14 persistence | PARTIAL | personalSessionId localStorage pin. Restart of packed asar not spoken-tested. |
| A15 budget/fallback | PASS | Chained; GPT-Live off; Edge fallback remains. |
| A16 security | PASS | No public listener; secret scan 0; worker allowlisted; employer files UNSUPPORTED; A3 Windows job FAILED as required. |
| A17 installer | PARTIAL | Plugin + Desktop asar patched locally. Cua Driver installed via GitHub-local official script. ZIP not rebuilt this turn. |
| A18 source/test | PASS pending this push | unittest + secret scan this turn. |
| A19 workday | PENDING_PHYSICAL | Owner must quit/relaunch packed Hermes and speak on Home. |

## Windows computer-use gates

| ID | Status | Evidence |
| --- | --- | --- |
| CUA_INSTALLATION | PASS | cua-driver 0.28.2 from GitHub zip; install.ps1 SHA256 `3e770fa8…eb0c3f`; cua.ai NXDOMAIN workaround documented. |
| CUA_DOCTOR | PASS | `cua-driver doctor --json` ok; `hermes computer-use doctor` ok on win32. |
| CUA_DAEMON | PASS | Interactive session 2 named pipe `\\.\pipe\cua-driver`; telemetry disabled. |
| WINDOWS_APPLICATION_DISCOVERY | PASS | `list_windows` / Calculator UIA tree 39 elements. |
| REAL_CALCULATOR_TEST | PASS | Background 6 × 7, accessibility `Display is 42`; only Calculator closed. |
| LOCAL_HERMES_COMPUTER_USE | PASS | Local `hermes chat -q -t computer_use` session `20260916_170630_c254b7` listed windows; remote brain was not this session. |
| CURSOR_INTEGRATION | PASS | Cursor CLI 3.17.8; cua MCP preview **not** merged (single execution owner). |
| CLAUDE_CODE_INTEGRATION | NOT INSTALLED | Store GUI present; `claude` CLI absent. Not a failure. |
| CODEX_INTEGRATION | NOT INSTALLED | Extension binary present; `codex` CLI not on PATH. Not a failure. |
| PRIVATE_WINDOWS_WORKER | PASS | Outbound SSH poll; mutex; allowlist. |
| REMOTE_NEEWA_DELEGATION | PASS | Inbox on neewa-core-01 workspace; JOB-20260916-004 complete. |
| ACTUAL_LOCAL_ARTIFACT | PASS | `%USERPROFILE%\NEEWA-Personal\jobs\JOB-20260916-004-personal-artifact.txt` |
| PERMISSION_BOUNDARIES | PASS | Shell and A3 jobs FAILED; bounded manifest denied click + desktop capture; AFH not granted. |
| STARTUP_RECOVERY | PARTIAL | HKCU Run registered; driver stop/start recovered; reboot/sleep not tested. |
| SECURITY | PASS | No Funnel; no public port; no YOLO computer_use; secrets not committed. |
| GIT_SYNCHRONIZATION | pending this push | |

## Release decision

**PARTIAL.** Windows remote-to-local worker is proven. Product is still not ACCEPTED until the owner spoken session on Home passes (wake, three turns, audible reply, Stop, rearm).
