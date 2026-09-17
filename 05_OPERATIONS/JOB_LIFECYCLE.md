# Job Lifecycle

States:
`NEW -> TRIAGED -> RESEARCHING -> PLANNED -> EXECUTING -> VALIDATING -> REWORK -> DONE`

Exceptional:
`BLOCKED`, `OWNER_DECISION`, `PAUSED`, `FAILED`, `CANCELLED`.

Windows Conversation bridge (durable inbox records) uses:
`QUEUED -> DISPATCHED -> RUNNING -> VALIDATING -> COMPLETED`
with `BLOCKED`, `FAILED`, `CANCELLED`, and `WAITING`. See `AI-OPS/delivery/ORCHESTRATION.md`.
Autonomous parent jobs use `12_SCRIPTS/neewa_autonomy.py` states through `OWNER_REVIEW`.
`COMPLETED` maps to `DONE` for repository job files when evidence is copied.

## Rules
- One accountable owner/chief agent per job.
- One primary implementation worker per write scope.
- No parallel agents editing the same files unless explicitly partitioned.
- Every job has a budget.
- Every job has an acceptance contract.
- Every job stores evidence and cost.
