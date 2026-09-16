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
- `portfolio_inventory` — copies a previously generated read-only report

A2/A3 jobs are refused. Unknown actions return `FAILED`.

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

## Rollback

```
pwsh -File .\Register-NeewaWindowsStartup.ps1 -Remove
cua-driver stop
# optional binary removal:
# powershell -File %USERPROFILE%\NEEWA-Personal\vendor\cua-driver-install\uninstall.ps1
```
