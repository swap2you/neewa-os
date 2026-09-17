# ARCHITECTURE — autonomy platform DES-v3

**Version:** DES-v3  
**Status:** engineering baseline  
**Owner approval:** not claimed  
**Reuse:** `neewa_orchestrate.py`, Windows inbox, `cursor_call`, `neewa_autonomy.py`, host `neewa_autonomy_runner.sh`

## Control planes

1. Conversation intake (Hermes skill) — submit parent, return job_id, do not hold the session.
2. Parent orchestrator — requirements, design, council, budget, auth, state machine.
3. Child execution — existing Windows poller + Cursor Agent CLI for software.
4. Independent validation — unittest / citation checks / artifact presence; worker claims are untrusted.
5. Owner authorization — A2/A3 blocked until an authenticated channel exists; job JSON is not that channel.

Home/HUD voice is not on this path.

## Workflows

| Workflow | Trigger | Execution |
| --- | --- | --- |
| `sdlc` | build/implement/tests/release software | Cursor child via inbox |
| `research_report` | katha/research/investigate without build | Local source-grounded synthesizer + citation validator |
| `answer` / `known_procedure` | questions, inventory | Existing orchestrate capabilities |
| `owner_gate` | A2/A3 | BLOCKED |

Research **must not** emit a Python CLI design.

## State machine

`INTAKE → CLASSIFIED → REQUIREMENTS → DESIGN → COUNCIL → BASELINE_LOCKED → PLANNED → EXECUTING → TESTING → VALIDATING → RELEASE_CANDIDATE → OWNER_REVIEW`

Also: `WAITING`, `BLOCKED`, `FAILED`, `CANCELLED`. `DONE` is owner-only. Child COMPLETED never implies parent DONE.

## Durability

- Parent/child IDs include a random suffix; same-second submits cannot collide.
- `save_json` writes a temp file then `os.replace`.
- Runner heartbeat plus lease `{owner, expires_at, fencing}` so a second runner does not double-dispatch.
- Restart reloads JSON and resumes; duplicate child submit is skipped when `active_child_id` exists.

## Budget

```
remaining = ceiling - consumed - reserved
```

Before a chargeable Cursor call: if estimate unknown → COST_UNKNOWN block; if remaining < estimate → BUDGET_EXHAUSTED; else add reservation, dispatch, settle to conservative estimate (or measured USD when present). Tokens are counts, not dollars. Config ceilings are not new spend authorization.

## Authorization

Trusted: worker allowlist, denied repo names, authenticated worker identity, frozen baseline hashes.  
Untrusted: owner objective, README, model output, child logs, mutable job JSON including `owner_decision`.

A2/A3 always block at execution. Keyword lists are a helper, not the only gate: publication/spend/financial action classes are evaluated on the owner objective and repo, not on generated worker prompts.

## Council

`independence_class = deterministic_only` until a second authenticated model is inventory-verified. Reviewer identity persisted. No mandatory material finding.

## Spec integrity

After council, `spec_sha256` = SHA-256 of requirements.json + approved design. Validators recompute; mismatch → SPEC_DRIFT, no RC.

## ADR

| ID | Decision |
| --- | --- |
| ADR-01 | Reuse Windows orchestrator; do not add a second queue or public listener. |
| ADR-02 | JSON + lockfile/lease is sufficient; SQLite not required this release. |
| ADR-03 | Research is in-process from an approved local source pack; no paid search API. |
| ADR-04 | Cross-provider failover UNVERIFIED; WAITING is the honest state. |
| ADR-05 | Cursor remains sole Git writer for software workspaces. |
| ADR-06 | Engineering baseline ≠ owner-approved product direction. |
