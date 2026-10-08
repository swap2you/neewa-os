# NEEWA autonomous personal-project delivery — implementation contract
Date: 2026-10-08
Owner: Personal-project owner
Purpose: Finish the active NEEWA repair and establish one reusable delivery standard for every owner-controlled personal software project.

## Execution instruction for the current Cursor session

Treat this document as a continuation and expansion of the NEEWA repair already running. Keep the current session and its work. Do not start a competing NEEWA or ChakraOps writer. Read the entire document, reconcile current source and installed versions, implement the missing behavior, install the verified changes, and demonstrate normal mission execution. Finish by handing control to Neewa through the existing bridge; the owner must not have to submit a second bootstrap prompt.

Put this contract and the resulting reusable standard in the NEEWA repository. Use the existing project registry, worker, transport, authorization registry, test tools, and reporting channel. Extend those components rather than introducing a new orchestration framework, paid service, separate broker, or another worker.

The owner authorizes ordinary personal software engineering, artifact sharing with the designated reviewers, necessary local tool installation, research, automated UAT, commits, pushes, PRs/merges, local app restarts, and maintenance updates to the existing NEEWA host and Windows worker after their checks pass. This authorization applies to personal project identities, not employer projects or other people's accounts. Implement recognized standing authorization; prompt wording alone must not be represented as an installed policy.

Orders, financial transfers, purchases, paid subscriptions, paid credits/API fallback, paid cloud-resource expansion, and acceptance of an obligation to pay remain prohibited. Existing subscribed tools may be used within their included limits. Read-only financial data access is permitted for the owner's authorized project and integrations.

All source and evidence claims below describe inspected GitHub files or owner-supplied receipts. They do not prove the current Windows/Ubuntu runtime state. Cursor is editing the source concurrently; verify current versions and avoid overwriting its newer fixes.

## 1. Existing locations and failure history

NEEWA working checkout supplied by the owner:
C:\Development\Workspace\NEEWA-OS
Expected remote: swap2you/neewa-os

Canonical ChakraOps checkout:
C:\Users\swap2\NEEWA-Personal\projects\ChakraOps
Expected remote: swap2you/chakraops
Project identity: PRJ-CHAKRAOPS, modify-existing.

Windows worker reported installation:
C:\Users\swap2\AppData\Local\NEEWA\worker
Reported identity: LAPTOP-HKGLJEE8\swap2.
Verify both rather than treating them as hardcoded universal defaults.

Existing coordinator host: ubuntu@neewa-core-01.
Reported active release link: /opt/neewa/neewa-os-current.
Host shared inbox reported:
 /home/ubuntu/.hermes/sandboxes/docker/default/workspace/windows-jobs
Container view reported:
 /workspace/windows-jobs
The exact mount relationship must be verified; the paths are not interchangeable on all executors.

Preserve historical terminal mission decisions:
- MISSION-20261007T204850Z-C2E85D13: FAILED/MAX_REPAIR_CYCLES.
- MISSION-20261008T015300Z-A9B1DD10: BLOCKED/A2_OWNER_GATE.
- MISSION-20261008T133401Z-55B99A8F: subsequently reported FAILED/IDENTICAL_FAILURE_NO_NEW_EVIDENCE.
Do not relabel terminal history as success to make reporting green.

The last failed successor involved:
- JOB-20261008T133443Z-5804508C-AUTO-CC02: worker completion reported.
- Its parent: controller CHILD_TIMEOUT at 2026-10-08T13:47:38Z.
- JOB-20261008T134809Z-2F4638D5-AUTO: continuation without terminal child receipt.
Reconstruct the actual timeline and explain the failed receipt/recovery path.

Bootstrap receipts reported a working temp probe, 12 collected/passed independent ORATS tests, and two loopback HTTP 200 responses. Those prove narrow checks at their timestamps. They do not establish full mission acceptance, trading performance, or current runtime health.

## 2. Source-grounded audit findings

