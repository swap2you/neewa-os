# NEEWA Jarvis V1 — Acceptance Baseline (Phase 0 reconciliation)

Reconciled 2026-09-16 from the ACTUAL local checkout + installed Hermes, not documents.
Source of truth for gate status is `04_PRODUCT_ACCEPTANCE.md` (A01–A19).

## Verified environment facts

- Git: local HEAD = origin/main = `3d71463` (clean; untracked handoff ZIP/CMD/MD present and will NOT be committed).
- Installed Hermes Desktop: v0.21.3 (upstream 2cfb655d), `C:\Users\swap2\AppData\Local\hermes`.
- Remote backend: `neewa-core-01` (Ubuntu), reached via authenticated SSH over Tailscale; no Serve/Funnel.
- Voice/wake config (installed): wake_word.enabled=true, provider=sherpa, phrase="hey neewa",
  surface=gui, capture=client, **start_new_session=true** (3-turn fragmentation risk — to address),
  tts.provider=edge, voice.voice_chat_mode=chained.
- Desktop SDK capabilities CONFIRMED in installed source:
  - `ROUTES_AREA` ('routes') full-page routes; `SIDEBAR_NAV_AREA` ('sidebar.nav'); working example: kanban `/kanban`.
  - `host.navigate`, `host.onEvent` (gateway event tap, '*'), `host.request` (gateway JSON-RPC),
    `host.state` (gateway/busy/awaitingResponse/model/profile/focusedUsage/connectionId), `host.logs`.
  - Disk plugins load from `<HERMES_HOME>/desktop-plugins/<name>/plugin.js` (local), hot-reload on change.

## Component evidence vs product acceptance (start of this delivery)

| Gate | Prior evidence | Product status at Phase 0 |
| --- | --- | --- |
| A01 startup after login | login-startup shortcut -> packed exe | PENDING_PHYSICAL |
| A02 correct private backend | connections.json primary=neewa; reconnect verified | PASS (infra) |
| A03 no-click wake armed | wake armed only after GUI ear/session; not auto on cold start | TO IMPLEMENT |
| A04 wake phrase detected | log: wake "hey neewa" phrase detected (08:02) | PENDING_PHYSICAL (needs live) |
| A05 real speech->task | log: 6s webm -> faster-whisper -> remote turn complete | PENDING_PHYSICAL |
| A06 3 continuous turns | not proven; start_new_session=true risk | TO IMPLEMENT + PHYSICAL |
| A07 spoken reply chosen voice | Edge Aria generated; aesthetically rejected | PENDING (voice choice) + PHYSICAL |
| A08 barge-in/stop | not verified | PENDING |
| A09 original NEEWA Home | only skin + right pane; HERMES splash remains | TO BUILD |
| A10 animated state authenticity | none | TO BUILD |
| A11 HUD | none | TO BUILD |
| A12 real CoS task | registries exist; no voice-created job | TO IMPLEMENT + PHYSICAL |
| A13 operational data | Command Center shows real cron/host.state + snapshot | PASS (infra) |
| A14 persistence/recovery | reconnect verified; sleep/resume untested | PARTIAL + PHYSICAL |
| A15 budget/fallback | chained voice; local Qwen slow; no new billing | PARTIAL |
| A16 security/governance | read-only mounts, no exposure, no secrets | PASS |
| A17 installer/rollback | bootstrap ZIP rebuilt dc02b1eb | PARTIAL |
| A18 source/test release | 40 tests Linux; manifest reproducible; HEAD synced | PASS |
| A19 usable workday | not proven hands-free | PENDING_PHYSICAL |

## This delivery's autonomous scope (no owner needed)

1. No-click wake auto-arm on startup + start_new_session continuity (A03/A06 infra).
2. Native NEEWA Home full-page route + animated persona + HUD + real widgets (A09–A11 build).
3. Voice provider matrix (Nous managed TTS check; keep Edge fallback) (A07/A15 infra).
4. Chief-of-Staff durable task lifecycle (A12/A13 infra).
5. Bounded backend work order to NEEWA + independent review.
6. Delivery docs, regression, commit/push/sync, release report.

Physical gates (A01/A04–A08/A19 and visual A09–A11 confirmation) require one consolidated owner session.
