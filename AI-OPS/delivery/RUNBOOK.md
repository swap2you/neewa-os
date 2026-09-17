# NEEWA Jarvis V1 — Runbook

## Start NEEWA (owner)
1. Sign in to Windows normally. Hermes Desktop auto-starts (Startup shortcut → packed
   `...\apps\desktop\release\win-unpacked\Hermes.exe`) and reconnects to `neewa-core-01` (primary).
2. The app opens **NEEWA Home** (`/neewa-home`). Wake auto-arms on connect (no ear click).
3. Home must show **READY** only when `audio_silent === false` or PCM frame
   counters are flowing. Missing telemetry is **UNKNOWN**, not READY. Stay on
   **NEEWA Home** while speaking — Conversation is an optional transcript, not
   the required voice UI. Say **"Hey Neewa"**, **"Hey Niva"**, or **"Hey Neeva"**.

## What “READY” means (read this)

| Badge | Meaning | What you do |
| --- | --- | --- |
| **UNKNOWN** | Listener on but no positive PCM/`audio_silent` proof | Wait or Rearm |
| **READY** | Positive evidence of wake audio | Say **Hey Neewa / Niva / Neeva**, then your request |
| **NO AUDIO** | Listener on but PCM is silent/missing | Tap **Rearm**; close Wispr/Zoom if they hold the mic |
| **STARTING** | Just armed (≤2.5s) | Wait a moment for READY |
| **MIC LIVE** | Capture actually started (`__NEEWA_VOICE__.recording`) | Keep speaking your request |
| **WAKE** | Wake phrase heard; capture is starting | Wait a moment — do not treat this as recording |
| **BUSY** | Thinking / working / speaking | Wait for the spoken reply |
| **MIC OFF** | Muted | Tap **Rearm** |

**Start listening** is still NEEWA on Home (same remote agent and the same
mounted composer). It must not jump to `#/` (that route is New Chat).

Home / HUD / Conversation share one session. HUD is the compact overlay, not a
second assistant. Native always-on-top HUD remains Ctrl+Shift+H.

**Spoken reply:** after wake + your request, NEEWA should speak through your selected
speakers (Nous coral). Chained mode is STT → agent → TTS, so a few seconds of delay is
normal. GPT-Live (full-duplex) is off until you approve a budget.

**Accent:** aliases include hey niva / neeva / neva / he neva. Sensitivity is 0.5.
Hindi/Marathi STT is a later upgrade (current STT is local faster-whisper base).

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

## Windows computer-use (neewa-edge-01, not Ubuntu)

- Driver: `cua-driver 0.28.2` in the interactive Windows session. Telemetry off.
- Install/repair: `16_WINDOWS_CLIENT/worker/Install-CuaDriverFromGitHub.ps1` (does not use cua.ai).
- Daemon: `Start-CuaDriver.ps1`. Worker: `Start-NeewaWindowsWorker.ps1` (outbound SSH poll).
- Logon: HKCU Run keys `NEEWA-CuaDriver` and `NEEWA-WindowsWorker` (not a SYSTEM service).
- Remote NEEWA does **not** drive this desktop through the Hermes SSH gateway. Jobs go to `windows-jobs/inbox` on the core workspace.
- Read-only personal Workspace inventory: enqueue `workspace_inventory` at A1. Policy and generator live in `16_WINDOWS_CLIENT/worker/`. Evidence packs: `evidence/LOCAL_WINDOWS_BRIDGE/<timestamp>/`. Raw JSON stays under `%USERPROFILE%\NEEWA-Personal`.
- Calculator UWP needs a restored (not iconic) window for UIA. Do not grant `ApplicationFrameHost.exe`.
- Cursor/Claude/Codex were **not** given concurrent cua MCP control.

## Recovery
- Desktop: relaunch packed exe; reconnects to primary `neewa` and re-arms wake.
- Gateway: `systemctl --user restart hermes-gateway.service`.
- Wake: confirm Source **neewa**, Home **STREAM ACTIVE**, Communications device = Realtek.
- Capture device: re-run `Set-NeewaCaptureDevice.ps1`, then restart Hermes.

## Rollback
- Windows worker Run keys: `Register-NeewaWindowsStartup.ps1 -Remove` or `Uninstall-NEEWA-Client.ps1`.
- Cua Driver binary: official GitHub `uninstall.ps1` from the 0.28.2 release (binaries preserved by NEEWA uninstall).
- Local Hermes `computer_use`: restore `%LOCALAPPDATA%\hermes\config.yaml.bak-neewa-cua-20260916` or delete the `computer_use` list entry under `platform_toolsets.cli`.
- Plugin: `git revert` then copy `plugin.js` into `%LOCALAPPDATA%\hermes\desktop-plugins\neewa-command-center\`.
- Desktop keep-mounted patch: restore `resources\app.asar.bak-neewa-*` (see
  `16_WINDOWS_CLIENT/hermes-desktop-patches/README.md`).
- TTS: `hermes config set tts.provider edge` on the server.
- Wake aliases: `python3 12_SCRIPTS/apply_neewa_wake_aliases.py` then
  `systemctl --user restart hermes-gateway.service`. Rollback the
  `wake_word_engines.py.bak-neewa-aliases-*` and `config.yaml.bak-neewa-aliases-*`
  copies, then restart the gateway.