| ID | Inspected component | Evidence and limitation | Required resolution |
|---|---|---|---|
| F01 | 12_SCRIPTS/neewa_orchestrate.py, inspect_folders | Checks inbox, processing, done, failed in that order. A stale claim can mask a completed receipt. Exact cause of the observed timeout still needs logs. | Validate terminal receipts and reconcile them before stale projections. Handle conflicting terminal results explicitly. |
| F02 | 16_WINDOWS_CLIENT/worker/Start-NeewaWindowsWorker.ps1 | Upload failure is logged, then local inbox job is removed. SSH/SCP native failures lack checked acknowledgements. Already-done job handling skips rather than proving receipt delivery. | Durable result outbox, checked native exits, acknowledged atomic remote publication, replay without re-execution. |
| F03 | 16_WINDOWS_CLIENT/worker/Invoke-NeewaCursorCall.ps1 | Redirects stdout/stderr, waits for exit, then ReadToEnd. This is a potential pipe-buffer deadlock on verbose children. | Drain both streams concurrently while the process runs; preserve bounded logs and progress; test with output exceeding pipe capacity on Windows. |
| F04 | 12_SCRIPTS/neewa_autonomy.py, child_is_stale and constructor | Staleness is based on dispatch age; default child timeout remains 600 seconds. Worker accepts timeout=0, but that does not make the parent unlimited. | Align deadlines across layers; separate elapsed budget, polling expiry, inactivity, liveness, and substantive progress. |
| F05 | Worker status/progress publishers | Worker top-level heartbeat is published before blocking invocation and active_job_id is empty. Child progress emits ISO timestamps with fractional precision. | Publish independent heartbeat while busy; identify actual job/PID; parse all emitted timestamp formats consistently. |
| F06 | 12_SCRIPTS/neewa_autonomy.py, parse_utc | Uses only %Y-%m-%dT%H:%M:%SZ. Worker emits .ToString('o'). | Normalize aware ISO8601 timestamps, fractional seconds and offsets; reject future/skewed evidence as unknown. |
| F07 | 12_SCRIPTS/neewa_autonomy.py, run_council | Council explicitly deterministic_only/INDEPENDENCE_UNAVAILABLE; some fields still say PASS or approved_design. | Separate lint/checklist from actual independent consultation. Actual reviewer receipts must drive the design/acceptance gate. |
| F08 | 12_SCRIPTS/neewa_mission.py, consult_advisors | invoke=False by default; missing callback produces UNAVAILABLE. Configuration alone does not dispatch reviewers. | Wire real authorized invocation into the installed supervisor and prove it executes without owner prompting. |
| F09 | 12_SCRIPTS/neewa_autonomy.py, build_validation_prompt and validation dispatch | Generic independent validation asks a read-only model to run tests. New deterministic independent_test action exists, but generic path must be checked. | Dispatch deterministic independent tests with writable scratch, then provide actual receipts to read-only reviewers. |
| F10 | Worker artifact transport | Worker copies only result.artifact, despite controller handling artifact_paths. Reports describe reviewer-inaccessible UI/test evidence. | Publish complete declared evidence bundles with manifests, hashes, locations, and per-reviewer read probes. |
| F11 | 11_CONFIG/budgets.json; budget_decision | Cursor calls receive a conservative $0.50 estimate; unknown cost/ceilings can stop work. Codex is recorded as $0.00 cash. These do not measure actual subscription capacity. | Separate incremental cash cost, subscription quota, model effort and concurrency. Pause on real capacity, not fabricated dollar spend. |
| F12 | allowlist.json; cursor-call-policy.json; action classifier | Several ordinary Git operations are A2; shared policy contains generic blocked words and old workspace assumptions. Broad objectives have stopped local work. | Recognized personal-project standing authorization and action/target classification. Retain money prohibitions. |
| F13 | chatgpt_review_routes.json and review launcher | SSO routes and successful model probes now exist; fallback uses recorded availability. Probe age, missing entries, quota failure, and invocation evidence require verification. | Validate live account/identity route and actual model output; refresh on failure; no paid fallback. |
| F14 | Planning/project identity helpers | Generic project names and synthetic expected paths can be generated. Some research synthesis draws only from a small local corpus. | Real repository adapters, typed project registry, live research capability, requirement-derived artifacts; no generic file-presence substitute. |
| F15 | Release/controller/worker version evidence | Source, local copies and loaded release have repeatedly diverged. | Record resolved runtime path, commit, script hashes, account and capability manifest for every acceptance receipt. |

