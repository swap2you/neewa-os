# Autonomy RFC-v4 — evidence report

## Outcome

**READY_FOR_OWNER_ACCEPTANCE** for this proven scope only:

- NEEWA Conversation software jobs against an existing approved Node/TypeScript repo (`KidsProjects/ScienceQuest`)
- NEEWA Conversation research jobs grounded in OWNER.md / PROJECT_ACCESS.md (not the Ganesh template)
- DISCOVERED projects (Bhāva / Vāṇī) remain blocked for A1 writes
- Receipt-totals Python sandbox path remains a regression PASS

Not DONE. Not all-purpose autonomy. Product jobs stay `OWNER_REVIEW`. Home spoken voice remains **PENDING_PHYSICAL**. Cross-provider failover remains **UNVERIFIED**. Council independence remains **INDEPENDENCE_UNAVAILABLE**.

## Environment

- origin/main and neewa-core-01: `75777e77d748b36d7047fce1856d000bc9405c4a`
- Effective skill SHA-256: `e454b3e2b3d1e7bd791a6caf2086163a1fa1893ecb3599a9b236276e28d8d482` (`/home/ubuntu/.hermes/skills/operations/windows-worker-bridge/SKILL.md`)
- Runner heartbeat live at 2026-09-17T18:31:03Z; host flock runner was not restarted during the owner smoke job
- Windows worker pwsh pid 35488; Cursor Agent CLI `2026.09.15-d2fe57e`
- RFC lock: `AI-OPS/delivery/autonomy-baseline/BASELINE_LOCK_v4.json` (additive on REQ-v3; owner_approved=false)

## Live Conversation jobs

**E2E-A software** (existing approved repo, not receipt-totals / changelog / project-status):

1. `JOB-20260917T181511Z-3B2E3882-AUTO` FAILED after 3 Cursor children. Root cause: `Resolve-ApprovedRepo` returned `KidsProjects` instead of `KidsProjects\ScienceQuest`, so expected files were checked at the parent root. Bounded retries repeated the same defect until the worker fix.
2. `JOB-20260917T182305Z-C4D25491-AUTO` Conversation returned the job_id at INTAKE. Runner completed while chat was closed. CC01 implemented the scoped change; CC02 independently reran `npm test`. Parent: OWNER_REVIEW, independent_rerun=PASS, traceability all_pass.

Observed files: `docs/KNOWN_LIMITATIONS.md` (npm test / vitest run sentence) and `src/progress/storage.test.ts` (no account identifiers). Independent host rerun: 4 files / 26 tests passed. Cost: conservative **$1.00** reserved (two Cursor calls); actual USD unavailable-until-measured; tokens 18664/1924 then 26618/821.

**E2E-B research** (not Ganesh): `JOB-20260917T181533Z-F85975A8-AUTO` OWNER_REVIEW. 720-word briefing cites OWNER.md and PROJECT_ACCESS.md. SOURCE_PACK/SRC-01 not used. independent_rerun=LOCAL_CORPUS. Cursor cost $0.

**Regression:** `JOB-20260917T172008Z-74B7B1EF-AUTO` still OWNER_REVIEW. Local `test_local_receipt_totals.py`: 3 OK.

## P0 matrix

| Pathway | Result | Evidence |
| --- | --- | --- |
| Intake job_id | PASS | hermes stdout for both live jobs |
| Project routing | PASS | ScienceQuest ACCESS_APPROVED; PRJ-WANI BLOCKED unit |
| Stack-aware design | PASS | design.stack=node-typescript, create_new_package=false, npm test |
| AC traceability | PASS | five REQ rows with check/result for E2E-A |
| Independent rerun | PASS | CC02 + host vitest 26 passed |
| DISCOVERED A1 | PASS | unit `test_discovered_job_blocks_before_cursor` |
| Research corpus | PASS | E2E-B OWNER.md / PROJECT_ACCESS.md |
| A2/A3 / denied repo | PASS | existing unit + prior OratsUtil BLOCKED |
| Cost honesty | PASS | conservative $0.50/call; actual_usd null |
| Restart/concurrency | PARTIAL | flock runner live; `--once` pid lease stalled VALIDATING until expiry — fixed in `75777e7` |
| Home voice | OUT_OF_SCOPE | PENDING_PHYSICAL |
| Cross-provider | UNVERIFIED | CLIs not installed |

## Remaining limitations

- Child-folder Cursor workspace required a live miss then a worker fix; first ScienceQuest parent is FAILED evidence, not hidden.
- Worker still writes `RELEASE_CANDIDATE.md` into the target repo when listed in expected_paths. Delete `KidsProjects/ScienceQuest/RELEASE_CANDIDATE.md` if you do not want that file in the kids tree.
- Independent review is deterministic_only.
- Cursor actual billed USD is not exposed by the CLI JSON used here.
- Mixed stacks (manan, aarohan) are catalogued, not live-proven.

## Rollback

`git -C /opt/neewa/neewa-os checkout d3b9f8e` then `git pull` is not needed; to undo v4: reset to `d3b9f8e` (v3 Conversation path). Do not force-push. Revert ScienceQuest edits by removing the added limitations bullet, the vitest case, and `RELEASE_CANDIDATE.md`.

## Owner next action

In NEEWA Conversation, review the two OWNER_REVIEW jobs (`JOB-20260917T182305Z-C4D25491-AUTO` and `JOB-20260917T181533Z-F85975A8-AUTO`). They are not DONE and were not published. No further Cursor engineering prompt is required for this scope.
