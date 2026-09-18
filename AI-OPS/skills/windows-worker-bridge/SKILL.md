# NEEWA Windows worker bridge

When the owner asks from NEEWA Conversation to inventory Windows projects,
delegate coding, check job status, or summarize work, use this skill.
Do not say Windows execution is unavailable. Do not open a listener.
Do not request a raw Windows shell. Do not ask the owner to paste the
task into Cursor. Do not ask the owner to pick a worker or approve routine A1 steps.

Inside the Hermes Docker sandbox the worker-visible inbox is
`/workspace/windows-jobs`. That bind-mount is the same host directory
`/home/ubuntu/.hermes/sandboxes/docker/default/workspace/windows-jobs`.
The host-shaped path is **not mounted** in the sandbox. Do not inspect
`/home/ubuntu/.hermes/sandboxes/...` and do not run `systemctl`. Creating
the host path inside the container would be an invisible overlay.

`systemctl` is absent in Conversation. Host runner health comes from
`/workspace/windows-jobs/autonomy/runner-heartbeat.json` and
`conversation-status.json`, plus the read-only snapshot
`/opt/neewa/status/autonomy.json` when present.

Before any overnight or unattended software mission, run preflight:

```
python3 /opt/neewa/neewa-os/12_SCRIPTS/neewa_autonomy.py mission-preflight
```

Use that JSON. Do not ask the owner to copy host diagnostics.
`submission_safe=true` means the canonical bind-mount is writable, the
runner heartbeat is fresh, the NEEWA ceiling can reserve the conservative
Cursor estimate, and no host overlay is being used. Provider remaining
credits are reported `UNKNOWN` unless an authoritative API exists; do not
invent a balance. `systemctl` unavailable-in-sandbox is expected.

`12_SCRIPTS/neewa_orchestrate.py` writes records and jobs to
`/workspace/windows-jobs` automatically.

Standing authorization: ordinary personal work under
`C:\Development\Workspace\<project>` and `%USERPROFILE%\NEEWA-Personal`
is already allowed. Do not require a new allowlist entry, project-id
registration, or owner confirmation for each repository, folder, or stack.
Discover a new personal folder by using its Windows path. Registry rows
are descriptive metadata, not gates.

Exclusions that still block work (do not override them):
- Employer/client/trading trees: api-fintech-automation-platform,
  perf-fintech-testing-platform, ui-fintech-automation-platform,
  QE_Platform_lead_Repos, OratsUtil, ChakraOptionsWatch, and names
  containing fintech/employer/brokerage/trading.
- Secrets: `.ssh`, `.aws`, `.gnupg`, credential files.
- The Workspace drive root itself (it contains excluded trees).
- A2/A3: publish/deploy to production, send messages or make commitments
  to external recipients, purchases, financial/trading, irreversible
  deletion, disabling security, disclosing secrets.

Bhāva/Vāṇī and other registry-only rows may be used when the owner gives a
personal workspace path. Without a personal path, submit nothing that would
write; report MISSING_WORKSPACE instead of inventing a location.

## Show connected projects

```
python3 /opt/neewa/neewa-os/12_SCRIPTS/neewa_orchestrate.py submit --capability project_inventory --objective "show connected personal projects" --job-id JOB-<utc>-WS --approval A0
python3 /opt/neewa/neewa-os/12_SCRIPTS/neewa_orchestrate.py wait --job-id JOB-<utc>-WS --timeout-sec 90
```

## Software objective (requirements, council, Cursor, tests, release candidate)

Do not run the demo-status fixture. Do not ask the owner to paste into Cursor.
If the request mentions documentation or review together with tests, debugging,
or repository inspection, still submit an sdlc parent. Classification selects
the workflow; it does not prevent execution.

Submit a persistent mission and return the mission_id immediately. The host
user-systemd runner (`neewa-autonomy-runner.service`) advances it after this
conversation ends. Do not wait in chat. Do not create a second job for the
same mission.

```
python3 /opt/neewa/neewa-os/12_SCRIPTS/neewa_autonomy.py mission-submit \
  --objective "<owner software objective>" \
  --project-id <known id or omit> \
  --workspace "<personal Windows repo path>" \
  --origin conversation
python3 /opt/neewa/neewa-os/12_SCRIPTS/neewa_autonomy.py mission-get --mission-id MISSION-<id>
```

