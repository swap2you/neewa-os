# NEEWA Jarvis V1 — Runbook

## Start NEEWA (owner)
1. Sign in to Windows normally. Hermes Desktop auto-starts (Startup shortcut → packed
   `...\apps\desktop\release\win-unpacked\Hermes.exe`) and reconnects to `neewa-core-01` (primary).
2. The app opens **NEEWA Home** (`/neewa-home`). Wake auto-arms on connect (no ear click).
3. Say **"Hey Neewa"**, then speak. **Mute** = wake.stop. **Stop** = voice.toggle off +
   session.interrupt + rearm. **Cancel task** = session.interrupt. **Rearm** = wake.start.

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
- Wake: confirm Source **neewa**, not This device.

## Rollback
- Plugin: `git revert` then copy `plugin.js` into `%LOCALAPPDATA%\hermes\desktop-plugins\neewa-command-center\`.
- TTS: `hermes config set tts.provider edge` on the server.