Source links:
- https://github.com/swap2you/neewa-os/blob/main/12_SCRIPTS/neewa_orchestrate.py
- https://github.com/swap2you/neewa-os/blob/main/12_SCRIPTS/neewa_autonomy.py
- https://github.com/swap2you/neewa-os/blob/main/12_SCRIPTS/neewa_mission.py
- https://github.com/swap2you/neewa-os/blob/main/12_SCRIPTS/neewa_action_semantics.py
- https://github.com/swap2you/neewa-os/blob/main/16_WINDOWS_CLIENT/worker/Start-NeewaWindowsWorker.ps1
- https://github.com/swap2you/neewa-os/blob/main/16_WINDOWS_CLIENT/worker/Invoke-NeewaCursorCall.ps1
- https://github.com/swap2you/neewa-os/blob/main/16_WINDOWS_CLIENT/worker/Invoke-NeewaCodexReview.ps1
- https://github.com/swap2you/neewa-os/blob/main/16_WINDOWS_CLIENT/worker/allowlist.json
- https://github.com/swap2you/neewa-os/blob/main/16_WINDOWS_CLIENT/worker/chatgpt_review_routes.json
- https://github.com/swap2you/neewa-os/blob/main/11_CONFIG/budgets.json

Inspected file blobs, for comparison rather than checkout/runtime identity:
neewa_autonomy.py: 630080462a797aeb536877cbdf417c4adad731ef
neewa_mission.py: b989b2093ed0aeb94b56455ae85cd3d7d098f2f7
neewa_orchestrate.py: c9e2eefe53fba21a2f09099460ccf83fcf7b2307
Start-NeewaWindowsWorker.ps1: 05a4caf2aac57b2915d53ded5c86088d9e77b18a
Invoke-NeewaCursorCall.ps1: 2e8e89ba6b115049495ec264ac9b0620080e61f5

Both swap2you/neewa-os and swap2you/chakraops were confirmed public through repository metadata. Publishing all untracked files is not necessary. Commit shareable source/docs/tests/sanitized evidence; retain credentials, raw account information, licensed market data, large dumps and session tokens in an authenticated evidence store.

## 3. One standard for all personal repositories

Implement a reusable standard at AI-OPS/delivery/PERSONAL_AUTONOMY_STANDARD.md and wire it into actual intake/dispatch. Do not just create a document nobody reads.

Use a small typed project record in the existing registry, including:
project_id; ownership=personal; lifecycle=create-new/modify-existing;
canonical_path; remote; default_branch; runtime targets; test/build/health commands;
evidence locations; requirement document; authorized operation scope;
read-only integrations; money-side-effect prohibition; reporting destination.

Onboard new personal projects under approved personal roots automatically with preflight. The root folder itself is not an implementation workspace. Resolve canonical project identity and repository remote before running commands. An existing repo remains modify-existing even if its name contains trading or deployment words. Ownership and actual operation matter more than an application-name substring.

Use the same mission lifecycle and evidence protocol across repos, with stack-specific adapters for test/build/restart. Avoid ChakraOps-only conditions as the general repair.

Reuse the registered canonical checkout. Separate personal project access from employer access and external account authorization. Do not broaden access to the entire machine just to pass an artifact check.

Do not migrate or delete the NEEWA checkout during this repair. The owner asked to retire duplicate ChakraOps trees, not to relocate unrelated sources. Report duplicates and reconcile them only where ownership and requested scope are clear.

## 4. Installed authority: broad personal engineering, money blocked

Map the owner's already stated permission to the existing supported registry. Authorization must be consumable by the installed worker and coordinator and covered by tests.

Automatically authorized for registered personal projects:
- requirements, design, research, repository inspection and implementation;
- local files, scratch, test artifacts, fixture/test accounts for the owner's app;
- necessary tools/dependencies using free or already subscribed access;
- automatic independent testing, reviews, UAT and corrections;
- Git branches, commits, pushes, PR updates, technical approvals and integration;
- personal app deployment/restarts and maintenance of the existing worker/coordinator;
- existing owner-directed notification channels and delivery artifacts;
- free third-party evaluation accounts when allowed by the provider and no payment obligation is accepted.

Commit/runtime identity, green checks and rollback are engineering prerequisites that the agents must satisfy automatically. They must not become repeated requests for owner confirmation. Reviewers may give technical approval within the owner's standing scope.

