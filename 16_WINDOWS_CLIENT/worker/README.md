# NEEWA Windows worker

Outbound / polling only. No public listener. No unrestricted shell.
Employer files, credentials, browsers, and trading apps are out of scope.

Architecture:

```
NEEWA (neewa-core-01 Hermes)
  -> governed job JSON in Docker workspace windows-jobs/inbox
  -> neewa-edge-01 worker polls over Tailscale SSH
  -> allowlisted local action
  -> optional local cua-driver (interactive session)
  -> evidence returned to windows-jobs/done
  -> Cursor remains the Git writer
```

Hermes Desktop talking to the remote gateway does **not** give the Ubuntu
agent Windows computer_use. The driver that can see this desktop is the
one installed on `neewa-edge-01`.

## Allowlisted actions

- `ping`
- `capability_inventory.ps1` — discovery only
- `personal_artifact` — one file under `%USERPROFILE%\NEEWA-Personal\jobs\`
- `portfolio_inventory` — copies a previously generated 08_PROJECTS registry report
- `workspace_inventory` — generates a read-only metadata inventory of
  allowlisted personal projects under `C:\Development\Workspace`. Employer,
  fintech, and trading trees are named and skipped. No file contents, no write
  access to Workspace, no unrestricted desktop.
- `cursor_call` — invokes the **Cursor Agent CLI** (`agent --print --output-format json
  --workspace <approved_repo>`), not `cursor.cmd` (that is the IDE launcher).
  Restricted to approved personal repositories. Routine A1 development does not
  re-prompt. Sensitive prompts (`git push`, live trade, secrets) return
  `BLOCKED`. Missing or unauthenticated CLI returns `BLOCKED`, never `complete`.
  Timeout cancels the process tree. No caller-supplied shell string is executed.
  Conversation uses `12_SCRIPTS/neewa_orchestrate.py` so NEEWA can submit,
  wait, and report without the owner pasting into Cursor.

A2/A3 jobs are refused. Unknown actions return `FAILED`.

NEEWA requests this from `neewa-core-01` by running
`12_SCRIPTS/neewa_orchestrate.py` (or `windows_job_inbox.py`) against the
Docker workspace inbox (`windows-jobs/inbox`). The Windows worker polls that
inbox over outbound Tailscale SSH. Cursor remains the Git writer.

Local evidence packs live under `evidence/LOCAL_WINDOWS_BRIDGE/<timestamp>/`.
Raw inventory JSON stays in `%USERPROFILE%\NEEWA-Personal\inventory` and is
not committed.

## Cua Driver

`cua.ai` has no DNS record (NXDOMAIN). Install with
`Install-CuaDriverFromGitHub.ps1`, which runs the official GitHub
`install.ps1` beside `_install-common.psm1` so the installer never calls
cua.ai. The zip still comes from GitHub Releases.

Telemetry is disabled (`CUA_DRIVER_RS_TELEMETRY_ENABLED=0`).

Do not register `cua-driver mcp` into Cursor, Claude, and Codex at the
same time. Generated snippets live in `mcp-config.preview.json` and are
not applied.

## Startup

`Register-NeewaWindowsStartup.ps1` writes HKCU Run entries (interactive
user logon). It does not create a SYSTEM service and does not use
`cua-driver autostart enable` (that path wants RunLevel=Highest / UAC).

For a stable install outside a disposable sandbox checkout, run
`Install-NeewaWindowsWorker.ps1` (optionally `-Start`). It copies the
required worker files to `%LOCALAPPDATA%\NEEWA\worker`, points
`HKCU\...\Run\NEEWA-WindowsWorker` at that path, and can restart to
exactly one live worker process. `-Remove` clears the Run key;
`-Remove -PurgeFiles` also deletes the installed copy.

`cursor_call` timeout semantics: job `timeout_sec=0` means no
elapsed-time kill. Policy `default_timeout_sec` / `max_timeout_sec`
remain `604800` until host deploy adopts `0`.

## Rollback

```
pwsh -File .\Register-NeewaWindowsStartup.ps1 -Remove
cua-driver stop
# optional binary removal:
# powershell -File %USERPROFILE%\NEEWA-Personal\vendor\cua-driver-install\uninstall.ps1
```
