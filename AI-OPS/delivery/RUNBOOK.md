# NEEWA Jarvis V1 — Runbook

## Start NEEWA (owner)
1. Sign in to Windows normally. Hermes Desktop auto-starts (Startup shortcut → packed
   `...\apps\desktop\release\win-unpacked\Hermes.exe`) and reconnects to `neewa-core-01` (primary).
2. The app opens **NEEWA Home** (`/neewa-home`). Wake auto-arms on connect (no ear click).
3. Home must show **STREAM ACTIVE** (not STREAM INACTIVE). Say **"Hey Neewa"**,
   **"Hey Niva"**, or **"Hey Neeva"** — Sherpa listens for those aliases on the
   same profile. If detection misses, tap **Start listening** (same client voice
   path as a successful wake). **Mute** = wake.stop. **Stop** = voice.toggle off +
   session.interrupt + rearm. **Cancel task** = session.interrupt. **Rearm** = wake.start.

## Microphone routing (load-bearing)
Hermes Desktop wake capture uses Chromium Communications capture (echo cancellation on).
That endpoint must be **Microphone Array (Realtek(R) Audio)**, not Iriun Webcam.
`16_WINDOWS_CLIENT/Set-NeewaCaptureDevice.ps1` sets Console/Multimedia/Communications
to the Realtek array. After changing it, restart packed `Hermes.exe` so getUserMedia
reopens. If Iriun is put back as Communications default, wake will fail again.

## Voice (remote neewa-core-01 — not “This device”)
- Live: `tts.provider=nous` (managed OpenAI audio via Nous), voice `coral`, mode `chained`.
- Fallback: `hermes config set tts.provider edge` on the **server**.
- Do not use local Windows `hermes.exe config get` as NEEWA truth.
- GPT-Live is off. Do not set `voice.voice_chat_mode gpt-live` without a finite budget.

## Sandbox isolation
- Repo `/opt/neewa/neewa-os` and `/opt/neewa/status` are read-only in Docker.
- Writable scratch is `/workspace` → host `~/.hermes/sandboxes/docker/default/workspace` (not Git).
- `TERMINAL_DOCKER_MOUNT_CWD_TO_WORKSPACE=false` so the repo is not bind-mounted RW at `/workspace`.
- Rollback: restore `~/.hermes/.env.bak-isolation-*` and `config.yaml.bak-isolation-*`, then
  `systemctl --user restart hermes-gateway.service`.

## Recovery
- Desktop: relaunch packed exe; reconnects to primary `neewa` and re-arms wake.
- Gateway: `systemctl --user restart hermes-gateway.service`.
- Wake: confirm Source **neewa**, Home **STREAM ACTIVE**, Communications device = Realtek.
- Capture device: re-run `Set-NeewaCaptureDevice.ps1`, then restart Hermes.

## Rollback
- Plugin: `git revert` then copy `plugin.js` into `%LOCALAPPDATA%\hermes\desktop-plugins\neewa-command-center\`.
- TTS: `hermes config set tts.provider edge` on the server.
- Wake aliases: `python3 12_SCRIPTS/apply_neewa_wake_aliases.py` then
  `systemctl --user restart hermes-gateway.service`. Rollback the
  `wake_word_engines.py.bak-neewa-aliases-*` and `config.yaml.bak-neewa-aliases-*`
  copies, then restart the gateway.
