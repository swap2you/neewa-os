# NEEWA validation follow-up — 2026-10-08

## Verified conclusion

The NEEWA repair is committed and pushed, and GitHub CI is green. Autonomous delivery is still only partially demonstrated.

Inspected immutable NEEWA candidate: `b0915eabebaf2985109e1ec4e48634d5ce063347`.
GitHub NEEWA `main` matched that candidate during this check.
GitHub ChakraOps `main` remained `bb9731ea99c68a8147a91e1873f943ce7edc8acc`; the reported dirty ORATS repair is therefore not established on ChakraOps main.

Verified GitHub run: https://github.com/swap2you/neewa-os/actions/runs/37802117585
- Push-triggered NEEWA validation: success.
- Deployment functional suite: ran 36 tests, OK.
- Full Python suite: ran 375 tests, OK (skipped=29). This means 346 tests passed and 29 skipped, not 375 passed plus 29 skipped.
- CI ran on Ubuntu. It does not prove the installed Windows worker behavior.
- The run exposes no downloadable workflow artifacts.

The report says worker PID 24620 and child PID 57608 were preserved. The new stream drain was installed on disk but had not been loaded by that running worker. Current Windows processes, shared receipts, loaded code and app health cannot be independently read from this ChatGPT environment. Their reported status is evidence supplied by the owner, not a new live verification.

Assumptions: the current Cursor session still owns the NEEWA repair; the existing ChakraOps child may still be active; the previous personal-project engineering authorization remains in force. Verify these before mutation.

## Source-level defects reproduced or identified

### 1. Automatic independent-test arguments are disconnected

`_submit_independent_test` sends `test_command` but no `args`.
`Invoke-NeewaIndependentTest.ps1` parses that command into local `$args`, then validates the original `$ArgumentList` instead. The normal generated job can consequently fail with UNAPPROVED_TEST_COMMAND even though a manually submitted test with explicit args passed.

The helper also rejects the ordinary bare `-m unittest` form through its minimum-token check, and its outcome parser recognizes pytest summaries rather than unittest's normal “Ran N tests / OK” output. Its interpreter/CWD defaults assume ChakraOps's backend. The disposable second repository must exercise its own registered adapter.

### 2. A passing independent-test artifact is not harvested

The worker wrapper publishes a small receipt referencing `<job>-independent-test.json`. The actual counts, transcript and candidate identity are in that artifact.

The controller's `_merge_sidecar` reads only `<job>-cursor-call.json`. `harvest` therefore receives neither `independent_test`, `test_results`, nor the independent stdout.

A source-level reproduction used unchanged Python functions extracted from b0915ea and synthetic files matching the committed worker's actual JSON shapes:
- Artifact: 12 collected, passed=true, exit=0.
- Harvested worker state: COMPLETED.
- Controller test evidence: passed=false, source=absent.
- Independent receipt exposed to controller: false.

This is a controller/data-contract reproduction, not a live Windows test.

### 3. Reviewer objections do not control acceptance

The read-only launcher returns COMPLETED for a successful Codex process. The parent records `review_completed`, but does not parse and enforce the reviewer's decision. `evaluate_autonomy_done` checks council PASS without requiring actual independent approval.

Two unchanged-function probes confirmed:
- A VALIDATING job with otherwise passing fields and review_decision=OBJECT produces an empty done-gate failure list.
- The same job in OWNER_REVIEW with independent_rerun=PASS is considered mission-successful despite OBJECT.

The COUNCIL path still assigns `validation.council=PASS` from the deterministic checklist. Changing its displayed role to CHECKLIST_ONLY did not wire an actual consultation gate.

### 4. Queued consultation is counted as completed consultation

`_installed_consult_invoke` creates a reviewer job but supplies neither the canonical repo nor a typed review_task. It returns a response object containing decision=null.

`consult_advisors` counts that dispatch object as a consultation. A probe returned consulted_count=1 with zero completed reviewer responses. The normal design path still uses the checklist; consultation invocation currently appears in failure recovery.

The Codex launcher selects its model from `review_task` and otherwise defaults to software_review. Passing only implementation_model does not establish strategy/UI routing.

