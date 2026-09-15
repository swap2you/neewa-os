# Model Routing Policy

## Principle

Use the least expensive approved model that can meet the acceptance contract.

## Aliases

### `neewa-premium`
Default: GPT-5.6 Sol, High reasoning.

Use for:
- owner strategic conversation;
- architecture;
- business analysis;
- difficult research synthesis;
- Council chair;
- complex ambiguity.

### `neewa-routine`
Default: GPT-5.6 Luna or approved low-cost model.

Use for:
- summaries;
- extraction;
- classification;
- status generation;
- simple transformations;
- repetitive agent tasks.

### `neewa-balanced`
GPT-5.6 Terra or equivalent approved model.

Use when Luna is not reliable enough but Sol is unnecessary.

### `neewa-extreme`
GPT-6 Astra.

Allowed only when:
- Sol has failed or confidence remains below threshold;
- business value justifies cost;
- the job is explicitly marked exceptional.

### `neewa-local`
Qwen/Gemma/other reviewed local model.

Use only on sanitized inputs unless the model/runtime is inside the approved secure environment.

## Coding routing
Implementation is normally delegated to:
1. Codex
2. Claude Code
3. Gemini CLI
4. selected fallback

Writer cannot be the sole final reviewer.
