# Failure Injection Plan

Before trusting NEEWA, simulate:

1. OpenAI provider returns rate limit.
2. Codex worker unavailable.
3. Worker produces failing tests.
4. Reviewer finds HIGH defect.
5. Same remediation fails twice.
6. Budget threshold reached.
7. GPU worker timeout.
8. Voice unavailable.
9. Unexpected network destination.
10. Missing evidence with worker claiming "done".

Expected behavior must match policy; no manual prompt-shuttling should be needed for normal recovery.
