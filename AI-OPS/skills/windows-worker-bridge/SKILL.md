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

## Software objective (requirements, council, tests, release candidate)

```
python3 /opt/neewa/neewa-os/12_SCRIPTS/neewa_autonomy.py run \
  --objective "build a project-status application" \
  --project-id PRJ-NEEWA \
  --workdir /workspace/windows-jobs/autonomy/work
python3 /opt/neewa/neewa-os/12_SCRIPTS/neewa_autonomy.py get --job-id JOB-<id>
```

Do not ask the owner to paste the same prompt into Cursor. Child coding still
uses `neewa_orchestrate.py` `code_implementation` as below.

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
