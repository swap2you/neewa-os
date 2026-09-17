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

Do not mark the system complete while cursor_call remains BLOCKED for auth.
