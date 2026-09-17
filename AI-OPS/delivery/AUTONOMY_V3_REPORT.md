# Autonomy v3 — consolidated evidence report

## Outcome

**PLATFORM_READY_FOR_OWNER_ACCEPTANCE** for the Conversation autonomy path described by REQ-v3. Not DONE. Product jobs remain `owner_decision=pending_review`. Home spoken voice remains **PENDING_PHYSICAL**. Cross-provider failover remains **UNVERIFIED**. Independent multi-model review remains **INDEPENDENCE_UNAVAILABLE**.

## Environment

- Pack: `NEEWA_AUTONOMY_V2.zip` static verifier PASS (package only)
- Baseline ID: `AUTONOMY-REQ-v3-DES-v3-ACCEPT-v3`
- Approver classification: internal engineering baseline (not owner-approved direction)
- Inspected then implemented from HEAD `b611737`; final SHA `fa38cca`
- origin/main and neewa-core-01: `fa38cca`
- Windows worker pwsh pid 35488; Cursor Agent CLI `2026.09.15-d2fe57e`
- Autonomy runner pid 2135184
- Effective skill: `/home/ubuntu/.hermes/skills/operations/windows-worker-bridge/SKILL.md`

## What changed

Reused Windows orchestrator + `cursor_call`. Locked REQ/DES/ACCEPT. Added research workflow, budget reservation, collision-safe IDs, atomic JSON, runner lease, spec hash, and untrusted job-JSON approvals. Fixture `demo-status` remains labeled regression-only. Historical changelog job does not count (NEG-20).

## Design council

Two deterministic rounds, same Cursor session, `independence_class=deterministic_only`. Blockers C-01..C-09 accepted into v3. Zero fabricated material findings.

## Live scenarios

**E2E-A** objective: local receipt-totals CSV CLI (not project-status, not changelog).  
Conversation `hermes-software-out.txt` → `JOB-20260917T172008Z-74B7B1EF-AUTO` → child CC01 `cursor-agent-cli` → `local_receipt_totals` → independent 3 unittest OK + missing-file exit 1 → OWNER_REVIEW. Cost conservative $0.50; tokens 17611/4717.

**E2E-B** objective: 8-minute Ganesh Chaturthi katha, do not publish.  
First Conversation job `JOB-20260917T172035Z-F4A46AE1-AUTO` BLOCKED A2 on “Do not publish” (keyword false positive). Fix `fa38cca`. Second Conversation job `JOB-20260917T172150Z-2E88BFE7-AUTO` research_report → SRC-01..04 → OWNER_REVIEW. No verses invented. Not published.

**E2E-C** Conversation returned job_id at INTAKE; host runner advanced both jobs.

**Capabilities** fresh Conversation (`hermes-capabilities-out.txt`) reported software submit, research/source pack, no second CLI, A2/A3 blocked, Home pending.

## Economics / access

Positive remaining-cap reservation: unit PASS. Ceiling 0: prior live BLOCKED. Forged `owner_decision`: unit PASS. Denied OratsUtil: prior live BLOCKED. “Do not publish” no longer A2.

## Owner action

None required to keep the platform running. Product RCs wait for your review if you want them accepted; they are not DONE and were not published. Home voice stays a separate physical check.
