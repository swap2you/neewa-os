# NEEWA Jarvis V1 — release report (wake-path repair)

**Product status:** PARTIAL
**Report date/time + timezone:** 2026-09-16 13:35 America/New_York
**Repo:** `swap2you/neewa-os`
**Commit SHA:** parent `316f3f4`; this repair commit is the new `HEAD` after push.
**Bootstrap ZIP SHA256:** `A2F9B50058F05EEFE5480DC80597476A27DC98F38770921971F004D5CFD68FDF`
**Windows app + Hermes:** Desktop 0.21.3; server hermes CLI on `neewa-core-01`.

## Defects fixed

1. **Wake captured the wrong Windows microphone.** Default Communications capture was
   Iriun Webcam. Hermes `getUserMedia` (echoCancellation/noiseSuppression/AGC) uses that
   role. Laptop speech on Realtek never reached Sherpa. Set Console/Multimedia/Communications
   to **Microphone Array (Realtek(R) Audio)** and restarted Desktop so the stream reopened
   (mic LastUsedStart 13:32:47, still held; `wake.start(gui)` 13:32:48).
2. **Home treated listener-armed as success.** `usePersonaState` defaulted to `armed` when
   the gateway was online. UI now distinguishes OFFLINE / CONNECTING / UNKNOWN / LISTENER
   STARTING / LISTENER ARMED (unverified) / STREAM ACTIVE / STREAM INACTIVE / WAKE DETECTED
   using `wake.status.audio_silent` plus a local non-retained RMS/device-label probe.
   Probe never sends PCM to `wake.feed`.
3. **Installer now pins Realtek as the capture endpoint** via `Set-NeewaCaptureDevice.ps1`.

## Tests

- `python -m unittest discover -s 13_TESTS -p test_*.py`: 47 OK, 1 skipped.
- Secret scan: 0 findings.
- Isolation (live inspect): `/opt/neewa/neewa-os` and `/opt/neewa/status` `rw=false`;
  `/workspace` → sandbox scratch RW.
- No `wake.detected` this afternoon (expected until owner re-speaks). No `mic delivers
  only silence` after the 13:32 re-arm.

## Security configuration (effective)

- Docker: repo `RW=False`; status `RW=False`; `/workspace` is not Git.
- No Tailscale Funnel/Serve.
- Cursor remains Git writer.

## Voice status

- Live TTS: nous / coral / chained.
- Direct OpenAI TTS: unconfigured.
- GPT-Live: off.
- Windows speaker audition: PENDING_PHYSICAL.

## Remaining owner-only (one session)

1. Confirm Home shows STREAM ACTIVE (not STREAM INACTIVE / Iriun).
2. Say **Hey Neewa** with no clicks.
3. Ask for system status; then two follow-ups; confirm spoken reply on speakers.
4. Stop; confirm wake re-arms; speak one safe task.

## Final statement

**PARTIAL.** Do not declare ACCEPTED until that physical session passes.
