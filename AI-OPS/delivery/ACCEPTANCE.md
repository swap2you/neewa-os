# NEEWA Jarvis V1 — Acceptance

Updated 2026-09-16 13:20 America/New_York after telemetry/Stop/isolation/voice fixes.
Physical speech/speaker/login gates are **not** PASS.

## Environment

- Git: local = origin/main = server after this delivery push (see RELEASE_REPORT).
- Desktop Hermes 0.21.3; plugin deployed to `%LOCALAPPDATA%\hermes\desktop-plugins\neewa-command-center\`.
- Remote: Tailscale SSH `ubuntu@neewa-core-01`. No Serve/Funnel.
- Effective **remote** wake (server `hermes config get`): enabled=true, phrase=`hey neewa`,
  surface=gui, capture=client, **start_new_session=false**, voice_chat_mode=**chained**.
- Live TTS: **nous / coral** (managed OpenAI audio). Direct OpenAI TTS key: **unconfigured**.
- Local Windows `hermes.exe config get` is “This device” and is not the mic path when Source=neewa.

## Gates

| ID | Status | Evidence |
| --- | --- | --- |
| A01 login autostart | PENDING_PHYSICAL | Startup shortcut exists → packed Hermes.exe. Not witnessed this logoff/login. |
| A02 private backend | PASS | Live Home Source **neewa**, Gateway ONLINE. Funnel: No serve config. |
| A03 no-click arm | PASS (infra) / PENDING_PHYSICAL (spoken) | MIC ARMED, wake armed · hey neewa, capture client on live Home. |
| A04 wake phrase | PENDING_PHYSICAL | Do not pass from historical 08:02 logs. |
| A05 speech → remote task | PENDING_PHYSICAL | Same. |
| A06 3 continuous turns | PENDING_PHYSICAL | Remote `start_new_session=false` verified via server CLI. Spoken continuity not witnessed. |
| A07 chosen voice on speakers | PENDING_PHYSICAL | Server generated coral.mp3 63360 bytes via Nous gateway. Not heard on Windows speakers this session. |
| A08 stop | PASS (infra) / PENDING_PHYSICAL | Stop now calls `voice.toggle off` + `session.interrupt` + rearm. Spoken confirm remaining. |
| A09 NEEWA Home | PASS | Running `#/neewa-home` screenshot (owner + this session). |
| A10 animated state | PASS (infra) | Bound to wake.status + host.state + events. |
| A11 HUD | PASS (infra) | `/neewa-hud` + Ctrl+Shift+H. |
| A12 CoS task | PENDING_PHYSICAL | Isolation job proved sandbox writes; owner spoken job not done. |
| A13 operational data | PASS | Jobs 4/4, model luna, speech/mode/STT **verified**; TTS provider labeled telemetry unavailable (no RPC); approvals none (no focused session). |
| A14 persistence | PARTIAL | Gateway restart + Desktop reconnect observed. Sleep/resume untested. |
| A15 budget/fallback | PASS | Chained; GPT-Live off; Edge remains fallback; Nous TTS uses existing subscription. |
| A16 security | PASS | Repo and status mounts RW=false. `/workspace` is sandbox scratch, not Git. Isolation test: repo write exit 1 (read-only). |
| A17 installer | PASS after ZIP rebuild if plugin changed | Rebuild from tracked plugin. |
| A18 source/test | PASS pending this push | Unit tests + secret scan. |
| A19 workday | PENDING_PHYSICAL | Owner must close Cursor and use Home. |

## Release decision

**PARTIAL.** Confirmed gaps 1–4 and 6 (engineering) are closed. Required physical speech, speakers, login, three-turn, and spoken job gates remain. Not ACCEPTED.
