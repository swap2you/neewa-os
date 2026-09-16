# NEEWA backend work order — Cursor dispatches; owner does not paste

Durable copy of the Jarvis V1 dispatch contract. Cursor is the sole Git writer.
NEEWA on `neewa-core-01` is a read-only reviewer / bounded executor.

## Dispatch

1. Write a short packet at `AI-OPS/delivery/work-orders/<job-id>.md`.
2. Commit and push the authorized personal repo.
3. Sync the host checkout `/opt/neewa/neewa-os` via the existing host Git pull.
4. Ask NEEWA (authenticated SSH one-shot) to read that exact path in the
   read-only mount. Never paste the whole pack into chat.

## Current packet

`AI-OPS/delivery/work-orders/WO-20260916-jarvis-v1.md`

Required parsable fields: `job_id`, `source_commit`, `host_snapshot_timestamp`,
`voice_snapshot_timestamp`, `observed_state`, `defects`, `actions_performed`,
`actions_not_performed`, `approval_required`, `final_status`
(`DONE | BLOCKED | APPROVAL_REQUIRED`).

The host must never claim a Windows physical/UI/audio PASS.
