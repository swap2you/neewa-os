# Work Order WO-20260916-jarvis-v1-review (Cursor → NEEWA, read-only)

Read this file from the repo mount after host `git pull`. Do not write repo files.

## Checks

1. `/opt/neewa/status/latest.json` — `generated_at`, host identity, gateway/docker/tailscaled/ollama, repo SHA.
2. `/opt/neewa/status/voice.json` — `generated_at`, overall, last wake/STT/turn.
3. Confirm jobs `neewa-daily-health`, `neewa-morning-brief`, `neewa-host-status`, `neewa-voice-readiness`.
4. Confirm `wake_word.start_new_session` is false.
5. Independent review of Cursor commit on `main` (plugin.js, no secrets, RO mounts, no public listener).

## Response (parsable)

`job_id`, `source_commit`, `host_snapshot_timestamp`, `voice_snapshot_timestamp`,
`observed_state`, `defects`, `actions_performed`, `actions_not_performed`,
`approval_required`, `final_status` (DONE | BLOCKED | APPROVAL_REQUIRED).
Never claim a Windows physical/UI/audio PASS.
