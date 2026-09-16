# Worker Architecture

Workers are roles, not permanent personalities.

## Worker classes
- Research worker
- Coding implementation worker
- Code review worker
- Browser/UAT worker
- Content production worker
- Media worker
- QA/evidence worker

## Local edge
Use NEEWA-EDGE-01 for:
- local repositories;
- existing paid coding subscriptions;
- browser/UAT requiring local runtime;
- local media tools;
- sanitized local model work;
- Windows computer-use via locally installed cua-driver (not the Ubuntu sandbox).

The remote NEEWA brain cannot drive this desktop because Hermes Desktop is connected to it. Governed jobs are polled outbound over Tailscale SSH by `16_WINDOWS_CLIENT/worker`. Cursor remains the Git writer.

## Cloud/GPU
Use on-demand GPU only when:
- required model cannot run economically on edge;
- video/image generation benefits materially;
- workload has a bounded budget.

Workers receive:
- objective;
- relevant project context;
- skill;
- file/worktree scope;
- budget;
- acceptance tests;
- stop conditions.

Workers do not receive unrelated project history.
