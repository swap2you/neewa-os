# System Architecture

```text
OWNER
  |
  +-- Voice/Text UI (GPT-Live-1 + text fallback)
  |
  v
NEEWA CORE
  Hermes Agent inside NemoClaw/OpenShell
  |
  +-- Constitution / Memory / Project Registry
  +-- Research Protocol
  +-- Task Planner
  +-- Governor interface
  |
  v
LITELLM GATEWAY
  |
  +-- GPT-5.6 Sol High (premium reasoning)
  +-- GPT-5.6 Luna (routine)
  +-- GPT-6 Astra (exception)
  +-- OpenRouter governed models
  +-- Nous tools/models
  |
  +--> Langfuse traces / cost / evaluation
  |
  v
WORKFORCE
  |
  +-- NEEWA-EDGE-01 (ThinkPad)
  |    +-- OpenHands Agent Canvas
  |    +-- Codex
  |    +-- Claude Code
  |    +-- Gemini CLI
  |    +-- Cursor
  |    +-- local models/media tools
  |
  +-- RunPod GPU workers (ephemeral)
  |
  v
VALIDATION
  +-- deterministic checks
  +-- independent reviewer
  +-- Council when risk requires
  +-- Done Gate
  |
  v
OWNER GATE only for policy-defined actions
```

## Design constraints

- cloud control plane is always on;
- GPU compute is not always on;
- worker agents are disposable;
- durable knowledge is stored outside individual chats;
- no agent receives global credentials by default;
- model/provider choice is policy-driven, not personality-driven.