Always prohibited without separate owner instruction: orders/order modifications, execution, cancellation/rolling, transfers, purchases, paid credits/subscriptions, a free trial that commits to billing, paid resource expansion, credential/public financial-data exposure. Read-only brokerage access is allowed; broker write routes are denied and tested at the actual execution boundary.

The same authorization applies only to existing or onboarded owner-controlled targets. If a target belongs to someone else, or login/MFA requires a human, state the exact required input once. Do not invent access, bypass provider controls, or treat an AI reviewer as the identity owner.

No --yolo or public arbitrary-command listener is required. The implementer needs ordinary engineering access to the canonical project and scratch; the testing worker needs write access to scratch; reviewers need read access to source and evidence. Fix the actual missing capability.

## 5. Reliable job transport, process handling and scheduling

Implement only missing pieces using existing components.

A. Claim and execute
- Atomic claim with project writer lease, executor identity, attempt and generation.
- Lease prevents two agents editing the same canonical tree.
- A PID or heartbeat alone is not proof of substantive progress.
- Record receipt_id, job_id, mission_id, execution generation, state, runtime identity and candidate identity.

B. Child process
- Concurrent stdout/stderr draining; logs available during execution.
- Separate executor heartbeat and substantive progress timestamps.
- Preserve checkpoints and actual command exit status.
- No silent failure masking or wholesale arbitrary failure_class=AUTH.
- Use monotonic clocks for local elapsed calculations; normalize cross-host ISO times.

C. Finish and publish
- Save final local receipt atomically before network delivery.
- Persist a durable outbox entry and artifact manifest.
- Publish artifacts and receipt atomically/with acknowledgements.
- Retain until verified remote acceptance. Retry publication without rerunning completed code.
- After restart, completed local work is republished rather than dropped.
- Check SSH/SCP exits and errors. A command finishing is not evidence that transfer succeeded.

D. Harvest and recover
- Valid terminal receipts take precedence over stale claims/projections.
- Conflicting generations/receipts are reported and reconciled, not arbitrarily overwritten.
- Poll timeout means observation expiry, not automatic child failure.
- Parent absolute deadline, child execution budget, inactivity limit, delivery timeout and quota wait are distinct.
- Heartbeat without progress can still be stalled; progressing work must not fail only because it crossed 600 seconds.
- A true dead child is terminalized with evidence; kill/lease confirmation precedes replacement.
- Completed implementation advances to validation even if its delivery was delayed.
- Late evidence on a historically failed parent is appended as reconciliation evidence; history is preserved and a necessary successor is linked.
- Terminal mission recovery requires a changed condition, one recovery reservation and one successor. No infinite clone chain.

E. Continue the charter
- Stage completion cannot strand remaining requirements at OWNER_REVIEW.
- A supervisor dispatches the next authorized stage automatically after its checks pass.
- Stage plan/acceptance matrix distinguishes completed, in progress, blocked, waiting, and not started.
- Quota waits and connectivity outages persist next_check_at and resume through the installed scheduler.
- Notifications/status must state whether real work is executing, waiting, or stopped.

## 6. Common evidence store and access negotiation

Use the current shared inbox/evidence transport first. Do not open public Windows folders, add Drive, or buy a storage service unless the existing bridge actually cannot satisfy the need.

Standard layout under the verified shared root:
evidence/<project_id>/<mission_id>/<stage_id>/<candidate_id>/
  manifest.json
  requirements.json
  candidate.json
  tests/
  ui/
  reviews/
  traceability/
  release/

Use actual safe identifiers rather than inserting untrusted path components.

Manifest minimum:
schema_version; project/mission/stage/candidate IDs; producer;
source commit and dirty-diff hash where applicable;
created_at/as_of; artifact relative path; media type; size; SHA-256;
classification=public-sanitized/private/licensed;
allowed reviewer contexts; canonical host location; executor-local read location;
availability; redaction notes; linked requirement IDs.

Publish every required artifact, not just result.artifact. For dirty candidates, preserve an inspectable sanitized patch/candidate bundle and its hash. Reconcile untracked duplicates, output files and actual test sources deliberately.

Before starting a substantive review:
1. Resolve each review executor's actual access route.
2. Materialize the same immutable candidate/evidence bundle into its approved read scope.
3. Have that executor list/read required files, verify hashes, open the actual screenshot/image, and report its access probe.
4. If access fails, use an existing alternative: shared inbox materialization, authenticated GitHub access, or current worker copy operation.
5. Continue access negotiation between coordinator and reviewer until readable, or record a precise capability failure.
6. Do not spend model review calls on a brief that merely promises inaccessible artifacts exist.

