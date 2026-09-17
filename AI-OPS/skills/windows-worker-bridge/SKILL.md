# NEEWA Windows worker bridge

When the owner asks from NEEWA Conversation to inventory Windows projects,
delegate coding, check job status, or summarize work, use this skill.
Do not say Windows execution is unavailable. Do not open a listener.
Do not request a raw Windows shell. Do not ask the owner to paste the
task into Cursor.

Inside the Hermes Docker sandbox the worker-visible inbox is
`/workspace/windows-jobs`. `12_SCRIPTS/neewa_orchestrate.py` writes records
and jobs there automatically.

## Show connected projects

```
python3 /opt/neewa/neewa-os/12_SCRIPTS/neewa_orchestrate.py submit --capability project_inventory --objective "show connected personal projects" --job-id JOB-<utc>-WS --approval A0
python3 /opt/neewa/neewa-os/12_SCRIPTS/neewa_orchestrate.py wait --job-id JOB-<utc>-WS --timeout-sec 90
```

## Software objective (requirements, council, Cursor, tests, release candidate)

Do not run the demo-status fixture. Do not ask the owner to paste into Cursor.
Submit a parent job and return the job_id immediately. The host runner advances it.

```
python3 /opt/neewa/neewa-os/12_SCRIPTS/neewa_autonomy.py submit \
  --objective "<owner software objective>" \
  --project-id PRJ-NEEWA \
  --workspace "C:\\Users\\swap2\\NEEWA-Personal\\cursor-sandbox" \
  --origin conversation \
  --unattended
python3 /opt/neewa/neewa-os/12_SCRIPTS/neewa_autonomy.py get --job-id JOB-<id>
```

Implementation is a child `cursor_call` through `neewa_orchestrate.py`.
Do not call `--fixture demo-status` for real owner work.
Do not wait in the chat for Cursor; report the parent job_id and current state.

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

## What NEEWA can do (truthful)

- Submit durable software jobs that Cursor implements on the Windows worker.
- Submit durable research/document jobs grounded in the approved local source pack.
- Report job_id, state, worker, artifacts, tests/citations, and cost basis (measured, conservative estimate, or unknown).
- Codex/Claude/Gemini CLIs are not installed; failover is UNVERIFIED.
- Home spoken voice remains PENDING_PHYSICAL and is not this path.
- A2/A3 (publish, deploy, spend, secrets, trades) stay blocked. Job JSON cannot approve them.

## Delegate coding to Cursor (approved personal repo or cursor-sandbox)

```
python3 /opt/neewa/neewa-os/12_SCRIPTS/neewa_orchestrate.py submit \
  --capability code_implementation \
  --job-id JOB-<utc>-CC \
  --objective "<one sentence>" \
  --repo "C:\\Users\\swap2\\NEEWA-Personal\\cursor-sandbox" \
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

Science Quest lives under KidsProjects (`ACCESS_APPROVED` parent). It is not
a separately connected production project.

A0/A1 approved-repo work does not need a new owner confirmation.
A2/A3 (publish, deploy, spend, secrets, trades) stay blocked.
