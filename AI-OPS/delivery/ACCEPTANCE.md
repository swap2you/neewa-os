# NEEWA Jarvis V1 — Acceptance Baseline

Reconciled 2026-09-16 12:40 ET from the live checkout, installed Hermes 0.21.3,
running Desktop (`#/neewa-home`), and host snapshots. Physical speech/audio
gates stay PENDING until the owner witnesses them.

## Environment

- Git before this delivery commit: `39e3a28` local = origin/main. Server checkout
  was `39e3a28` / clean until the new push.
- Desktop: packed `Hermes.exe`; plugin hash matches repo after install copy.
- Remote: Tailscale SSH `ubuntu@neewa-core-01:22`. No Serve/Funnel.
- Wake: sherpa, phrase `hey neewa`, surface=gui, capture=client,
  `start_new_session=false`. Auto-arm observed `wake.start(gui)` at 12:21:19
  after Desktop restart (no ear click in that restart).
- TTS: `edge` (Aria rejected aesthetically). OpenAI TTS key present on server;
  not switched pending owner audition.
- Host snapshot: `generated_at=2026-09-16T16:29:17Z` host=`neewa-core-01` overall=ok.
- Voice snapshot: `generated_at=2026-09-16T16:33:48Z` overall=`voice_pipeline_observed_working`.

## Gates

| ID | Status | Evidence |
| --- | --- | --- |
| A01 startup after login | PENDING_PHYSICAL | Startup shortcut → packed exe exists. Needs a real logoff/login witness. |
| A02 correct private backend | PASS | Live Home shows Source **neewa**, Gateway ONLINE. Tailscale: no funnel. |
| A03 no-click listener armed | PASS (infra) / PENDING_PHYSICAL (spoken) | Home MIC ARMED; wake.start 12:21:19 after restart. Spoken test still owner. |
| A04 wake phrase | PENDING_PHYSICAL | Prior log 08:02 phrase detected; not re-witnessed this session. |
| A05 speech → remote task | PENDING_PHYSICAL | Prior 11:32 6.5s whisper → 22.2s remote turn. Not re-run. |
| A06 3 continuous turns | PENDING_PHYSICAL | `start_new_session=false` set; continuity not spoken-proven. |
| A07 chosen voice on speakers | PENDING_PHYSICAL | Edge fallback live; OpenAI voices listed in VOICE_PROVIDER_MATRIX.md. |
| A08 barge-in / stop | PARTIAL | Mute/Stop/Rearm buttons call `wake.stop` / `wake.start`. Barge-in = chained-engine limitation unless owner confirms. |
| A09 original NEEWA Home | PASS (running UI) | Screenshot: persona + NEEWA Home selected, not HERMES splash. Physical ack still useful. |
| A10 animated state | PASS (infra) | Bound to wake.status + host.state + gateway events. |
| A11 HUD | PASS (infra) | `/neewa-hud` + native `Ctrl+Shift+H` bridge. Owner should toggle overlay. |
| A12 CoS task | PENDING_PHYSICAL | Lifecycle documented; needs one spoken safe job. |
| A13 operational data | PASS | Live: 4/4 jobs, model gpt-5.6-luna, source neewa. TTS/approvals show Unavailable when RPC lacks a session — not fabricated. |
| A14 persistence | PARTIAL | Restart reconnect + re-arm observed. Sleep/resume untested. |
| A15 budget/fallback | PASS (policy) | Chained voice; GPT-Live deferred; Qwen slow survival path. |
| A16 security | PASS with note | RO `/opt/neewa/neewa-os` + `/opt/neewa/status`. Hermes also mounts repo RW at `/workspace` via `docker_mount_cwd_to_workspace` — remaining hardening, not a public exposure. No secrets in repo. A2/A3 intact. |
| A17 installer | PASS | Bootstrap ZIP rebuilt from tracked files. |
| A18 source/test | PASS pending push | Unit tests + secret scan 0 findings. Sync after commit. |
| A19 usable workday | PENDING_PHYSICAL | Owner closes Cursor and uses Home hands-free. |

## Release decision

**PARTIAL.** Engineering surfaces for Home/HUD/wake/continuity/data are running on
the owner PC against `neewa-core-01`. Required physical speech, speaker, login,
and task-delegation witnesses remain. Continue; do not call ACCEPTED.
