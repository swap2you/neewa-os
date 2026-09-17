# Orchestration acceptance

Evidence for Conversation-to-Cursor activation. Each PASS needs a real artifact.

| Gate | Meaning | Evidence |
| --- | --- | --- |
| CURSOR_CLI_AUTHENTICATED | Agent CLI `status` is logged in, same user as the worker | worker-invoked cursor_call not AUTH_REQUIRED |
| WINDOWS_WORKER_ONLINE | poller pid, same Windows user | `Start-NeewaWindowsWorker` process |
| CONVERSATION_JOB_SUBMITTED | Hermes Conversation ran orchestrate/enqueue | hermes -z output path |
| JOB_INBOX_VISIBLE | job on bind-mount inbox | `/workspace/windows-jobs/inbox` host copy |
| CURSOR_CALL_EXECUTED | Agent CLI started | args file + log + exit |
| REAL_FILES_CREATED | expected paths exist on disk | independent listing |
| REAL_TESTS_EXECUTED | tests actually ran | test output in evidence |
| RESULT_VALIDATED | worker did not accept a claim | missing expected files => FAILED |
| EVIDENCE_RETURNED | done/failed JSON on core | windows-jobs/done or failed |
| NEEWA_JOB_UPDATED | records JSON state terminal | windows-jobs/records |
| NEEWA_RESULT_REPORTED | Conversation printed job state | hermes output |
| PROJECT_ACCESS_SCOPED | denied trees untouched | inventory classifications |
| SECURITY_VERIFIED | no public listener, no raw shell, A2/A3 refused | tests + allowlist |
| GIT_SYNCHRONIZED | origin/main and neewa-core-01 ff-only | git SHA |

Filled 2026-09-17 against origin/main after JOB-20260917-CONV-CC-005.

| Gate | Result | Evidence |
| --- | --- | --- |
| CURSOR_CLI_AUTHENTICATED | PASS | `agent status --format json` isAuthenticated; worker-invoked JOB-20260917-WORKER-AUTH2 result PONG |
| WINDOWS_WORKER_ONLINE | PASS | pid 35488, user swap2 |
| CONVERSATION_JOB_SUBMITTED | PASS | hermes -z orchestrate submit CONV-CC-004/005 |
| JOB_INBOX_VISIBLE | PASS | `/workspace/windows-jobs/inbox` bind-mount |
| CURSOR_CALL_EXECUTED | PASS | agent.cmd exit 0, 88s then 51s |
| REAL_FILES_CREATED | PASS | sample.json, project_health.py, test_project_health.py |
| REAL_TESTS_EXECUTED | PASS | independent `python -m unittest` 5 OK; Cursor reported 5 passed |
| RESULT_VALIDATED | PASS | CONV-CC-004 FAILED missing report; CONV-CC-005 COMPLETED all four paths |
| EVIDENCE_RETURNED | PASS | windows-jobs/done and failed JSON |
| NEEWA_JOB_UPDATED | PASS | records history QUEUED→COMPLETED |
| NEEWA_RESULT_REPORTED | PASS | hermes printed COMPLETED JSON |
| PROJECT_ACCESS_SCOPED | PASS | CONV-CC-FAIL BLOCKED OratsUtil |
| SECURITY_VERIFIED | PASS | no public listener; A2/A3 refused; no raw shell |
| GIT_SYNCHRONIZED | PASS | see commit SHA on origin/main |
