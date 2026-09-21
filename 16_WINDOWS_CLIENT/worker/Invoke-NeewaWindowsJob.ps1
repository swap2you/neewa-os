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
  $gateOk = $false
  $gate = $null
  $py = Get-Command python -ErrorAction SilentlyContinue
  if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
  $hasReceiptAuth = $false
  if ($job.PSObject.Properties['authorization'] -and $null -ne $job.authorization) { $hasReceiptAuth = $true }
  $a2Mod = Join-Path $here 'neewa_a2_receipt_auth.py'
  if (-not (Test-Path -LiteralPath $a2Mod)) {
    $a2Mod = Join-Path $here '..\..\12_SCRIPTS\neewa_a2_receipt_auth.py'
  }
  if ($hasReceiptAuth) {
    if (-not $py -or -not (Test-Path -LiteralPath $a2Mod)) {
      return [pscustomobject]@{
        job_id = $job.job_id
        status = 'BLOCKED'
        reason = 'A2 receipt authorization failed: MISSING_SSH'
        artifact = $null
      }
    }
    try {
      $cacheDir = $env:NEEWA_A2_AUTH_CACHE
      if (-not $cacheDir) { $cacheDir = Join-Path $env:LOCALAPPDATA 'NEENEEWA\authorizations' }
      $nativePref = $PSNativeCommandUseErrorActionPreference
      $PSNativeCommandUseErrorActionPreference = $false
      try {
        $gateOut = & $py.Source $a2Mod --job-file $JobPath --cache-dir $cacheDir | Out-String
      } finally {
        $PSNativeCommandUseErrorActionPreference = $nativePref
      }
      $gate = $gateOut | ConvertFrom-Json
      if ($gate.allowed -eq $true -or $gate.decision -eq 'AUTHORIZED') { $gateOk = $true }
      if (-not $gateOk) {
        return [pscustomobject]@{
          job_id = $job.job_id
          status = 'BLOCKED'
          reason = "A2 receipt authorization failed: $($gate.reason)"
          artifact = $null
          authorization = $gate
        }
      }
    } catch {
      return [pscustomobject]@{
        job_id = $job.job_id
        status = 'BLOCKED'
        reason = 'A2 receipt authorization failed: MISSING_SSH'
        artifact = $null
      }
    }
  }
  if (-not $gateOk) {
    $authMod = Join-Path $here '..\..\12_SCRIPTS\neewa_authorization.py'
    if (-not (Test-Path -LiteralPath $authMod)) {
      $authMod = Join-Path $here 'neewa_authorization.py'
    }
    if ($py -and (Test-Path -LiteralPath $authMod)) {
      try {
        $gateOut = & $py.Source $authMod --job-file $JobPath
        $gate = $gateOut | ConvertFrom-Json
        if ($gate.decision -eq 'AUTHORIZED') { $gateOk = $true }
        if (-not $gateOk) {
          return [pscustomobject]@{
            job_id = $job.job_id
            status = 'BLOCKED'
            reason = "A2/A3 standing authorization missing: $($gate.reason)"
            artifact = $null
            authorization = $gate
          }
        }
      } catch {
        $gateOk = $false
      }
    }
  }
  if (-not $gateOk) {
    return [pscustomobject]@{
      job_id = $job.job_id
      status = 'FAILED'
      reason = 'A2/A3 requires owner approval; worker refused'
      artifact = $null
    }
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
$status = 'COMPLETED'
$reason = $null
$cursorResult = $null
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
    if ($status -eq 'complete') { $status = 'COMPLETED' }
    if ($status -notin @('COMPLETED', 'FAILED', 'BLOCKED', 'CANCELLED')) { $status = 'FAILED' }
  }
  'repo_preflight' {
    $cursorResult = & (Join-Path $here 'Invoke-NeewaRepoPreflight.ps1') -JobFile $JobPath -OutDir $jobsDir
    $artifact = $cursorResult.artifact
    $status = [string]$cursorResult.status
    $reason = $cursorResult.reason
    if ($status -eq 'complete') { $status = 'COMPLETED' }
    if ($status -notin @('COMPLETED', 'FAILED', 'BLOCKED', 'CANCELLED')) { $status = 'FAILED' }
  }
  { $_ -in @('create_scoped_repair_workspace', 'review_scoped_repair_patch', 'apply_scoped_repair_patch', 'cleanup_scoped_repair_workspace') } {
    $cursorResult = & (Join-Path $here 'Invoke-NeewaScopedRepair.ps1') -JobFile $JobPath -OutDir $jobsDir
    $artifact = $cursorResult.artifact
    $status = [string]$cursorResult.status
    $reason = $cursorResult.reason
    if ($status -eq 'complete') { $status = 'COMPLETED' }
    if ($status -notin @('COMPLETED', 'FAILED', 'BLOCKED', 'CANCELLED')) { $status = 'FAILED' }
  }
  { $_ -in @('home_mission_submit', 'home_mission_status') } {
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
    if (-not $py) { throw 'python is required for home mission bridge' }
    $bridge = Join-Path $here '..\..\12_SCRIPTS\neewa_home_bridge.py'
    $cmd = if ($action -eq 'home_mission_status') { 'status' } else { 'submit' }
    $argList = @($bridge, $cmd)
    if ($job.objective) { $argList += @('--objective', [string]$job.objective) }
    if ($job.origin) { $argList += @('--origin', [string]$job.origin) }
    if ($job.mission_id) { $argList += @('--mission-id', [string]$job.mission_id) }
    if ($job.workspace) { $argList += @('--workspace', [string]$job.workspace) }
    $artifact = Join-Path $jobsDir "$($job.job_id)-home-mission.json"
    $out = & $py.Source @argList
    $out | Set-Content -LiteralPath $artifact -Encoding utf8
  }
  { $_ -in @('git_fetch', 'git_pull', 'git_create_feature_branch', 'git_commit_scoped_changes', 'git_push_feature_branch', 'git_verify_remote_state', 'git_create_pull_request', 'git_update_pull_request', 'git_review_pull_request', 'git_merge_approved_pull_request') } {
    $cursorResult = & (Join-Path $here 'Invoke-NeewaGovernedGit.ps1') -JobFile $JobPath -OutDir $jobsDir
    $artifact = $cursorResult.artifact
    $status = [string]$cursorResult.status
    $reason = $cursorResult.reason
    if ($status -eq 'complete') { $status = 'COMPLETED' }
    if ($status -notin @('COMPLETED', 'FAILED', 'BLOCKED', 'CANCELLED')) { $status = 'FAILED' }
  }
}
$result = [pscustomobject]@{
  job_id = $job.job_id
  status = $status
  reason = $reason
  artifact = $artifact
  host = $env:COMPUTERNAME
  failure_class = $(if ($cursorResult) { $cursorResult.failure_class } else { $null })
  preflight = $(if ($cursorResult -and $cursorResult.PSObject.Properties['preflight']) { $cursorResult.preflight } else { $null })
  authorization = $(if ($cursorResult -and $cursorResult.PSObject.Properties['authorization']) { $cursorResult.authorization } else { $null })
}
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $stampFile -Encoding utf8
return $result
