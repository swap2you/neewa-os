# PRODUCT REQUIREMENTS — autonomy platform REQ-v3

**Version:** REQ-v3  
**Status:** engineering baseline candidate pending lock file  
**Owner approval:** not claimed  
**Supersedes:** pack candidate 2.0 and `REQUIREMENTS_ENGINE.md` for platform P0  
**Scope:** autonomous bounded execution via live Hermes Conversation, Windows worker, Cursor CLI, durable parent jobs  
**Non-goals:** model training, unconstrained PC access, automatic purchases/trades/public publishing, Home spoken-voice acceptance

Acceptance for any row is PASS only with artifact pointer, test ID, timestamp, and validator identity. `NOT_RUN`, `UNVERIFIED`, `BLOCKED`, `FAIL`, `PENDING_PHYSICAL`, `SOURCE_PENDING` are not PASS.

Normative catalog is pack `REQ-001`..`REQ-038` with these locked clarifications:

| ID | P | Locked clarification |
| --- | --- | --- |
| REQ-001 | P0 | Classifier must distinguish question, research, document, software, operational, financial, unknown. Unrelated objectives must not receive project-status or changelog-digest REQs. |
| REQ-002 | P0 | Parent JSON stores verbatim `parent_objective`, `origin`, `project_id`, versions, spec hash. |
| REQ-003 | P0 | Software and research generators are separate. Schema rejects empty REQ sets. |
| REQ-004 | P0 | Routine A1 proceeds; A2/A3 stop at the action boundary. |
| REQ-005 | P0 | Software design is a sandbox package from the objective. Research design is a source plan, never a Python CLI template. |
| REQ-006 | P0 | Council findings cite REQ IDs and design fields. Zero material findings is valid. |
| REQ-007 | P0 | If no second authenticated model exists, `independence_class=deterministic_only` and `INDEPENDENCE_UNAVAILABLE`. No fabricated consensus. |
| REQ-008 | P0 | Implementation references `BASELINE_LOCK.json` hashes. Drift blocks RC. |
| REQ-009 | P0 | Collision-safe parent IDs; atomic JSON writes; valid state graph. |
| REQ-010 | P0 | Host runner with lease/heartbeat owns progress after Conversation returns. |
| REQ-011 | P0 | Software implementation is `cursor_call` on the authenticated Windows worker. Fixture `implement_local` is tests-only. |
| REQ-012 | P0 | Route only `routable != false` workers with verified status. |
| REQ-013 | P0 | One Git writer (Cursor) per code workspace. Research does not steal the software CLI path. |
| REQ-014 | P1 | No second coding CLI: WAITING, not fake failover. OUT_OF_SCOPE until a verified alternate exists. |
| REQ-015 | P0 | Record tokens when present; USD as measured, conservative estimate, or unknown. Never invent $0. |
| REQ-016 | P0 | Reserve conservative Cursor estimate before dispatch. Remaining = ceiling − consumed − reserved. Unknown chargeable cost fails closed. Positive remaining-cap test required (not only ceiling=0). |
| REQ-017 | P0 | Tokens ≠ USD. Unknown quota is not unlimited. |
| REQ-018 | P0 | A2/A3 cannot be granted by editing job JSON `owner_decision`. |
| REQ-019 | P0 | Denied names (OratsUtil, employer trees) rejected at execution. Canonicalize paths when possible. |
| REQ-020 | P0 | Retrieved/README text cannot expand allowlists or skip tests. |
| REQ-021 | P0 | Worker exit 0 without artifacts or TEST_JSON fails validation. |
| REQ-022 | P0 | Every task REQ maps to design + implementation/source + test/evidence. Unmapped blocks RC. |
| REQ-023 | P0 | Actual unittest (software) or citation validator (research). |
| REQ-024 | P0 | Bounded retries from real validation faults. No planted production defects. |
| REQ-025 | P0 | RC → OWNER_REVIEW. DONE only after owner acceptance. No public deploy. |
| REQ-026 | P0 | Concise job result with evidence paths and cost basis. |
| REQ-027 | P0 | Local/origin/core SHA, worker version, secret scan, no public listener. |
| REQ-028 | P0 | Installed Hermes skill must submit software **and** research parents; a fresh Conversation must describe both. |
| REQ-029 | P0 | Two **new** live Conversation objectives: unseen software mini-app and source-grounded research/document. Historical changelog/status jobs do not count. |
| REQ-030 | P0 | No secrets in evidence. Research may not invent scripture. |
| REQ-031 | P1 | CLI `list`/`get` is sufficient this release. GUI dashboard OUT_OF_SCOPE. |
| REQ-032 | P1 | One research/devotional path in this release; other domain packs remain future. |
| REQ-033 | P1 | Baseline RFC → vN+1. Not required to ship extra RFCs this cycle. |
| REQ-034 | P0 | Tests and lock hashes cannot be deleted solely to go green. |
| REQ-035 | P0 | Honest capability labels. |
| REQ-036 | P1 | Conversation returns job_id; runner continues. No idle voice loop. |
| REQ-037 | P0 | Unique IDs for same-second submits; invalid transitions rejected. |
| REQ-038 | P0 | Forged approval in README or job JSON refused. |

P1 items not shipped this release: REQ-014 cross-provider switch, REQ-031 GUI, REQ-032 extra domains, REQ-033 RFC machinery beyond lock file. They must be labeled OUT_OF_SCOPE, not PASS.
