# NEEWA Jarvis V1 — Delivery Backlog

## Done (engineering, this delivery)
- [x] Phase 0 reconciliation + acceptance baseline.
- [x] No-click wake auto-arm on connect; `start_new_session=false`.
- [x] NEEWA Home `/neewa-home` + compact HUD `/neewa-hud` + native HUD bridge.
- [x] Mute / Stop / Rearm + MIC privacy badge bound to `wake.status`.
- [x] Real widgets: connection, jobs, wake, TTS provider (named keys only), approvals count.
- [x] Voice provider matrix; GPT-Live deferred.
- [x] Chief-of-Staff intent/lifecycle doc; backend work-order packet.
- [x] Cron registry includes host-status + voice-readiness jobs.
- [x] Delivery docs under `AI-OPS/delivery/`.

## Requires owner (one consolidated physical session)
- [ ] A01 autostart after real Windows login (restart/login — do not store the password).
- [ ] A03/A04 no-click wake fires on spoken “Hey Neewa”.
- [ ] A05/A06 three continuous voice turns with retained context.
- [ ] A07 pick a premium OpenAI voice (audition) + confirm speakers.
- [ ] A08 Stop then rearm; barge-in if the chained engine supports it.
- [ ] A09–A11 confirm Home / persona / HUD on the owner screen.
- [ ] A12 speak a real safe task; confirm job id + progress + result.
- [ ] A19 close Cursor and use NEEWA for a normal signed-in stretch.

## Deferred (explicit)
- [ ] Full-duplex GPT-Live — direct OpenAI key + owner-approved finite budget.
- [ ] On-device Piper/KittenTTS if network TTS is unwanted.
- [ ] 3D avatar — only after the 2D persona is accepted.
