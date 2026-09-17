# NEEWA Conversation orchestration

NEEWA coordinates work. The owner speaks in Hermes Conversation.
NEEWA selects a verified worker, submits a durable job, and reports evidence.
The owner does not paste the same assignment into Cursor.

## Path

```
Conversation
  -> 12_SCRIPTS/neewa_orchestrate.py
  -> /workspace/windows-jobs/inbox  (Hermes bind-mount)
  -> neewa-windows-worker (outbound Tailscale SSH)
  -> allowlisted action (cursor_call | workspace_inventory | ping)
  -> evidence in windows-jobs/done or failed
  -> records in windows-jobs/records
```

## States

`QUEUED → DISPATCHED → RUNNING → VALIDATING → COMPLETED`

Exceptions: `BLOCKED`, `FAILED`, `CANCELLED`.

Each state is timestamped on the job record. `COMPLETED` requires worker
validation of expected files when they were declared. A model claim is not evidence.

## Routing

| Capability | Worker | Notes |
| --- | --- | --- |
| code_implementation | cursor-agent-cli | default; A1 on approved repos |
| code_review | cursor-agent-cli | read-only `--mode ask` |
| project_inventory | neewa-windows-worker | A0 |
| host_status | neewa-windows-worker | A0 ping |
| gui_operation | cua-driver | local interactive session only; not inbox-routed |

Claude Code, Codex, Gemini, and Cowork are inventoried and **not routable**
until a programmable CLI is verified. Do not invent workers.

## Approval

- A0: inventory, ping, read-only ask
- A1: routine coding/tests in an approved personal repo or cursor-sandbox
- A2/A3: cannot be enqueued; worker refuses

`--trust` is headless workspace trust for that approved repo.
`--force` is used only for authorized writes.
--sandbox enabled is omitted on Windows (CLI requires macOS/Linux). Headless uses `--trust` for the approved workspace only.

## Duplicate and timeout

The same `job_id` cannot be enqueued twice. The worker stamp file prevents
re-execution. Timeouts kill the Agent CLI process tree (`taskkill /T`).
Windows offline: jobs remain in inbox until the worker reconnects.
The server stays up independently.

## Parent autonomous jobs

Software objectives also run `12_SCRIPTS/neewa_autonomy.py`, which keeps a
parent record independent of the chat session. Child Cursor work still uses
this inbox path.

`WAITING` parks a job when no verified coding worker is routable.

