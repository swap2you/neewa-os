# Step 17 — NEEWA Voice Implementation

Implemented: faster-whisper `base` STT, free Edge TTS with female `en-US-AriaNeural`, sherpa open-vocabulary wake engine, phrase `hey neewa`, remote Desktop client capture, GUI-only wake ownership, and server relay mode.

Validated: imports; Edge TTS speech generation; local STT successfully transcribed generated speech in 4.7 seconds; sherpa initialized in client-capture mode for `hey neewa`.

Requires Windows PC validation: microphone permission, acoustic wake detection, speaker playback/barge-in, and real English/Hindi/Marathi accuracy.

Python 3.12 cannot install openWakeWord 0.6.0 because Linux `tflite-runtime` lacks a CPython 3.12 wheel. Sherpa is the supported zero-training alternative. Sherpa also needed `pypinyin`, installed after initialization exposed the missing dependency.