Do not label a screenshot inspected because a path was returned. An image must be opened. A pytest summary must link to the actual collected-test transcript and exit receipt. Licensed provider data and raw account details must not be pushed to public GitHub.

Shareable source/docs/tests/sanitized evidence go to GitHub through the authorized normal workflow. Large/private/licensed artifacts stay in authenticated existing storage, with safe manifest references. GitHub is a useful second read route; it is not a substitute for private artifact access.

## 7. Actual consultation, model routing, tests and UAT

Wire consultation into the installed supervisor; prove the default mission path invokes it. Deterministic lint is separate from model consultation. A configured advisory list is not a council meeting.

Required independent review roles:
- domain/strategy and downside;
- software/data reliability;
- UI/product requirements and automated UAT.

Use separate contexts and actual reviewer IDs. They may inspect the same candidate but cannot certify their own implementation. They may propose alternatives and exchange structured objections/evidence through the coordinator; no competing writer.

Each receipt records actual model/effort/auth route; candidate/manifest hashes;
required artifacts successfully read; findings tied to requirements;
commands actually run or links to deterministic receipts;
decision=APPROVE/CHANGES_REQUIRED/INSUFFICIENT_EVIDENCE;
blocking objections, remediation and scope limitations.
Successful CLI exit means the call completed, not that the reviewer approved.

Run deterministic tests outside the read-only model sandbox, using scoped writable scratch. Reviewers assess those receipts and request additional necessary tests. Never accept TEST_JSON text, zero tests, a model assertion, a heartbeat, or existence of RELEASE_CANDIDATE.md alone as acceptance.

SSO routes already inspected:
triage: gpt-5.6-luna medium;
software/UI: gpt-5.6-sol high with available Astra fallback;
strategy/acceptance: gpt-6-astra high.
gpt-6-sol was reported unavailable on this ChatGPT account.
Verify current account availability and refresh failures; do not keep retrying an unavailable model. All OpenAI review calls must use actual ChatGPT sign-in, with API-key fallback disabled. No raw credential copying between products.

Separate subscription quota from incremental cash. Codex $0 cash is not zero resource use. Cursor estimated dollars are not verified extra billing. Retain usage estimates as telemetry, use actual quota outcomes and concurrency, and resume after reset without purchasing credits. Independent reviews can be sequenced to manage limits.

UAT is requirement-based behavior testing, including realistic success/failure states, responsive layouts, accessibility where relevant, and UI/backend result parity. Use current local browser/test tooling for localhost and deterministic HTTP for health. A failed paid cloud browser is not a reason to abandon local testing.

User review is a final product evaluation when desired, not a gate that silently stops every routine stage.

## 8. Research and external application comparison

Implement source-grounded research as real retrieval and inspection, not a generated "research report" made only from OWNER.md and local configuration excerpts.

For each project:
- Understand the existing implementation and original requirements first.
- Identify relevant currently working products and primary domain references.
- Inspect public product pages/docs and, where permitted, available free demos or owner-authorized test accounts.
- Record source URL, retrieval time, access route, observed behavior and limitations.
- Distinguish observed UI flows from inferred behavior and marketing claims.
- Compare feature/flow/data contracts against the owner's requirements.
- Propose justified changes with measurable acceptance tests and consultation.
- Do not buy subscriptions or start chargeable trials. If a paid wall prevents evaluation, use public docs/demo or mark the observation unavailable.

Use provider terms and available access. Do not bypass account/MFA/captcha controls or claim a premium application's behavior was tested when only marketing text was read.

Avoid adding unnecessary services. Reuse the current owner channel before creating Slack/Telegram/Discord infrastructure. Report project stage, real delivered work, test/review results, blockers and next action. Notification delivery should have a receipt and should not itself block implementation.

## 9. ChakraOps delivery requirements preserved

After NEEWA acceptance, resume ChakraOps with exactly one mission path.

