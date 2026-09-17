# Work order — Workspace inventory

NEEWA on `neewa-core-01` may request a governed **read-only** inventory of
personal projects under `C:\Development\Workspace`.

Enqueue on the existing Windows job inbox (Docker workspace
`windows-jobs/inbox`) with:

```
action: workspace_inventory
approval: A1
```

The `neewa-windows-worker` on `neewa-edge-01` generates metadata only
(folder name, git present, top-level names, status doc). Employer, fintech,
and trading trees are classified `denied` and not recursed. Unlisted folders
are `unclassified` and skipped.

This is **not** write access to Workspace, not full-drive access, and not
unrestricted desktop control. File contents, `.env`, and credentials are
not read. Cursor remains the Git writer.

Sanitized evidence packs: `evidence/LOCAL_WINDOWS_BRIDGE/<timestamp>/`.
Do not commit `%USERPROFILE%\NEEWA-Personal\inventory\workspace-inventory.json`.
