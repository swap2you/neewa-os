# Job Lifecycle

States:
`NEW -> TRIAGED -> RESEARCHING -> PLANNED -> EXECUTING -> VALIDATING -> REWORK -> DONE`

Exceptional:
`BLOCKED`, `OWNER_DECISION`, `PAUSED`, `FAILED`, `CANCELLED`.

## Rules
- One accountable owner/chief agent per job.
- One primary implementation worker per write scope.
- No parallel agents editing the same files unless explicitly partitioned.
- Every job has a budget.
- Every job has an acceptance contract.
- Every job stores evidence and cost.