Initial stage:
- Reconcile the existing modified ORATS/charter files, root loader/duplicate test and stdout/stderr artifacts.
- Bind the independent 12-test receipt to the actual candidate diff.
- Validate malformed/future/timezone-less/stale/unavailable/valid timestamps and provider failures.
- Demonstrate that unknown/stale/failing data cannot silently produce a qualified live ticket.
- Commit and integrate the verified change through the normal workflow; identify the running app version.

Next stages must cover the original charter:
- Actual no-signal evidence: stage-by-stage evaluation counts, data availability, filters, rejection reasons, universe and configured windows.
- English strategy explanation and flowchart tied to implemented code.
- CSP/CC/spread/shares calculations: units, multiplier, cash collateral, covered shares, spread width, fees, expiry P/L, assignment and downside.
- Trading calendar, holidays, business days, expiry conventions, earnings and news availability.
- Conservative/aggressive profiles: explicit tested risk changes; no forced trades.
- Read-only Robinhood positions, buying power, cash/margin and refresh timestamps; unknown account fields remain unknown.
- CC and CSP eligibility based on actual holdings and funds; shares entry/exit/size/P&L behavior.
- UI/live-evaluation parity, failure states, usable explanations and responsive/accessibility testing.
- Universe expansion and indicators only with data quality and defensible validation; inherited thresholds are configuration, not demonstrated edge.
- Historical/replay tests and market snapshots, named with as_of, source, timezone and capture metadata; replay never called live.
- Evidence-based competitor comparison and research; walk-forward/out-of-sample evaluation when claiming performance, accounting for costs and bias.
- Owner alerts: exact strategy and action, ticker, strike/expiry, premium/as-of, size assumptions, exits, risks and reason; CSP/CC sell actions must not be mislabeled as buys.
- Position monitoring/exit/roll recommendations with rationale, while actual broker order actions remain blocked.
- Final traceability: requirement -> design -> implementation -> deterministic test -> UI evidence -> independent review -> deployed candidate.

A rising market does not imply that safe trades must qualify. Diagnose missing signals without manufacturing eligibility or promising a profitable/foolproof strategy.

## 10. Acceptance scenarios through the normal installed path

Cursor must implement missing behavior and prove these cases with behavioral tests and actual bridge canaries. Use a disposable personal fixture repository for fault injection, not the owner's trading data. Inject faults through test hooks or controlled restart/network simulation; do not damage production accounts.

| Case | Required observation |
|---|---|
| A01: Personal project onboarding | New personal repo resolves canonical identity and uses the common standard without bespoke ChakraOps code. |
| A02: Permission semantics | Local implementation/restart, Git integration and authorized existing-target maintenance proceed. A forbidden money/order action remains denied. |
| A03: Busy worker | Fresh worker and child status continues while the implementation runs; job identity matches actual PID/process claim. |
| A04: Large stdout/stderr | Verbose child exceeds pipe capacity and still completes; both streams preserved; no deadlock. |
| A05: Stale claim plus final receipt | Valid completion is harvested before stale inbox/processing projection; no false timeout or second writer. |
| A06: Result upload outage | Completed child remains in durable outbox; transfer retry publishes receipt/artifacts; implementation execution count stays one. |
| A07: Worker restart before acknowledgement | Same completed result republishes; no lost receipt or duplicate execution. |
| A08: Long legitimate child | Progressing child crosses the old deadline without false failure; configured inactivity/deadline behavior is explicit. |
| A09: Genuine stalled/dead child | Watchdog captures evidence, stops/releases ownership appropriately and schedules bounded recovery without overlapping writers. |
| A10: Controller restart/late receipt | Completed evidence consumed once, stage advances once; historical failures remain documented. |
| A11: Independent tests | Normal mission dispatch uses independent_test with writable scratch, collects real tests, captures nonzero failure and rejects zero collection. |
| A12: Reviewer access | Each reviewer verifies candidate hashes and reads test transcript and an actual UI image from its own executor before deciding. |
| A13: Real consultation | Default installed mission invokes three independent review contexts; checklist-only approval is rejected. |
| A14: Objection loop | Reviewer raises a seeded defect; implementer repairs; deterministic test catches it; reviewer verifies the changed candidate. |
| A15: Subscription/model failure | Unsupported model or quota response yields available SSO route or durable wait/resume; no paid fallback, purchase or reset transaction. |
| A16: Full lifecycle | Requirements -> design consultation -> implementation -> independent tests -> UI UAT -> review -> authorized integration/restart -> health -> next stage occurs without owner copy/paste. |
| A17: Second repository | Repeat the ordinary full lifecycle in a second disposable personal repo without project-specific policy edits. |
| A18: ChakraOps continuation | Exactly one linked ChakraOps successor is claimed and advances beyond ORATS reconciliation into the next substantive charter stage. |

