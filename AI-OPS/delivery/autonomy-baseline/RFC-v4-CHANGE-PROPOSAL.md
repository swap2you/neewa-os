# RFC-v4 — change proposal on locked REQ-v3

**Status:** internal engineering RFC. Does **not** replace REQ-v3 hashes. Does **not** claim owner approval.  
**Supersession:** additive. v3 remains the frozen platform lock; v4 adds P0 clarifications for remaining gaps found after live Conversation E2E at `d3b9f8e`.

Observed live: owner smoke job `JOB-20260917T175316Z-68DA9459-AUTO` (markdown_task_counter) was VALIDATING at recon. Do not interrupt it. Do not reuse receipt-totals, changelog, project-status, or Ganesh katha as this RFC's proof.

## Uncovered gaps (v3 still true, incomplete)

| ID | P | Gap | Acceptance procedure |
| --- | --- | --- | --- |
| V4-G01 | P0 | Planner defaults to a new Python CLI even for existing Node/TS/mixed repos | Inspect workspace markers or `11_CONFIG/project_stacks.json`; design names real files and the repo's test command |
| V4-G02 | P0 | Traceability PASSes functional REQs from any unittest | Each REQ has an `ac` + `check`; missing file or skipped AC → FAIL/UNVERIFIED |
| V4-G03 | P0 | Independent validation trusts implementer TEST_JSON | After implement, a distinct validation child or local citation check must rerun; if it cannot, status UNVERIFIED not PASS |
| V4-G04 | P0 | Project routing ignores registry access_stage | DISCOVERED (Bhāva/Vāṇī) BLOCKED; ACCESS_APPROVED/CONNECTED map to canonical workspace_path |
| V4-G05 | P0 | Research is a Ganesh outline template | Arbitrary research uses matching corpus files; word-count/citation map; else SOURCE_PENDING |
| V4-G06 | P0 | Job lease is runner-global, not per-job fencing | Per-job lease owner/expiry; second `runner --once` must not double-dispatch EXECUTING children |
| V4-G07 | P1 | Stacks other than Python stdlib + one Node/TS repo | Unsupported stacks labeled UNSUPPORTED, not fake Python |

## Independence

No second authenticated coding/review CLI is installed. Review class: `deterministic_only` / `INDEPENDENCE_UNAVAILABLE`.

## Out of scope

Home spoken voice PENDING_PHYSICAL. Cross-provider failover UNVERIFIED. Public deploy. Paid providers. Employer/trading trees.
