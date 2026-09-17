# Autonomous operating model

NEEWA is the coordinator. Cursor is the Git writer. A chat reply is not DONE.

## Executable path

Conversation
→ `neewa_autonomy.py submit` (parent job on the Windows-jobs bind-mount)
→ host runner `neewa_autonomy_runner.sh` (survives chat disconnect)
→ requirements derived from the objective
→ design from those requirements
→ council inspects the written design (evidence per finding)
→ child `cursor_call` via `neewa_orchestrate.py` and the Windows worker
→ unittest evidence + independent traceability
→ release candidate → OWNER_REVIEW

The project-status JSON CLI is a **regression fixture** (`--fixture demo-status` /
`neewa_autonomy_fixture.py`). It is not the production path.

## Parent states

`INTAKE → CLASSIFIED → REQUIREMENTS → DESIGN → COUNCIL → PLANNED → EXECUTING → TESTING → VALIDATING → RELEASE_CANDIDATE → OWNER_REVIEW`

Exceptions: `WAITING`, `BLOCKED`, `FAILED`, `CANCELLED`.

`EXECUTING` parks on a child inbox job. Restarting the runner harvests that child
instead of replaying completed work.

Approval is re-checked at the cursor_call boundary (repo, blocked intents, A2/A3).
Budget uses measured cost when present, otherwise the conservative Cursor estimate
in `11_CONFIG/budgets.json`. Unknown remaining allowance blocks chargeable work.

## What this does not do

- It does not open listeners or Funnel.
- It does not invent Claude/Codex/Gemini workers.
- It does not spend new paid APIs.
- It does not mark NEEWA Home spoken voice as working.
