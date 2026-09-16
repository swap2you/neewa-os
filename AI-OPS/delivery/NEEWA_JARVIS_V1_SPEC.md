# NEEWA Jarvis V1 — Delivery Spec (verified truth)

This is the current implemented spec, not the handoff prompt. Source: installed
Hermes 0.21.3 desktop SDK + this repo. Updated 2026-09-16.

## Architecture

- **Windows PC (Cursor-owned):** Hermes Desktop (Electron) is the face — mic capture,
  speakers, NEEWA Home UI. Sole Git writer + installer + release owner.
- **`neewa-core-01` (NEEWA):** remote Hermes agent/gateway over Tailscale SSH; the brain,
  wake detector (Sherpa), STT (faster-whisper), TTS, jobs, memory. Docker repo/status mounts
  read-only. Bounded reviewer/executor, not a repo writer.

## NEEWA Home (native Desktop plugin)

`16_WINDOWS_CLIENT/assets/neewa-command-center/plugin.js` (installed to
`<HERMES_HOME>/desktop-plugins/neewa-command-center/plugin.js`). Registrations (supported SDK):

- `ROUTES_AREA` full-page route `/neewa-home` — the product Home.
- `SIDEBAR_NAV_AREA` entry "NEEWA Home".
- `panes` right pane + `statusBar.right` chip (chip navigates to Home).
- Best-effort cold-start navigation to `/neewa-home` when the app opens at the default route.

**Persona:** an original abstract feminine-coded luminous presence (canvas: soft core +
concentric rings, graphite/teal/ivory). NOT a real person or movie character. Motion is
driven by REAL signals — `host.state` (gateway/busy/awaitingResponse) and `host.onEvent`
gateway wake events (`wake.detected`/`wake.pause`/`wake.resume`). Idle uses a slow breath;
reduced-motion renders a static frame; loop throttles + pauses when hidden (low idle CPU).
No fabricated metrics, no lip-sync claim.

**State machine (real events):** disconnected → armed → listening → thinking → working.
Widgets show real Connection/Assistant/Model/Context (host.state) and live Scheduled jobs
(`host.request('cron.manage', {action:'list'})`) with freshness; server health/morning brief/
projects are host-snapshot backed via the NEEWA chat (labeled, never fabricated).

## Wake / voice

- `wake_word`: enabled, provider=sherpa, phrase="hey neewa", surface=gui, capture=client.
  **Auto-arms on connect** (no ear click) — verified in gui.log (`wake.start(gui)` after a
  plain restart). `start_new_session=false` set for multi-turn context continuity.
- Chained voice: wake → mic → faster-whisper STT → remote NEEWA turn → TTS. `voice_chat_mode=chained`.
- TTS: see `VOICE_PROVIDER_MATRIX.md`. Edge Aria is the free default/fallback; premium OpenAI
  TTS is available (server `VOICE_TOOLS_OPENAI_KEY` present) pending owner voice choice.

## What requires the owner (physical)

Login/restart autostart, saying the wake phrase, hearing the chosen voice, seeing the animated
Home live, and a real voice-created task — all per `04_PRODUCT_ACCEPTANCE.md` (A01/A03–A08/A12/A19).
