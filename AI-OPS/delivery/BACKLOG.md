# NEEWA Jarvis V1 — Delivery Backlog

## Done (autonomous, this delivery)
- [x] Phase 0 reconciliation + acceptance baseline (`ACCEPTANCE.md`).
- [x] No-click wake: confirmed auto-arm on connect; `start_new_session=false` for 3-turn continuity.
- [x] Native NEEWA Home: `/neewa-home` full-page route + sidebar nav + animated event-bound persona
      + real widgets (connection/assistant/jobs) + working controls. Renders (screenshot evidence).
- [x] Voice provider matrix; premium OpenAI TTS available (key present) as owner-selectable path.
- [x] Durable delivery docs (`AI-OPS/delivery/*`), work-order packet for NEEWA.
- [x] Bootstrap ZIP rebuilt with the new plugin; manifest reproducible; regression + secret scan.

## Requires owner (one consolidated physical session)
- [ ] A01 autostart after real Windows login (restart/login).
- [ ] A03/A04 no-click wake fires on spoken "Hey Neewa" (witness).
- [ ] A05/A06 three continuous voice turns with retained context.
- [ ] A07 pick a premium OpenAI voice (audition) + confirm audible playback through speakers.
- [ ] A08 stop/rearm behavior.
- [ ] A09–A11 confirm NEEWA Home / persona / HUD live on the owner screen.
- [ ] A12 speak a real task; confirm job id + progress + result.

## Deferred (explicit)
- [ ] Full-duplex GPT-Live voice — needs direct OpenAI key + owner-approved finite budget.
- [ ] On-device local TTS (piper/kittentts) install if network TTS is unwanted.
- [ ] Optional compact always-on-top HUD overlay window (separate from Home) if desired.
- [ ] 3D avatar — only after 2D benchmark justifies it.
