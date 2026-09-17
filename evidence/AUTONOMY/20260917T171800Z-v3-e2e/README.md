# Autonomy v3 live Conversation evidence

Pack: NEEWA_AUTONOMY_V2 (static verifier PASS; not live acceptance).
Baseline: AUTONOMY-REQ-v3-DES-v3-ACCEPT-v3 (`AI-OPS/delivery/autonomy-baseline/BASELINE_LOCK.json`).
Git: `fa38cca` on origin/main and neewa-core-01.
Independence: INDEPENDENCE_UNAVAILABLE (deterministic_only).
Home spoken voice: PENDING_PHYSICAL (not opened).

## Conversation origin (not a local controller substitute)

| Prompt | Hermes output | Parent |
| --- | --- | --- |
| conversation-software-prompt.txt | hermes-software-out.txt | JOB-20260917T172008Z-74B7B1EF-AUTO INTAKE |
| conversation-research-prompt.txt (1st) | hermes-research-out.txt | JOB-20260917T172035Z-F4A46AE1-AUTO BLOCKED A2_OWNER_GATE on "Do not publish" |
| conversation-research-prompt.txt (2nd, after negation fix) | hermes-research2-out.txt | JOB-20260917T172150Z-2E88BFE7-AUTO research_report INTAKE |
| conversation-capabilities-prompt.txt | hermes-capabilities-out.txt | truthful skill report |

Runner pid 2135184 continued after Conversation returned.

## E2E-A software (receipt-totals, not changelog / not project-status)

- Parent `JOB-20260917T172008Z-74B7B1EF-AUTO` origin=conversation workflow=sdlc
- Child `JOB-20260917T172008Z-74B7B1EF-AUTO-CC01` execution_worker=cursor-agent-cli
- Product `C:\Users\swap2\NEEWA-Personal\cursor-sandbox\local_receipt_totals\`
- Independent unittest 2026-09-17T17:26Z: 3 OK (happy path, missing input, non-numeric amount)
- Independent missing.csv: exit 1
- Cost: conservative $0.50; tokens 17611 / 4717
- State OWNER_REVIEW, not DONE

## E2E-B research (Ganesh Chaturthi katha)

- Parent `JOB-20260917T172150Z-2E88BFE7-AUTO` workflow=research_report
- Worker local-research-synthesizer (no software CLI)
- Cites SRC-01..SRC-04 from `14_REFERENCE/devotional_sources/SOURCE_PACK.md`
- Owner tradition selection listed; not published
- State OWNER_REVIEW, not DONE

## Other

- First research Conversation job BLOCKED A2 is retained (false-positive keyword, then fixed).
- Cross-provider failover UNVERIFIED.
- Fixture demo-status remains regression-only.