Acceptance is not satisfied by mocked terminal states alone. Unit/regression tests may use fakes for transport boundaries, but the installed bridge must have normal-path proof. No "run direct pytest, then manually mark mission complete."

## 11. Implementation order, integration and installation

1. Adopt the active Cursor repair; capture baseline state, installed target identity and relevant logs.
2. Repair process output, receipt transport/harvest and liveness/deadline handling.
3. Repair generic independent-test dispatch and full evidence publication/access negotiation.
4. Install recognized standing authorization, actual consultation invocation, and quota-aware routing.
5. Wire common project standard, progress/status and stage continuation.
6. Run relevant regression/integration suites; resolve failures; obtain actual independent review.
7. Commit scoped source/docs/tests/sanitized evidence; push, complete normal integration and CI.
8. Install verified worker/coordinator revisions using the existing procedure and rollback.
9. Run installed-path acceptance canaries including the second repository.
10. Publish acceptance evidence; dispatch/adopt one ChakraOps successor and verify real next-stage progress.

Rebase/reconcile active work; do not overwrite other changes, bulk-commit secrets/output dumps, force-push or make a second repair writer. Current two repositories are public; verify other projects' visibility individually before publication.

Do not install a startup "fail closed" change that makes the worker unusable before its repair/bootstrap action can execute. Provide a fallback bootstrap mechanism and rollback.

Do not remove bounded recovery or test gates to silence failures. Implement autonomous steps that satisfy them. A reviewer decision cannot create unavailable tools or override the money prohibition.

## 12. Delivery artifacts and completion receipt

Commit:
- this implementation contract;
- AI-OPS/delivery/PERSONAL_AUTONOMY_STANDARD.md;
- supported project/onboarding schema and scoped standing authorization documentation;
- relevant source/config changes;
- behavioral regressions and sanitized acceptance summary;
- one simple status/run/recovery entry point using the installed interfaces.

Publish privately through the existing shared evidence bridge:
- exact failed-job timeline and causal findings;
- deterministic command/test/build receipts;
- full artifact manifests and per-reviewer read probes;
- reviewer decisions and objections/remediation;
- source/local/GitHub/worker/coordinator version/hash comparisons;
- installation/rollback/post-restart verification;
- fault-injection canary receipts and normal full-lifecycle receipts.

Use shared records/autonomy-acceptance-latest.json plus the existing
records/chakraops-bootstrap-latest.json. Include:
schema_version; generated_at; active project/mission/job/stage;
source and loaded runtime identity; capability manifest;
implemented/tested/reviewed/installed states separately;
acceptance cases and linked evidence; open objections;
cash-side-effect policy; quota wait/resume; no_duplicate_writer proof;
latest substantive progress and owner-facing status location.

The final Cursor report must be short and concrete:
what was repaired; exact tests and canaries; Git and installed versions;
reviewer decisions; active ChakraOps successor and next-stage progress;
any genuine unresolved capability.

Cursor must publish the handoff into Neewa's readable inbox and trigger the
existing supervisor to adopt it. The owner should not have to relay artifacts
or supply another prompt. The installed Neewa then continues the remaining
charter and uses the existing owner reporting channel.

Do not claim "done" or "working autonomously" unless the normal installed path
completes consultation, independent testing, evidence sharing, integration and
stage continuation. If actual human identity/MFA, prohibited money or an
unavailable host route prevents that, identify that exact boundary and finish
all unaffected work. Never fabricate an approval, process, test or receipt.

## 13. Short prompt to attach this file to the running Cursor session

Continue your existing NEEWA repair using this attached implementation contract.
Do not start another writer. Incorporate the source audit, implement the common
personal-project standard, and prove the full normal installed lifecycle in
ChakraOps and a second disposable personal repo. Commit/sync/install verified
changes, publish reviewer-readable evidence and acceptance receipts, and hand
off directly to Neewa so it resumes the charter without another owner prompt.
The standing engineering authorization is in the document; purchases and all
financial/order side effects remain blocked.

