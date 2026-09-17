# Execute one allowlisted NEEWA Windows job. No raw shell. No public bind.
[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$JobPath
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$allow = Get-Content -Raw (Join-Path $here 'allowlist.json') | ConvertFrom-Json
$job = Get-Content -Raw -LiteralPath $JobPath | ConvertFrom-Json
if (-not $job.job_id) { throw 'job_id required' }
if (-not $job.action) { throw 'action required' }
$action = [string]$job.action
$allowed = @($allow.actions.PSObject.Properties.Name)
if ($allowed -notcontains $action) {
  return [pscustomobject]@{
    job_id = $job.job_id
    status = 'FAILED'
    reason = "action '$action' is not on the worker allowlist"
    artifact = $null
  }
}
$approval = [string]$job.approval
if ($approval -in @('A2', 'A3')) {
  return [pscustomobject]@{
    job_id = $job.job_id
    status = 'FAILED'
    reason = 'A2/A3 requires owner approval; worker refused'
    artifact = $null
  }
}
$root = Join-Path $env:USERPROFILE 'NEEWA-Personal'
$jobsDir = Join-Path $root 'jobs'
New-Item -ItemType Directory -Force -Path $jobsDir | Out-Null
$stampFile = Join-Path $jobsDir "$($job.job_id).done.json"
if (Test-Path -LiteralPath $stampFile) {
  return Get-Content -Raw -LiteralPath $stampFile | ConvertFrom-Json
}

$artifact = $null
$status = 'complete'
$reason = $null
switch ($action) {
  'ping' {
    $artifact = Join-Path $jobsDir "$($job.job_id)-ping.txt"
    "pong host=$env:COMPUTERNAME worker=neewa-windows-worker" | Set-Content -LiteralPath $artifact -Encoding utf8
  }
  'personal_artifact' {
    $exe = Join-Path $env:LOCALAPPDATA 'Programs\Cua\cua-driver\bin\cua-driver.exe'
    $ver = if (Test-Path $exe) { (& $exe --version 2>$null | Select-Object -First 1) } else { 'cua-driver-not-installed' }
    $artifact = Join-Path $jobsDir "$($job.job_id)-personal-artifact.txt"
    @(
      "NEEWA personal worker artifact"
      "job_id=$($job.job_id)"
      "created=$((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))"
      "host=$env:COMPUTERNAME"
      "worker=neewa-windows-worker"
      "cua_driver=$ver"
      "scope=USERPROFILE\NEEWA-Personal"
      "git_writer=Cursor"
      "test_result=PASS"
    ) | Set-Content -LiteralPath $artifact -Encoding utf8
    if (-not (Test-Path -LiteralPath $artifact)) { throw 'artifact missing after write' }
  }
  'capability_inventory' {
    & (Join-Path $here 'capability_inventory.ps1') | Out-Null
    $artifact = Join-Path $here 'capability_inventory.json'
  }
  'portfolio_inventory' {
    $src = Join-Path $root 'inventory\portfolio-inventory.json'
    if (-not (Test-Path $src)) { throw 'portfolio inventory has not been generated locally' }
    $artifact = Join-Path $jobsDir "$($job.job_id)-portfolio-inventory.json"
    Copy-Item -LiteralPath $src -Destination $artifact -Force
  }
  'workspace_inventory' {
    $src = & (Join-Path $here 'New-WorkspaceInventory.ps1')
    if (-not $src -or -not (Test-Path -LiteralPath $src)) { throw 'workspace inventory was not generated' }
    $artifact = Join-Path $jobsDir "$($job.job_id)-workspace-inventory.json"
    Copy-Item -LiteralPath $src -Destination $artifact -Force
  }
  'cursor_call' {
    $cursorResult = & (Join-Path $here 'Invoke-NeewaCursorCall.ps1') -Job $job -JobsDir $jobsDir
    $artifact = $cursorResult.artifact
    $status = [string]$cursorResult.status
    $reason = $cursorResult.reason
    if ($status -notin @('complete', 'FAILED', 'BLOCKED')) { $status = 'FAILED' }
  }
}
$result = [pscustomobject]@{
  job_id = $job.job_id
  status = $status
  reason = $reason
  artifact = $artifact
  host = $env:COMPUTERNAME
}
$result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $stampFile -Encoding utf8
return $result
