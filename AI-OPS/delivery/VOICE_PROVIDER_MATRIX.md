# NEEWA Voice Provider Matrix (verified 2026-09-16)

Installed Hermes 0.21.3 supports these `tts.provider` values: edge, openai, elevenlabs,
gemini, minimax, nous, piper, kittentts, neutts.

| Provider | Status on this server | Cost | Privacy | Notes |
| --- | --- | --- | --- | --- |
| **edge** (current default) | Active, works (Aria heard) | Free | Network (Microsoft), NOT offline | Owner rejected Aria aesthetically; kept as safe fallback |
| **openai** (premium) | **Available** — `VOICE_TOOLS_OPENAI_KEY` present in `~/.hermes/.env` | ~$15 / 1M chars (a spoken reply ≈ fractions of a cent) | Network (OpenAI) | Voices: alloy, ash, ballad, coral, echo, fable, nova, onyx, sage, shimmer, verse. Recommended for A07; needs owner voice pick + audible confirm |
| elevenlabs | Not configured (no ELEVENLABS_API_KEY) | Paid | Network | Optional premium alternative |
| piper / kittentts / neutts | Not installed | Free | **On-device/offline** | True local fallback if network TTS unwanted; install on demand |
| nous (managed) | Routes to OpenAI-audio via subscription | Subscription | Network | `openai-audio`; verify entitlement before relying on it |

## Decision

- **Do not** switch the default or spend before owner audition (mission: no assumed voice
  preference; bounded cost only). Edge remains the working fallback so voice input is never
  blocked by TTS choice.
- **Recommended path (A07):** at the consolidated acceptance session, audition 2–3 OpenAI
  voices (short neutral line), let the owner pick, set `tts.provider=openai` + chosen
  `tts.openai.voice`, and confirm audio plays through the Windows speaker.
- Keys never appear in Cursor chat, repo, JS, or logs — configured only in server `~/.hermes/.env`.

## STT / wake / reasoning (unchanged, for reference)

- Wake: Sherpa open-vocabulary "hey neewa", client capture, server detector.
- STT: faster-whisper base (free, local to server), verified on real 6s mic audio.
- Reasoning: Nous Luna routine / Sol escalation; local Qwen fallback (slow ~224s, survival only).
- Full-duplex GPT-Live: DEFERRED — requires direct OpenAI key + owner-approved finite budget
  ($0.05/active min per docs). Chained voice ships without it.
