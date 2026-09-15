# Step 5 — LiteLLM Gateway

Purpose:
- unified model endpoint;
- virtual keys;
- spend tracking;
- per-project budgets;
- rate limits;
- fallbacks;
- model aliases.

Run LiteLLM outside the NEEWA reasoning sandbox as part of the control/governance plane.

Create initial model aliases:
- `neewa-premium`
- `neewa-balanced`
- `neewa-routine`
- `neewa-extreme`

Create separate virtual key scopes for:
- NEEWA chief agent;
- Council;
- research;
- media;
- test environment.

No worker receives raw provider master keys when a scoped virtual key will work.
