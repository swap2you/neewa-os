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
