# NEEWA Jarvis V1 — release report (gap closure)

**Product status:** PARTIAL
**Report date/time + timezone:** 2026-09-16 13:20 America/New_York
**Repo:** `swap2you/neewa-os`
**Commit SHA:** parent `2c3ff5d`; this closure commit is the new `HEAD` after push.
**Bootstrap ZIP SHA256:** `dfc4563a44f8da54b2300d1cdd3c335fe261f12434e5faa56cfca906ee16f9df`
**Windows app + Hermes:** Desktop 0.21.3; server hermes CLI on `neewa-core-01`.

## Defects fixed

1. **Telemetry** — `config.get tts.provider` is not a 0.21.3 allowlisted key (error looked like “unavailable”). Command Center now uses `voice.toggle status` and `approval.pending` with `session_id`. Labels: verified / telemetry unavailable / none (no focused session). Never `config.get full`.
2. **Stop** — no longer wake.stop + 600ms wake.start. Stop = `voice.toggle off` (ends voice mode + TTS) + `session.interrupt` + `voice.record stop` + rearm. Mute and Cancel task are separate.
3. **Sandbox** — `TERMINAL_DOCKER_MOUNT_CWD_TO_WORKSPACE=false`. `/workspace` is host sandbox scratch, **not** the Git repo. `/opt/neewa/neewa-os` and `/opt/neewa/status` remain `:ro`. Proven: `MANIFEST.md` append → Read-only file system; `repo_w=False`.
4. **Remote voice config** — server CLI: `start_new_session=false`, capture=client, surface=gui, chained. Live UI Source=neewa. Local `hermes.exe` is This device.
5. **Voice upgrade** — no direct OpenAI TTS key. Switched live TTS to **Nous managed** `nous` / **coral** (sample 63360 bytes). Edge kept as fallback. GPT-Live not enabled.

## Tests

- `python -m unittest` home plugin + windows package + morning brief + neewa_ops: OK, 1 skipped (Windows symlink privilege).
- Secret scan: 0 findings (run at commit).
- Isolation: sandbox write to `/workspace` OK; repo write failed.
- Physical A01/A04–A08/A12/A19: **not PASS**.

## Security configuration (effective)

- Docker: repo `RW=False` at `/opt/neewa/neewa-os`; status `RW=False`; `/workspace` → `~/.hermes/sandboxes/docker/default/workspace` RW.
- No Tailscale Funnel/Serve.
- Cursor remains Git writer.

## Voice status

- Live: nous / coral / chained.
- Direct OpenAI TTS: unconfigured.
- Windows speaker audition: PENDING_PHYSICAL.

## Remaining owner-only

Sign-in autostart witness; say Hey Neewa; three no-click turns; hear coral through speakers (or revert to Edge); Stop while speaking; one safe spoken job; optional sleep/resume.

## Final statement

**PARTIAL.** Do not declare ACCEPTED until those physical gates pass.
