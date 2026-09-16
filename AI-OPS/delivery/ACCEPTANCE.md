# NEEWA Jarvis V1 — Acceptance

Updated 2026-09-16 13:35 America/New_York after the wake-path repair.
Physical speech/speaker/login gates are **not** PASS.

## Environment

- Git: see RELEASE_REPORT for HEAD after this push.
- Desktop Hermes 0.21.3; plugin deployed to `%LOCALAPPDATA%\hermes\desktop-plugins\neewa-command-center\`.
- Remote: Tailscale SSH `ubuntu@neewa-core-01`. No Serve/Funnel.
- Effective **remote** wake (server `hermes config get`): enabled=true, phrase=`hey neewa`,
  surface=gui, capture=client, **start_new_session=false**, voice_chat_mode=**chained**.
- Live TTS: **nous / coral**. Direct OpenAI TTS key: **unconfigured**.
- Windows capture: Communications + Multimedia + Console defaulted to
  **Microphone Array (Realtek(R) Audio)** at 13:32 (was Communications=Iriun Webcam).
  Hermes restarted 13:32:47 so getUserMedia reopened on Realtek.

## Diagnosis (owner-facing failure)

UI showed Gateway ONLINE / MIC ARMED / capture client while “Hey Neewa” did nothing.
`wake.status listening` is not PCM. Chromium wake capture uses the **Communications**
role (`echoCancellation: true`). That role was **Iriun Webcam**, not the laptop array.
No `wake.detected` after 08:02:14. Last pre-repair `wake.feed` was a WS send failure
at 13:24:24. Home previously defaulted to **armed** whenever the gateway was online.

## Gates

| ID | Status | Evidence |
| --- | --- | --- |
| A01 login autostart | PENDING_PHYSICAL | Startup shortcut exists. Not witnessed this logoff/login. |
| A02 private backend | PASS | Live Home Source **neewa**, Gateway ONLINE. No Funnel. |
| A03 no-click arm | PASS (infra) / PENDING_PHYSICAL (spoken) | Auto-arm `wake.start(gui)` 13:32:48 after Desktop restart. Spoken confirm remaining. |
| A04 wake phrase | PENDING_PHYSICAL | Do not pass from historical 08:02 logs. Repair is in place for this session. |
| A05 speech → remote task | PENDING_PHYSICAL | Same. |
| A06 3 continuous turns | PENDING_PHYSICAL | Remote `start_new_session=false`. Spoken continuity not witnessed. |
| A07 chosen voice on speakers | PENDING_PHYSICAL | Server coral TTS configured. Not heard on Windows speakers this session. |
| A08 stop | PASS (infra) / PENDING_PHYSICAL | Stop = `voice.toggle off` + `session.interrupt` + rearm. |
| A09 NEEWA Home | PASS | Running `#/neewa-home`. |
| A10 animated state | PASS (infra) | Honest states: unknown / starting / stream active / stream inactive. No default-armed. |
| A11 HUD | PASS (infra) | `/neewa-hud` + Ctrl+Shift+H. |
| A12 CoS task | PENDING_PHYSICAL | Owner spoken job not done. |
| A13 operational data | PASS (infra) | Jobs/model/speech labels remain; stream health now shown. |
| A14 persistence | PARTIAL | Gateway restart + Desktop reconnect observed. Sleep/resume untested. |
| A15 budget/fallback | PASS | Chained; GPT-Live off; Edge fallback; Nous TTS uses existing subscription. |
| A16 security | PASS | Repo and status mounts RW=false. `/workspace` is sandbox scratch. |
| A17 installer | PASS | ZIP rebuilt with plugin + capture-device helper. |
| A18 source/test | PASS pending this push | 47 tests, 1 skipped; secret scan 0. |
| A19 workday | PENDING_PHYSICAL | Owner must close Cursor and use Home. |

## Release decision

**PARTIAL.** Wake capture routing is repaired and the UI no longer claims MIC ARMED
as proof of audio. Not ACCEPTED until the single owner spoken session passes.
