# Design council — autonomy v3

**review_id:** REV-20260917-AUTONOMY-V3  
**independence_class:** deterministic_only  
**reviewer_identity:** cursor-engineering-adversarial-review (same session as implementer)  
**limitation:** INDEPENDENCE_UNAVAILABLE — no second authenticated coding/review model is installed. This is not multi-model consensus and is not owner approval.

## Round 1 — adversarial findings

| ID | Sev | REQ | Observed | Correction |
| --- | --- | --- | --- | --- |
| C-01 | blocker | REQ-003,005,029 | `advance_job` returns after CLASSIFIED for non-sdlc; research would never produce a report | Implement `research_report` end-to-end |
| C-02 | blocker | REQ-005,014 | `initial_design` always emits a Python CLI package | Workflow-specific design |
| C-03 | blocker | REQ-018,038 | `owner_decision==approved` in job JSON grants A2/A3 | Ignore mutable job JSON; A2/A3 always block |
| C-04 | blocker | REQ-016 | No `reserved` field; only ceiling=0 was live-tested | Reserve before Cursor; positive remaining-cap test |
| C-05 | major | REQ-037 | Job IDs are second-precision | Random suffix |
| C-06 | major | REQ-009,010 | Heartbeat exists; no lease/fencing; save_json is not atomic | Atomic replace + lease |
| C-07 | major | REQ-007 | Council could be mistaken for independent review | Persist independence_class |
| C-08 | major | REQ-008,034 | Jobs do not store spec hash | spec_sha256 + drift check |
| C-09 | major | REQ-029,NEG-20 | Changelog E2E cannot close this pack | Two new Conversation objectives |
| C-10 | minor | REQ-015 | First Cursor children lacked tokens until sidecar merge | Keep sidecar harvest; record estimate vs tokens |

No finding was invented to force disagreement. C-07 is a disclosure, not a fake design defect.

## Round 2 — dispositions

All blocker/major items accepted into REQ-v3 / DES-v3 / ACCEPT-v3. Residual risks: worker ConvertTo-Json truncation (mitigated by sidecar), no independent reviewer, no second coding CLI, Home voice pending.

**Disposition:** internal engineering baseline. Not owner-approved direction.
