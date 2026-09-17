# NEEWA Windows companion capability discovery.
# Reports AVAILABLE / NOT INSTALLED / AUTH REQUIRED / PERMISSION REQUIRED / UNSUPPORTED.
# Does not execute employer tools, does not print secrets, does not open a listener.

$ErrorActionPreference = 'Continue'
$script:out = [System.Collections.Generic.List[object]]::new()

function Add-Cap {
  param($Name, $Status, $Detail)
  $script:out.Add([pscustomobject]@{ name = $Name; status = $Status; detail = $Detail }) | Out-Null
}

function Find-Cmd($names) {
  foreach ($n in $names) {
    $c = Get-Command $n -ErrorAction SilentlyContinue
    if ($c) { return $c }
  }
  return $null
}

$git = Find-Cmd @('git')
if ($git) {
  $ver = (& git --version) 2>$null
  Add-Cap 'Git' 'AVAILABLE' $ver
} else { Add-Cap 'Git' 'NOT INSTALLED' '' }

$cursor = Find-Cmd @('cursor', 'cursor.cmd')
if ($cursor) {
  $ver = (& $cursor.Source --version) 2>$null | Select-Object -First 1
  Add-Cap 'Cursor IDE CLI' 'AVAILABLE' "$($cursor.Source) $ver"
} else { Add-Cap 'Cursor IDE CLI' 'NOT INSTALLED' 'Desktop app may exist without CLI on PATH' }

$agent = Find-Cmd @('agent', 'agent.cmd', 'cursor-agent')
if (-not $agent) {
  foreach ($p in @(
      (Join-Path $env:USERPROFILE '.local\bin\agent.exe'),
      (Join-Path $env:USERPROFILE '.local\bin\agent.cmd')
    )) {
    if (Test-Path $p) { $agent = Get-Item $p; break }
  }
}
if ($agent) {
  $src = if ($agent.Source) { $agent.Source } else { $agent.FullName }
  $ver = (& $src --version) 2>$null | Select-Object -First 1
  Add-Cap 'Cursor Agent CLI' 'AVAILABLE' "$src $ver"
} else {
  Add-Cap 'Cursor Agent CLI' 'NOT INSTALLED' 'required for cursor_call (agent --print); cursor.cmd is not this interface'
}

$codex = Find-Cmd @('codex', 'codex.cmd')
if ($codex) {
  Add-Cap 'Codex CLI' 'AVAILABLE' $codex.Source
} else { Add-Cap 'Codex CLI' 'NOT INSTALLED' '' }

$gh = Find-Cmd @('gh')
if ($gh) {
  $auth = (& gh auth status 2>&1 | Out-String)
  if ($auth -match 'Logged in') { Add-Cap 'GitHub CLI' 'AVAILABLE' 'authenticated' }
  else { Add-Cap 'GitHub CLI' 'AUTH REQUIRED' 'gh present, not logged in' }
} else { Add-Cap 'GitHub CLI' 'NOT INSTALLED' '' }

$tailscale = Find-Cmd @('tailscale')
if ($tailscale) {
  $st = (& tailscale status --json 2>$null)
  if ($st) { Add-Cap 'Tailscale' 'AVAILABLE' 'status json readable' }
  else { Add-Cap 'Tailscale' 'PERMISSION REQUIRED' 'binary present, status failed' }
} else { Add-Cap 'Tailscale' 'NOT INSTALLED' '' }

$ssh = Find-Cmd @('ssh')
if ($ssh) { Add-Cap 'OpenSSH client' 'AVAILABLE' $ssh.Source } else { Add-Cap 'OpenSSH client' 'NOT INSTALLED' '' }

$personal = Join-Path $env:USERPROFILE 'NEEWA-Personal'
if (Test-Path $personal) { Add-Cap 'Personal workspace' 'AVAILABLE' $personal }
else { Add-Cap 'Personal workspace' 'PERMISSION REQUIRED' "create $personal for scoped worker tasks" }

$workspace = 'C:\Development\Workspace'
if (Test-Path -LiteralPath $workspace) {
  Add-Cap 'Workspace inventory' 'AVAILABLE' 'read-only personal allowlist via workspace_inventory'
  Add-Cap 'cursor_call' 'AVAILABLE' 'A1 agent --print on approved personal repos; missing CLI is BLOCKED'
} else {
  Add-Cap 'Workspace inventory' 'PERMISSION REQUIRED' $workspace
}

Add-Cap 'Employer files' 'UNSUPPORTED' 'explicitly excluded from the worker allowlist'
Add-Cap 'Unrestricted Windows shell' 'UNSUPPORTED' 'remote model must not receive a raw shell'
Add-Cap 'Public listener' 'UNSUPPORTED' 'outbound/poll only'

$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$report = Join-Path $dir 'capability_inventory.json'
$script:out | ConvertTo-Json -Depth 4 | Set-Content -Path $report -Encoding utf8
$script:out | Format-Table -AutoSize
Write-Output "wrote $report"