`submit --unattended` is an alias that also creates a mission rather than a
bare parent job. Prefer `mission-submit`. The supervisor persists before
dispatch, refuses duplicate children, and may start at most three repair
cycles with new evidence. It does not reopen historical FAILED jobs.

`--project-id` is optional. Unregistered personal folders are valid when
`--workspace` is under the personal roots and not excluded.

Examples:
- `C:\\Development\\Workspace\\KidsProjects\\ScienceQuest` (`PRJ-KIDS` if known)
- `C:\\Development\\Workspace\\aarohan-careeros` (`PRJ-AAROHAN` if known)
- `C:\\Users\\swap2\\NEEWA-Personal\\cursor-sandbox` for throwaway files
- any other non-denied first-level folder under `C:\\Development\\Workspace`

Do not invent a Python CLI if the repo is Node/TypeScript or mixed FastAPI/Next.js.
Catalog stack labels are metadata, never expected file paths.
Existing repos get an A0 `repo_preflight` identity check on the Windows worker before
Cursor; Linux `exists_here=false` is not proof the Windows path is missing.
Research that is not a Ganesh katha should still be submitted as research; the
controller cites the matching local corpus (OWNER.md / PROJECT_ACCESS.md) or SOURCE_PENDING.

## Research or document objective (source-grounded, no software CLI)

If the owner asks for a katha, research note, or source-grounded document, submit a parent
with the same command. Do not invent scripture. The controller uses the approved local
source pack and records SOURCE_PENDING when a source is missing.

```
python3 /opt/neewa/neewa-os/12_SCRIPTS/neewa_autonomy.py submit \
  --objective "<owner research or katha request>" \
  --project-id PRJ-NEEWA \
  --origin conversation \
  --unattended
```

Do not turn a research request into a Python CLI. Do not publish.
If the owner also asks to inspect a repo, add tests, or debug, use the software
parent instead (multiple capabilities are allowed; sdlc is primary).

## What NEEWA can do (truthful)

- Plan, inspect personal workspaces, delegate to Cursor, edit files, run tests,
  repair within budget, and report with evidence without per-step owner approval.
- Work across personal projects, including folders that are not yet in the registry.
- Submit durable research/document jobs grounded in the approved local source pack.
- Report job_id, state, worker, artifacts, tests/citations, and cost basis (measured, conservative estimate, or unknown).
- Codex CLI is installed and ChatGPT-authenticated. Claude Code is Claude Pro-authenticated and `claude -p` returned pong. Grok CLI is grok.com-authenticated. Gemini CLI Google login works but Google rejected the individual Code Assist client; use Antigravity `agy` instead (`agy -p` returned pong). Failover is UNVERIFIED in NEEWA routing until a governed windows-worker action exists. Claude Cowork is GUI-only.
- Home spoken voice remains PENDING_PHYSICAL and is not this path.
- This is not full computer autonomy: the worker uses the owner's existing Windows
  user permissions, has no unrestricted shell, no public listener, and no admin elevation.
- A2/A3 stay blocked. Job JSON cannot approve them.

## Delegate coding to Cursor (personal repo or cursor-sandbox)

```
python3 /opt/neewa/neewa-os/12_SCRIPTS/neewa_orchestrate.py submit \
  --capability code_implementation \
  --job-id JOB-<utc>-CC \
  --objective "<one sentence>" \
  --repo "<personal Windows repo path>" \
  --prompt "<task>" \
  --write \
  --timeout-sec 300 \
  --expected-path "<relative file>"
python3 /opt/neewa/neewa-os/12_SCRIPTS/neewa_orchestrate.py wait --job-id JOB-<utc>-CC --timeout-sec 360
python3 /opt/neewa/neewa-os/12_SCRIPTS/neewa_orchestrate.py get --job-id JOB-<utc>-CC
```

Then tell the owner: job_id, state, selected_worker, artifact paths, and
whether validation passed. COMPLETED requires real files, not a model claim.

BLOCKED with AUTH_REQUIRED means Cursor Agent CLI login is needed.
FAILED means the worker ran and the task did not meet validation.
Do not report FAILED or BLOCKED as success.

## What is working on / completed work

```
python3 /opt/neewa/neewa-os/12_SCRIPTS/neewa_orchestrate.py list
```

Science Quest lives under KidsProjects. It does not need a separate allowlist entry.

A0/A1 personal-workspace work does not need a new owner confirmation.
A2/A3 (publish, deploy, spend, secrets, trades, external messages) stay blocked.