### 5. Artifact delivery remains incomplete

The worker outbox records and transfers only `result.artifact`. Full `artifact_paths`, transcripts, screenshots and candidate diffs are not transported as one verified evidence bundle.

The terminal JSON is uploaded before its referenced artifact. A controller can observe completion before the evidence is available. A `test -s` acknowledgement proves a nonempty file, not the expected bytes or hash.

### 6. Installed stream handling still needs a real Windows canary

The Cursor launcher now uses asynchronous output events, which is an actual source change. Its callback/runspace behavior, final EOF drainage and memory limits require testing under the installed Windows PowerShell version.

Other process runners retain unsafe output handling: independent tests read stdout then stderr sequentially before applying the wait timeout; the bounded SSH/SCP helper redirects both streams without draining them. These paths can still hang on sufficient output.

### 7. The stage plan covers only a small portion of the charter

The default ChakraOps plan currently contains ORATS reconciliation and no-signal evidence. Passing those two stages cannot establish holdings reconciliation, strategy correctness, UI parity, research, profile behavior, replay snapshots, alerts or full charter acceptance.

## Detailed instruction for the EXISTING Cursor session

Continue the current NEEWA repair in:
`C:\Development\Workspace\NEEWA-OS`

Use the canonical ChakraOps checkout:
`C:\Users\swap2\NEEWA-Personal\projects\ChakraOps`

This is a targeted follow-up to the committed implementation contract already in AI-OPS/delivery. Read that contract and this audit. Preserve newer fixes. Do not replace the framework, create a competing writer, reset terminal mission history, or claim approval from a checklist.

1. Reconcile the current mission, child, process identities, processing claim, progress and immutable receipts. Adopt the existing live child. Allow it to finish and harvest it before restarting its worker. If it has stopped, establish that from actual process/claim/receipt evidence before a changed-condition recovery.

2. Fix the independent-test contract end-to-end. Use a validated structured argv/CWD/interpreter from the registered project adapter; preserve a safe command compatibility path if needed. Validate the parsed arguments actually used. Support the declared pytest/unittest and frontend/build commands required by the two repos, with genuine collected/executed counts. Reject zero tests, precollection failures and failed commands. Return one typed independent receipt containing the full transcript location, exit, counts, candidate identity and hashes. Consume that receipt through the actual worker-wrapper/outbox/controller path.

3. Fix real consultation and acceptance. Dispatch actual design and postimplementation reviewers with project/mission/stage identity, canonical repo, typed task, candidate manifest and evidence locations. Persist consultation dispatches; harvest their actual responses. DISPATCHED is not CONSULTED. Parse a structured APPROVE/CHANGES_REQUIRED/INSUFFICIENT_EVIDENCE decision and preserve OBJECT/HOLD as unresolved objections. Missing, inaccessible, malformed or candidate-mismatched review evidence must trigger repair or evidence collection, not silent approval. Make the done gate and mission stage advancement enforce the required decisions.

4. Use verified ChatGPT sign-in routes: Sol high for software and UI; Astra high for strategy/downside and final acceptance; Luna for routine triage. The launcher must receive the actual task and record requested/actual model, effort and auth. No API-key or paid-credit fallback. Handle unavailable models/quota without pretending a review occurred.

5. Publish every required artifact through one manifest: receipt, full transcript, candidate patch including relevant staged/untracked content, UI screenshots and review responses. Map Windows paths to coordinator/reviewer paths. Confirm each reviewer can read the expected bytes and inspect the images. Hash-check transfers. Publish terminal completion only after its referenced evidence is durably available, with acknowledged replay/idempotency.

6. Use a reliable concurrent stdout/stderr drain in all relevant Windows runners, with working callback execution, EOF flush, streaming/bounded retention and real deadlines. After the current child completes, restart exactly one worker and prove the loaded revision/path/account/hashes. Run a Windows child that emits more than pipe capacity on both streams and a hanging child to prove drainage and timeout behavior. Do not rely on Ubuntu CI to certify this.

