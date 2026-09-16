# Step 19 — OpenAI/Codex Resilience

Current active chain: Nous primary -> verified loopback Qwen fallback.

Prepared but not activated:
- Codex OAuth: `hermes auth add openai-codex --type oauth`; owner must complete the browser/device authorization if requested. No credential is entered into chat.
- Direct OpenAI API: provide `OPENAI_API_KEY` through a protected environment/secret mechanism, then execute `12_SCRIPTS/configure_openai_fallback.sh`. The script stores only `key_env: OPENAI_API_KEY`, never the value.

Direct API model intent: Sol for difficult reasoning/architecture/high-risk work; Terra for general execution; Luna for background summaries, extraction, and simple automation.

The local fallback was tested through a forced primary connection failure. OpenAI/Codex are not marked verified until their credentials are securely available and a controlled validation run passes.
