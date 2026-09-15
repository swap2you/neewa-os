# Provider Failover

Critical capabilities must have a degraded path.

## Reasoning
Premium:
GPT-5.6 Sol -> approved alternate premium provider -> lower tier with explicit degradation -> owner only if no safe path.

## Routine
Luna -> local model -> OpenRouter approved model.

## Coding
Codex -> Claude Code -> Gemini CLI -> owner escalation.

## Voice
GPT-Live-1 -> text chat -> alternate TTS/STT stack.

## GPU
preferred RunPod endpoint -> alternate GPU class/provider -> defer noncritical render.

Fallback must preserve:
- job ID;
- context summary;
- budget;
- acceptance contract;
- evidence chain.