7. Add behavioral regressions for the exact generated test job with no manual args; its real receipt/artifact round trip; pytest and unittest success/failure/zero collection; reviewer OBJECT despite exit 0; missing review; dispatched-only consultation; typed model routing; inaccessible/hash-mismatched evidence; upload interruption/replay; verbose children; safe worker restart; and second-repo adapter execution. Run required CI and installed-path acceptance. Test fakes may isolate defects, but the final normal lifecycle must use the real bridge.

8. Finish the queued disposable repository through implementation, independent tests, accessible evidence and actual reviews. Demonstrate normal same-mission stage continuation without manual state edits or a new owner prompt. Keep its writer isolated from ChakraOps.

9. Reconcile ChakraOps's dirty files without bulk-committing outputs or deleting useful work. Commit/push scoped verified changes through its normal workflow, establish origin/main agreement and exact runtime candidate identity, and keep generated/private/licensed/account evidence in the shared bridge. Continue from ORATS into real no-signal evidence. Extend the stage plan from the full existing charter so it does not stop after the two initial tasks. Do not loosen trading filters merely to manufacture qualified signals.

10. Publish updated `records/autonomy-acceptance-latest.json` and `records/chakraops-bootstrap-latest.json` only with actual timestamps, candidate identities, loaded worker/coordinator versions, tests/counts, artifact-access probes, reviewer decisions, open items and current next-stage progress. Commit/push verified NEEWA changes, complete CI, install through the existing process, and preserve rollback.

The owner has already authorized personal engineering work, integration, existing-host maintenance, local restarts and reviewer evidence sharing. Use the recognized standing authorization for those operations. Broker submission/cancellation/rolling/execution, purchases, financial transfers and paid-credit fallback remain denied.

Finish by delivering the following handoff directly into NEEWA's existing readable bridge and triggering adoption. Do not make the owner relay it. Report whether the system is implemented, tested, reviewed, installed and genuinely progressing separately. If something remains unresolved, name the exact failed acceptance case and the evidence-based repair in progress.

## NEEWA handoff — Cursor must deliver this automatically

Adopt the current ChakraOps mission after the coordinator/worker repair is verified. Read the updated acceptance and bootstrap receipts, the full delivery charter and candidate evidence manifest. Reconcile active writers and preserve historical failures.

Continue the full charter using the same mission's stage plan. Obtain real design and acceptance consultation with reviewer-readable evidence and enforce the actual decisions. Independently execute the registered tests and UI journeys. Repair engineering/evidence failures through changed-condition recovery without asking the owner to relay files or prompts. Report substantive completed work, current stage, next step and genuine unresolved capability through the existing reporting channel. Broker orders and purchases remain disabled.

Do not call the charter accepted based on worker liveness, HTTP 200, the 12 freshness tests, a dispatch receipt, model exit 0, or completion of only the first two stages.

## Immutable source references

https://github.com/swap2you/neewa-os/blob/b0915eabebaf2985109e1ec4e48634d5ce063347/12_SCRIPTS/neewa_autonomy.py
https://github.com/swap2you/neewa-os/blob/b0915eabebaf2985109e1ec4e48634d5ce063347/12_SCRIPTS/neewa_mission.py
https://github.com/swap2you/neewa-os/blob/b0915eabebaf2985109e1ec4e48634d5ce063347/12_SCRIPTS/neewa_orchestrate.py
https://github.com/swap2you/neewa-os/blob/b0915eabebaf2985109e1ec4e48634d5ce063347/16_WINDOWS_CLIENT/worker/Invoke-NeewaIndependentTest.ps1
https://github.com/swap2you/neewa-os/blob/b0915eabebaf2985109e1ec4e48634d5ce063347/16_WINDOWS_CLIENT/worker/Invoke-NeewaCodexReview.ps1
https://github.com/swap2you/neewa-os/blob/b0915eabebaf2985109e1ec4e48634d5ce063347/16_WINDOWS_CLIENT/worker/Start-NeewaWindowsWorker.ps1
https://github.com/swap2you/neewa-os/blob/b0915eabebaf2985109e1ec4e48634d5ce063347/16_WINDOWS_CLIENT/worker/Invoke-NeewaCursorCall.ps1

