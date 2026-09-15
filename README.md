# NEEWA OS v1.0

**Status:** Architecture frozen for 30 days  
**Baseline date:** 2026-09-15  
**Purpose:** Build an always-on, female AI Chief of Staff that can understand the owner, research deeply, delegate work, validate results independently, control cost/token usage, preserve evidence, and escalate only when owner authority is actually required.

NEEWA is not a chatbot and is not a collection of permanent personality bots.

NEEWA is a governed operating layer:

- Hermes Agent = chief-agent runtime
- NVIDIA NemoClaw/OpenShell = security/sandbox boundary
- GPT-5.6 Sol High = primary high-value reasoning
- GPT-5.6 Luna = low-cost OpenAI worker
- GPT-6 Astra = exceptional escalation only
- LiteLLM = model gateway, budgets, retries, fallbacks
- Langfuse = traces, cost/latency/quality telemetry
- OpenRouter = governed model diversity / low-cost overflow
- Nous Plus = Hermes ecosystem + hosted tools/models
- OpenHands Agent Canvas = coding-agent execution floor
- Codex / Claude Code / Gemini CLI = specialist coding workers
- ThinkPad = NEEWA-EDGE-01 trusted local worker
- RunPod Serverless = on-demand GPU worker
- GPT-Live-1 = preferred natural voice front end
- Council + Governor + Done Gate = independent validation and control
- Git + structured Markdown/YAML = portable organizational memory

## Non-negotiable principles

1. The owner remains final authority.
2. NEEWA is expected to challenge weak assumptions; she is not a yes-sir assistant.
3. Research claims must disclose evidence and gaps.
4. No worker self-certifies critical work.
5. "Done" is an evidence state, not an LLM statement.
6. Every task has a budget, stop condition, and acceptance contract.
7. Failing loops stop automatically instead of consuming unlimited tokens.
8. Provider/model failure must not stop the whole system when an approved fallback exists.
9. Secrets are never stored in Git or normal project Markdown.
10. NEEWA's durable knowledge must survive replacement of any model or agent framework.

Start with: `00_START_HERE/00_EXECUTIVE_SUMMARY.md`.
