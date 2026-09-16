# NEEWA Voice Provider Matrix (verified 2026-09-16 13:16 ET)

Installed Hermes 0.21.3 supports these `tts.provider` values: edge, openai, elevenlabs,
gemini, minimax, nous, piper, kittentts, neutts.

| Provider | Status on this server | Cost | Privacy | Notes |
| --- | --- | --- | --- | --- |
| **nous** (current live) | **Verified** — managed `openai-audio-gateway.nousresearch.com`; sample `coral.mp3` 63360 bytes | Existing Nous subscription (not a new OpenAI key) | Network (Nous proxy → OpenAI audio) | `tts.provider=nous`, `tts.openai.voice=coral`, model coerced to `gpt-4o-mini-tts`. No `VOICE_TOOLS_OPENAI_KEY` in server `.env`. |
| **edge** (fallback) | Verified working; Aria rejected aesthetically | Free | Network (Microsoft), NOT offline | Revert with `hermes config set tts.provider edge` |
| **openai** (direct) | **Unconfigured** — no `VOICE_TOOLS_OPENAI_KEY` / `OPENAI_API_KEY` | ~$15 / 1M chars | Network (OpenAI) | Do not enable until a key is added in server `.env` |
| elevenlabs | Unconfigured | Paid | Network | Optional |
| piper / kittentts / neutts | Not installed | Free | On-device | True local fallback |
| gpt-live | **Deferred** | $0.05/active min per docs | Network | Direct OpenAI key + finite owner budget. Not enabled. `voice.voice_chat_mode=chained`. |

## Plugin telemetry vs CLI

Hermes 0.21.3 `config.get` allowlists keys such as `provider`, `skin`, `full` — **not** `tts.provider` or `voice.voice_chat_mode`. The Desktop plugin therefore must not call `config.get full` (whole YAML). Command Center shows speech/mode/STT from `voice.toggle status` and labels TTS provider **telemetry unavailable**. Live provider is this matrix / `hermes config get` on **neewa-core-01**.
