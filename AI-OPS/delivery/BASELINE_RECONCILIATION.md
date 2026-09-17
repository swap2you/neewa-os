# Baseline reconciliation (pack v2.0 vs live repo)

Inspected 2026-09-17T17:15:00Z. Pack snapshot commit `8e85edd` is historical.
Live local/origin/core: `b6117375560c5e52406e888714fc5f35f226432a`.
Pack static verifier: PASS (package consistency only; not NEEWA acceptance).
Windows worker: pwsh pid 35488. Cursor Agent CLI: `2026.09.15-d2fe57e`.
Core runner pid 2129543, heartbeat present. Home spoken voice: PENDING_PHYSICAL (out of scope).

## Pack observation vs current code

| Pack claim at 8e85edd | Live at b611737 | Disposition |
| --- | --- | --- |
| `build_requirements()` always JSON project-status | Production derives REQs from the objective; fixture isolated in `neewa_autonomy_fixture.py` | PARTIAL — still software-CLI biased; research not implemented |
| `run_council()` predetermined malformed-JSON | Council inspects actual design; material findings optional | PARTIAL — deterministic_only, not an independent model |
| Selects Cursor then `implement_local()` | Production `_submit_cursor` via Windows inbox | PARTIAL — research path still returns after CLASSIFIED |
| Fixed traceability IDs / unearned PASS | Dynamic IDs; missing TEST_JSON is not PASS | PARTIAL — some REQ kinds still weakly evidenced |
| `budget_allows` is invocation-count | Conservative $0.50/call; ceiling 0 and unknown block | PARTIAL — no atomic reservation field |
| Conversation parent SDLC unverified | Changelog job `JOB-20260917T161956Z-AUTO` reached OWNER_REVIEW | Historical evidence only (NEG-20); cannot satisfy this pack’s two new objectives |

## Gap ledger at recon time

| Gap | Severity | Status | Proof / remaining |
| --- | --- | --- | --- |
| GAP-01 objective-general REQs | P0 | PARTIAL | Software objectives differ; research/document still unused |
| GAP-02 genuine council | P0 | PARTIAL | Evidence-backed deterministic review; `INDEPENDENCE_UNAVAILABLE` |
| GAP-03 real Cursor child | P0 | VERIFIED historically | Changelog CC01–CC03; must repeat on a **new** objective |
| GAP-04 dynamic traceability | P0 | PARTIAL | TEST_JSON required; security still design-scoped |
| GAP-05 async recovery | P0 | PARTIAL | Host runner + heartbeat; no fencing lease |
| GAP-06 execution-boundary auth | P0 | PARTIAL | Denied repo/A3 tests exist; job JSON `owner_decision` is forgeable |
| GAP-07 honest billing | P0 | PARTIAL | Estimate vs unknown distinguished; reservation missing |
| GAP-08 cross-provider fallback | P1 | UNVERIFIED | No second coding CLI; WAITING is correct |
| GAP-09 live Conversation + skill | P0 | PARTIAL | Skill submits software parents; research undocumented; new E2E required |
| GAP-10 observability / false PASS | P1 | PARTIAL | Sidecar harvest; worker ConvertTo-Json truncation remains |
| GAP-11 Home voice | Separate | PENDING_PHYSICAL | Not opened |

## Reuse, do not duplicate

Keep `neewa_orchestrate.py`, Windows inbox, `cursor_call`, worker/provider registries, and the Conversation skill. Do not add public listeners, paid providers, or a second queue.
