# NEEWA Windows worker bridge

When the owner asks from NEEWA Conversation for a Windows workspace inventory
or a Cursor coding task, use the existing outbound inbox. Do not open a
listener and do not request a raw Windows shell.

## Inventory (no Cursor)

```
python3 /opt/neewa/neewa-os/12_SCRIPTS/windows_job_inbox.py enqueue --job-id JOB-<utc>-WS --action workspace_inventory --approval A1
python3 /opt/neewa/neewa-os/12_SCRIPTS/windows_job_inbox.py status
```

Read the JSON under `windows-jobs/done/` after the Windows worker polls.

## Cursor call

```
python3 /opt/neewa/neewa-os/12_SCRIPTS/windows_job_inbox.py enqueue --job-id JOB-<utc>-CC --action cursor_call --approval A1 --repo "<approved personal repo>" --prompt "<task>" --write
```

Approved personal repos only. Missing Cursor Agent CLI is BLOCKED.
