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
