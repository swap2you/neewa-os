# Skill: NEEWA Windows worker + Cursor delegation

Use the existing outbound Windows job inbox. Do not open a public listener
and do not request an unrestricted Windows shell.

## Read-only Workspace inventory (does not use Cursor)

```
python3 /opt/neewa/neewa-os/12_SCRIPTS/windows_job_inbox.py enqueue \
  --job-id JOB-<stamp>-WS \
  --action workspace_inventory \
  --approval A1
```

Then inspect:

```
python3 /opt/neewa/neewa-os/12_SCRIPTS/windows_job_inbox.py status
```

The report lists approved personal project directories under
`C:\Development\Workspace`. Denied/unclassified trees are named and skipped.

## Cursor call (approved personal repos only)

```
python3 /opt/neewa/neewa-os/12_SCRIPTS/windows_job_inbox.py enqueue \
  --job-id JOB-<stamp>-CC \
  --action cursor_call \
  --approval A1 \
  --repo "C:\\Users\\<owner>\\NEEWA-Personal\\cursor-sandbox" \
  --prompt "Create NEEWA-CURSOR-OK.txt containing NEEWA-CURSOR-OK only." \
  --write
```

`cursor.cmd` is the IDE launcher and is not this interface. The worker looks
for `agent --print`. Missing CLI or auth is `BLOCKED`, never success.

A2/A3 cannot be enqueued. Do not target employer/fintech/trading trees.
