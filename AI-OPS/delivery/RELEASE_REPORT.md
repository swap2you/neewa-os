# NEEWA Jarvis V1 — release report

**Product status:** PARTIAL (Windows computer-use worker proven; physical spoken session still required)
**Report date/time + timezone:** 2026-09-16 17:10 America/New_York
**Repo:** `swap2you/neewa-os`
**Commit SHA:** see git after this push
**Architecture:** NEEWA on `neewa-core-01` coordinates. `neewa-edge-01` runs cua-driver 0.28.2 in the interactive desktop session plus an outbound Tailscale SSH worker. Cursor is the Git writer.

## Windows computer-use (this turn)

`cua.ai` is NXDOMAIN. Official GitHub `install.ps1` SHA256 `3e770fa8c351b80db99ae6b080f696a22f844534498bf44d45816cbd05eb0c3f` was run from disk beside `_install-common.psm1` so the installer never called cua.ai. Zip `cua-driver-rs-0.28.2-windows-x86_64.zip` SHA256 `3c1fcf10ff9513b94e4af78ad6a216ab62aa95b2c9a3b70dfbdba9f04e021533`.

Calculator test: background UIA, Display is 42, only Calculator closed. Local Hermes `computer_use` listed windows (session `20260916_170630_c254b7`) against the Windows driver, not Ubuntu. Remote job JOB-20260916-004 wrote `%USERPROFILE%\NEEWA-Personal\jobs\JOB-20260916-004-personal-artifact.txt`. Shell and A3 probes returned FAILED.

Cua MCP was generated for Cursor/Claude/Codex and **not** merged. Claude Code CLI and Codex CLI are not on PATH (GUIs exist).

---

# NEEWA Jarvis V1 — release report (Home owns voice)

**Product status:** PARTIAL (Home/voice integration patched; physical spoken session still required)
**Report date/time + timezone:** 2026-09-16 16:50 America/New_York
**Repo:** `swap2you/neewa-os`
**Commit SHA:** `f3260a8635aba46399cb81142f03b2da8561ec1b`
**Hermes Desktop branch (local only, not Nous origin):** `neewa/keep-chat-mounted` from `2cfb655`
**Windows packed asar:** replaced `release/win-unpacked/resources/app.asar` (backup `app.asar.bak-neewa-20260916T164627`)
**Plugin SHA256:** `640EF675929E7A9F06C4FDE06D970C9D475FB5974421CBB3BD8D81AEA2FBC219`

## Root cause

1. **Route ownership.** `wake.detected` is handled in Hermes `wiring.tsx`. It latches `requestVoiceConversationStart()`. That latch is consumed only by the mounted main `ChatBar`. Plugin routes (`#/neewa-home`) previously **replaced** ChatView, so STT never started while Home was visible.
2. **Plugin workaround made it worse.** `ensureConversationAfterWake` and `startListening` navigated to `#/` which is `NEW_CHAT_ROUTE`. That is the generic Conversation screen and it **nulls** the selected session, minting extra chats.
3. **MIC OFF** after wake was `!wake.listening` during the post-detect pause, not a closed microphone.
4. **No spoken replies** previously also had `voice.auto_tts=false` (already set true this afternoon). Speaker mute in the composer still silences TTS.

## What changed

| Area | Change |
| --- | --- |
| Hermes Desktop | Keep ChatView mounted for the workspace pane lifetime; overlay Home/HUD. Wake mints a new session only if `start_new_session === true`. PCM counters on `window.__NEEWA_WAKE_HEALTH__`. Optional double-clap on the **same** ScriptProcessor, off unless `localStorage.neewa.doubleClap=1`. |
| Plugin | Stay on Home. No navigate to `/`. Pin `neewa.personalSessionId`. READY requires `audio_silent === false` or PCM frames. HUD is in-app overlay. Conversation opens the pinned transcript, not New Chat. |
| Worker | Capability inventory + one allowlisted personal artifact under `%USERPROFILE%\NEEWA-Personal\jobs\`. |
| Docs | PROJECT_REGISTRY honesty; RUNBOOK; this report. |

## Session routing (actual)

- Gateway emits `wake.detected` with `start_new_session: false`.
- Desktop no longer calls `startFreshSessionDraft()` unless that flag is **true**.
- Home path remains `#/neewa-home`. ChatView is `visibility:hidden` but mounted (`data-neewa-chat-layer=mounted-hidden`).
- Composer `queueSessionKey` uses store selection on non-chat routes (`primaryRouteSelectedSessionId` falls through).
- Optional Conversation view navigates to `/{focusedStoredSessionId}` when pinned.

## Latency

No p50/p95: physical sample size is 0 this turn. Pipeline remains chained: wake → getUserMedia conversation → local faster-whisper base → agent → nous coral TTS → Windows playback.

Removed avoidable delay:

- Route remount of ChatBar (seconds + lost capture).
- `startListening` 280ms navigate-to-`/` (now 80ms toggle on the already-mounted composer).

Do not enable GPT-Live to hide chained cost. STT language is `en`; do not assume Marathi accuracy.

## Capability inventory

See `16_WINDOWS_CLIENT/worker/capability_inventory.json`.

| Name | Status |
| --- | --- |
| Git | AVAILABLE (2.50.0) |
| Cursor CLI | AVAILABLE (3.17.8) — Cursor remains Git writer |
| Codex CLI | NOT INSTALLED |
| GitHub CLI | AVAILABLE (authenticated) |
| Tailscale | AVAILABLE |
| OpenSSH | AVAILABLE |
| Personal workspace | AVAILABLE (`%USERPROFILE%\NEEWA-Personal`) |
| Employer files / raw shell / public listener | UNSUPPORTED |

Real artifact: `C:\Users\swap2\NEEWA-Personal\jobs\JOB-20260916T164408-personal-artifact.txt`

## Double clap

Implemented on the existing wake ScriptProcessor. **Disabled by default.** Discrimination against speech is conservative and unproven; wake phrase + Start listening remain primary.

## Tests

- `python -m unittest discover -s 13_TESTS -p test_*.py`: 60 OK, 1 skipped.
- Hermes `surfaces.test.tsx` + `surfaces.late-routes.test.tsx`: 2 passed.
- Secret scan: 0 findings.

## Security

- No additional public listeners.
- No keys in plugin/JS/ZIP/chat.
- Sandbox mounts unchanged (repo/status RO).
- Worker is allowlisted scripts only.

## Owner-only action (unavoidable)

1. Fully quit packed `Hermes.exe`.
2. Relaunch `...\apps\desktop\release\win-unpacked\Hermes.exe`.
3. Unmute the **speaker** icon in the bottom bar if it is muted.
4. Stay on **NEEWA Home**. Wait for READY (not UNKNOWN).
5. Say **Hey Neewa, are you there?** then two follow-ups without opening Conversation.
6. Confirm the orb stays on Home (listening → thinking → speaking) and the reply is audible.
7. Stop; confirm wake re-arms.

If Home still jumps to Conversation, the packed asar did not load — restore `app.asar.bak-neewa-20260916T164627` and report.

## Final statement

**PARTIAL.** The required product is NEEWA Home owning the complete voice experience. Software now keeps Home visible and the composer alive. Spoken acceptance is still the owner's.
