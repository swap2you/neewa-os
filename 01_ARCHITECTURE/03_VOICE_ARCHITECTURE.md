# Voice Architecture

## Primary
GPT-Live-1 front-end voice layer.

Requirements:
- natural interruptions;
- full-duplex conversation;
- low latency;
- text transcript retained with project/job context;
- deep reasoning delegated to NEEWA backend.

## Languages
Design for:
- English;
- Hindi;
- Marathi;
- normal code-switching between them.

Do not assume perfect recognition. Track correction rate and add a fallback path.

## Fallbacks
1. ElevenLabs for premium TTS/media where justified.
2. OpenAI speech/transcription APIs.
3. Open/offline Indic ASR/TTS after quality benchmark.

## Voice identity
NEEWA should use a female voice.
Do not clone or imitate a specific real person's voice without rights/consent.
The exact ChatGPT voice heard by the owner may not be exposed via API; audition available GPT-Live voices and select the closest preferred experience.
