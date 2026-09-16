# NEEWA Jarvis V1 — Runbook

## Start NEEWA (owner)
1. Sign in to Windows normally. Hermes Desktop auto-starts (Startup shortcut → packed
   `...\apps\desktop\release\win-unpacked\Hermes.exe`) and reconnects to `neewa-core-01` (primary).
2. The app opens **NEEWA Home** (`/neewa-home`) — glowing NEEWA persona, "Ready · listening
   for Hey Neewa". Also reachable from the left sidebar, the "NEEWA · READY" chip, or Ctrl+Alt+N.
3. Wake auto-arms on connect (no ear click). Say **"Hey Neewa"**, then speak.
   Mute / Stop / Rearm are on Home. Compact HUD: sidebar **NEEWA HUD** or Ctrl+Shift+H (native overlay).

## Voice
- Default TTS is Edge (free). To use premium OpenAI voices: audition, then on the server
  `hermes config set tts.provider openai` and `hermes config set tts.openai.voice <voice>`
  (VOICE_TOOLS_OPENAI_KEY already present). Revert with `hermes config set tts.provider edge`.

## Recovery
- Desktop: relaunch the packed exe; it reconnects to primary (neewa) and re-arms wake.
- Gateway: `hermes gateway restart` on the server. Local model: `systemctl status ollama` (loopback).
- Wake not arming: confirm connected to `neewa` (not "This device"); check `~/.hermes/logs/gui.log`
  for `wake.start(gui)`.

## Rollback
- Plugin/UI: `git revert <commit>` (git preserves prior plugin) then redeploy asset to
  `<HERMES_HOME>/desktop-plugins/neewa-command-center/plugin.js`.
- Windows client: `16_WINDOWS_CLIENT/Uninstall-NEEWA-Client.ps1` (preserves Hermes data + Tailscale).
- Config: `hermes config set wake_word.start_new_session true` to restore prior behavior.

## Health / status
- Ask NEEWA "system status" / "morning brief" (host-snapshot backed, timestamped).
- Deterministic host probes: `12_SCRIPTS/neewa_host_status.sh`, `12_SCRIPTS/neewa_voice_readiness.sh`.
