# Personal autonomy standard

Every owner-controlled personal software project uses this lifecycle. ChakraOps is one project record, not a separate orchestrator.

## Project record

A registered project has: `project_id`, `ownership=personal`, `lifecycle` (`create_new` or `modify_existing`), `canonical_path`, `remote`, `default_branch`, runtime targets, test/build/health commands, evidence location, requirement source, authorized operations, read-only integrations, and a money-side-effect prohibition.

The personal root folder is not an implementation workspace. Preflight resolves the canonical checkout and remote before any command. An existing repository stays `modify_existing` even when its name contains trading or deployment words. Employer trees and other people's accounts are out of scope.

## Lifecycle

Requirements, design checklist, implementation, deterministic independent test, read-only review, then the next planned stage on the same mission. A checklist result is not a consultation. A reviewer exit code is not approval. A worker completion receipt is not charter approval.

Broker orders, transfers, purchases, paid credits, and new payment obligations stay denied. Read-only brokerage access is allowed. Git integration, local tests, and local app restart are ordinary engineering on registered personal projects.

## Evidence

Publish receipts and artifact manifests through the shared Windows-job inbox. Reviewers must read the same candidate hashes, the test transcript, and any UI image before deciding. Licensed data and raw account details stay out of public GitHub.

## Continuation

`auto_continue` missions move from owner review to the next `not_started` stage without a new mission and without a second writer. Historical terminal missions that lack `auto_continue` stay terminal.

Review objections and missing review evidence enter bounded repair, not automatic acceptance or an immediate nonrecoverable stop. Repairs address the current stage and carry the actual reviewer findings and artifact references to the implementation worker and follow-up reviewer. Findings travel as evidence separate from the authorized objective; they do not grant additional permissions.

Each stage has its own implementation and infrastructure retry bounds. Only an accepted stage transition resets those counters; its repair summary and the mission's cumulative retry count, failure history, authorization, and budget accounting remain preserved. Repeating failures and exhausted stage bounds still stop. Independent tests and an explicit approving review remain required before advancement.

## Candidate and review contract

Worker receipts hash the exact raw bytes of Git `diff HEAD --binary --no-ext-diff --no-textconv` output, including staged and unstaged changes and non-UTF-8 content. A separate worktree fingerprint binds status and nonignored untracked-file contents. Tests that change that candidate fail as `CANDIDATE_CHANGED`. A schema-2 receipt carries both identities; review verifies the candidate before and after consultation.

Full test transcripts live in the candidate workspace under `.neewa/evidence/<job_id>/`, with a SHA-256 digest and a shared-inbox copy. That generated directory is excluded through local Git metadata; it must not be committed or published. The reviewer checks the digest and workspace access before and after a model call. Product source is committed by the implementation worker; controller release and traceability documents remain generated evidence, not a required product-root file.

Machine traceability is checked before consultation. Failed rows retain their requirement ID, check, result, and observed evidence in the failure receipt and repair context. No root test-loader, checklist, or model approval may substitute for satisfying those rows. Native Windows CI must exercise stream draining, raw candidate hashes, transcript access, and candidate-change rejection; a Linux-only suite is insufficient proof of the Windows worker.

## Installed acceptance proof

Green source CI and an installed runtime are separate milestones. After installing a green immutable release, record coordinator SHA and worker script hashes, retain one worker, and use the existing handoff/adoption path without competing writers. Wait for any live child before replacing its worker.

Prove the disposable lifecycle canary on the installed bridge: an actual objection, a substantive repair, independent nonzero tests on the same clean committed candidate, an approving review with readable transcripts, passing machine traceability, and automatic execution of the next planned stage. Record the exact failed requirement rows if any step fails; neither delete the requirement nor force an approval to finish the fixture.

Then reconcile the existing ChakraOps dirty files without losing work, remove only demonstrated generated/duplicate artifacts, commit and push the scoped source repair, independently test that committed candidate, and obtain review on the same evidence. Prove automatic continuation into `no_signal_evidence` and produce actual evaluated-candidate rejection counts and reasons. Until these installed proofs exist, report orchestration acceptance as unproven and the application charter as incomplete. Keep account data, licensed snapshots, credentials, and private transcripts out of public GitHub.

