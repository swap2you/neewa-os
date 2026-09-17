# JOB-20260917-CONV-CC-001

Origin: NEEWA Conversation (`hermes -z --cli --skills windows-worker-bridge`).
Landed on the worker-visible bind-mount `/workspace/windows-jobs/inbox`.
Action: `cursor_call` A1 against `%USERPROFILE%\NEEWA-Personal\cursor-sandbox`.

Worker invoked `C:\Users\swap2\AppData\Local\cursor-agent\agent.cmd --print`
(exit 1, 2s). Result returned to NEEWA as `BLOCKED`, never `complete`.
Reason: Cursor Agent CLI is not authenticated (`agent login` or `CURSOR_API_KEY`).
No unrestricted shell was used.
