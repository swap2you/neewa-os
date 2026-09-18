# Autonomous operating model

NEEWA is the coordinator. Cursor is the Git writer. A chat reply is not DONE.

## Executable path

Conversation
→ `neewa_autonomy.py mission-submit` (persistent mission on the Windows-jobs bind-mount)
→ user-systemd `neewa-autonomy-runner.service` running `neewa_autonomy_runner.sh`
→ supervisor state machine, then parent job `JOB-*` created only after persist
→ requirements derived from the objective
→ design from those requirements
→ council inspects the written design (evidence per finding)
→ child `cursor_call` via `neewa_orchestrate.py` and the Windows worker
→ unittest evidence + independent traceability
→ release candidate → OWNER_REVIEW
→ on recoverable failure: evidence classify → optional one-pass advisor consult → new job (max 3)

Bare `submit` without `--unattended` still creates a parent job for compatibility.
A chat reply is not DONE. Hermes no-agent cron is not the autonomy runner.

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
