# NEEWA Jarvis V1 — release report

**Product status:** PARTIAL
**Report date/time + timezone:** 2026-09-16 12:40 America/New_York
**Repo:** `swap2you/neewa-os` (local origin `https://github.com/swap2you/neewa-os.git`)
**Commit SHA (local / origin/main / server):** recorded after push; pre-push HEAD was `39e3a28` on all three.
**Windows app + Hermes backend versions:** Hermes Desktop 0.21.3 (packed `win-unpacked\Hermes.exe`); server Hermes via `/home/ubuntu/.local/bin/hermes`.
**Environment:** Windows PC `neewa-edge-01`, `neewa-core-01` private Tailscale, authorized only.

## Actual outcome and owner usage

After Windows sign-in, Hermes Desktop auto-starts from the Startup shortcut. It reconnects to the primary SSH gateway **neewa**. The running UI lands on **NEEWA Home** (`#/neewa-home`): original teal persona, “Ready · listening for Hey Neewa”, MIC ARMED, Mute / Stop / Rearm / Open HUD. Say **Hey Neewa**, then speak. Compact in-app HUD is the sidebar item **NEEWA HUD**; native movable overlay is **Ctrl+Shift+H**. Chat remains backup.

This is **not** ACCEPTED: the owner has not yet witnessed post-login autostart, three no-click spoken turns, the chosen premium voice through speakers, or a voice-created job. Edge Aria remains the live TTS until that audition.

## Evidence table

See `ACCEPTANCE.md` for A01–A19. Screenshot of the running Home (not committed; personal desktop chrome):
`%LOCALAPPDATA%\NEEWA\Handoff\JarvisV1_20260916_123313\evidence\neewa-home-desktop.png`.
desktop.log shows `#/neewa-home`. Host: `/opt/neewa/status/latest.json` 2026-09-16T16:29:17Z overall ok. Voice: 2026-09-16T16:33:48Z `voice_pipeline_observed_working`. Wake auto-arm: `wake.start(gui)` 12:21:19 capture=client.

## NEEWA collaboration

Work orders: `AI-OPS/delivery/work-orders/WO-20260916-jarvis-v1.md` and
`WO-20260916-jarvis-v1-review.md`. Cursor writes Git; NEEWA is asked to read those
paths after host `git pull`. Host snapshots are layer-B (Lightsail), not the
container hostname. `/opt/neewa/status` mount is read-only.

## Rollback and release

- Plugin/UI: `git revert` then copy `plugin.js` to `%LOCALAPPDATA%\hermes\desktop-plugins\neewa-command-center\`.
- Wake continuity: `hermes config set wake_word.start_new_session true`.
- Windows client: `16_WINDOWS_CLIENT/Uninstall-NEEWA-Client.ps1`.
- Bootstrap ZIP SHA256: `e76fc87f25881f401d724b62d69cb65940d7885bf2120aa44aeac89d04cf4c7d`.
- Tests: `python -m unittest` package + home plugin + morning brief + neewa_ops — OK, 1 skipped (Windows symlink privilege).
- Secret scan: 0 findings.
- Handoff ZIP/MD/CMD were **not** committed.

## Voice/model/cost

Wake Sherpa `hey neewa`; STT faster-whisper base; reasoning Luna (`openai/gpt-5.6-luna` shown live); TTS Edge fallback. OpenAI TTS available on the server, not activated (no assumed voice, no extra spend). GPT-Live **DEFERRED** (needs finite owner budget). Local Qwen ~224s = survival only.

## Real remaining dependencies

One owner session: sign in (or confirm autostart), say Hey Neewa, three follow-ups without clicking, hear a chosen OpenAI voice (or keep Edge), press Stop and confirm rearm, optionally open Ctrl+Shift+H, speak one safe task. Optional later: `docker_mount_cwd_to_workspace=false` so `/workspace` is not a RW repo bind.

## Final statement

**PARTIAL.** The product Home is running on the owner PC against the private backend. Physical speech, speaker, login, and delegated-job gates are not claimed.
