# NEEWA Jarvis V1 — release report (wake-path repair)

**Product status:** PARTIAL (wake audio path repaired; physical spoken session still required)
**Report date/time + timezone:** 2026-09-16 15:42 America/New_York
**Repo:** `swap2you/neewa-os`
**Commit SHA:** parent `a1d8cf9`; this mic-probe fix is the new `HEAD` after push.
**Bootstrap ZIP SHA256:** `0B7DA5F9E5F724C9634CD27E5A4A4D5A07C079F7E61DC4779D9F48480FD6905F`
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

4. **Accented wake aliases** — Sherpa KeywordSpotter supports multiple keyword
   lines. Hermes 0.21.3 only enrolled `wake_word.phrase`. Canonical remains
   `hey neewa`; aliases `hey niva` / `hey neeva` / `hey neva` map to the same
   profile. Home **Start listening** uses `wake.pause` + Desktop
   `hermes:composer-voice-toggle` (not server `voice.record`, which would open
   PortAudio on the headless host).

5. **Home mic probe stole the wake stream.** The UI opened getUserMedia every 8s to
   “verify” audio. On Windows that competed with Desktop’s continuous wake.feed, so the
   server logged `mic delivers only silence` while Conversation PTT still worked. Probe
   now only enumerates device labels. Stream health uses `wake.status.audio_silent`.
   UI no longer sticks on “verifying” (that was caused by refreshing `wake.at` every poll).

## Tests

- `python -m unittest discover -s 13_TESTS -p test_*.py`: 58 OK, 1 skipped.
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
