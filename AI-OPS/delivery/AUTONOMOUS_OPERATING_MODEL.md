# Autonomous operating model

NEEWA is the coordinator. Cursor is the Git writer. A chat reply is not DONE.

## Executable path

Owner objective
→ `12_SCRIPTS/neewa_autonomy.py` classifies intent
→ durable parent job under `windows-jobs/autonomy` or `--root`
→ lightest workflow that can satisfy the request
→ software path: requirements, design, council, worker, tests, done-gate, owner review
→ child Windows jobs still use `neewa_orchestrate.py` + the existing inbox

Conversation can close. The parent job JSON is the source of truth.
NEEWA only claims background execution when that record exists and a worker
or this controller owns the next state.

## Parent states

`INTAKE → CLASSIFIED → REQUIREMENTS → DESIGN → COUNCIL → PLANNED → EXECUTING → TESTING → VALIDATING → RELEASE_CANDIDATE → OWNER_REVIEW`

Exceptions: `WAITING`, `BLOCKED`, `FAILED`, `CANCELLED`.

`DONE` is not written by the local SDLC runner. Owner review is required
before any public release. `evaluate_autonomy_done` still refuses unknown
evidence and missing tests.

## What this does not do

- It does not open listeners or Funnel.
- It does not invent Claude/Codex/Gemini workers.
- It does not spend new paid APIs.
- It does not mark NEEWA Home spoken voice as working.
