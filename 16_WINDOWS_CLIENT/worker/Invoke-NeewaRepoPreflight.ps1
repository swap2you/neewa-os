# A0 Windows repository identity preflight. No Cursor billing. No raw shell.
# A missing path on the Linux core host is not consulted; only this host's filesystem counts.
param(
  [Parameter(Mandatory=$true)]
  [string]$JobFile,
  [Parameter(Mandatory=$true)]
  [string]$OutDir,
  [string]$PolicyFile
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $PolicyFile) { $PolicyFile = Join-Path $here 'cursor-call-policy.json' }
$Job = Get-Content -Raw -LiteralPath $JobFile | ConvertFrom-Json
$policy = Get-Content -Raw -LiteralPath $PolicyFile | ConvertFrom-Json

. (Join-Path $here 'NeewaPersonalWorkspace.ps1')

$jobId = [string]$Job.job_id
$requestedRepo = [string]$Job.repo
if (-not $requestedRepo) { $requestedRepo = [string]$Job.workspace_path }
$markers = @()
if ($Job.markers) { $markers = @($Job.markers) }
$artifact = Join-Path $OutDir "$jobId-repo-preflight.json"

function New-PreflightResult($status, $reason, $identityOk, $extra) {
  $pre = [ordered]@{
    identity_ok = [bool]$identityOk
    requested_path = $requestedRepo
    approved_path = $null
    exists = $false
    git_ok = $false
    head = $null
    branch = $null
    dirty = $null
    stack_markers_found = ''
    stack_markers_missing = ''
    test_commands = ''
    relevant_files = ''
    reason = $reason
    source = 'windows-worker'
  }
  if ($extra) { foreach ($k in $extra.Keys) { $pre[$k] = $extra[$k] } }
  $obj = [ordered]@{
    job_id = $jobId
    action = 'repo_preflight'
    status = $status
    reason = $reason
    artifact = $artifact
    host = $env:COMPUTERNAME
    worker = 'neewa-windows-worker'
    selected_worker = 'neewa-windows-worker'
    git_writer = 'Cursor'
    public_listener = $false
    unrestricted_shell = $false
    write = $false
    failure_class = $(if ($identityOk) { $null } else { 'REPO_IDENTITY' })
    preflight = [pscustomobject]$pre
  }
  return [pscustomobject]$obj
}

if (-not $requestedRepo) {
  $r = New-PreflightResult 'FAILED' 'repo_preflight requires repo or workspace_path' $false $null
  [System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
  return $r
}

$leaf = [System.IO.Path]::GetFileName($requestedRepo.TrimEnd('\', '/'))
foreach ($denied in @($policy.denied_name_equals)) {
  if ($leaf -and $leaf.Equals($denied, [System.StringComparison]::OrdinalIgnoreCase)) {
    $r = New-PreflightResult 'BLOCKED' 'repo is on the denied list' $false @{ failure_class = 'DENIED_REPO' }
    $r.failure_class = 'DENIED_REPO'
    [System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
    return $r
  }
}

$repo = Resolve-ApprovedRepo $requestedRepo
if (-not $repo) {
  $r = New-PreflightResult 'BLOCKED' 'repo is not on the approved personal list' $false @{ failure_class = 'UNAPPROVED_PATH' }
  $r.failure_class = 'UNAPPROVED_PATH'
  [System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
  return $r
}

$lifecycle = [string]$Job.project_lifecycle
if (-not $lifecycle) { $lifecycle = 'modify_existing' }
$wsRoot = [string]$Job.workspace_root
$bootstrap = Invoke-ProjectBootstrap -Repo $repo -Lifecycle $lifecycle -WorkspaceRoot $wsRoot
if (-not [bool]$bootstrap.identity_ok) {
  $r = New-PreflightResult 'FAILED' $bootstrap.reason $false @{
    approved_path = $repo
    exists = $false
    git_ok = $false
    identity_ok = $false
    failure_class = $bootstrap.failure_class
    project_lifecycle = $lifecycle
    bootstrap = $bootstrap
    target_directory_state = $bootstrap.target_directory_state
    bootstrap_result = $bootstrap.bootstrap_result
  }
  $r.failure_class = $bootstrap.failure_class
  [System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
  return $r
}

$exists = Test-Path -LiteralPath $repo
$gitDir = Join-Path $repo '.git'
$gitOk = $exists -and (Test-Path -LiteralPath $gitDir)
$found = @()
$missing = @()
foreach ($m in $markers) {
  $rel = [string]$m
  if (-not $rel) { continue }
  $fullMarker = Join-Path $repo $rel
  if ($exists -and (Test-Path -LiteralPath $fullMarker)) { $found += $rel } else { $missing += $rel }
}

$testCmds = @()
$relevant = @()
$head = $null
$branch = $null
$dirty = $null
if ($exists) {
  foreach ($name in @('package.json','pyproject.toml','requirements.txt','docker-compose.yml','README.md','apps\api','apps\web')) {
    $p = Join-Path $repo $name
    if (Test-Path -LiteralPath $p) { $relevant += $name.Replace('\','/') }
  }
  $pkg = Join-Path $repo 'package.json'
  if (Test-Path -LiteralPath $pkg) {
    try {
      $pkgObj = Get-Content -Raw -LiteralPath $pkg | ConvertFrom-Json
      if ($pkgObj.scripts -and $pkgObj.scripts.test) { $testCmds += 'npm test' }
    } catch {}
  }
  if ((Test-Path -LiteralPath (Join-Path $repo 'pyproject.toml')) -or (Test-Path -LiteralPath (Join-Path $repo 'requirements.txt'))) {
    $testCmds += 'python -m unittest'
  }
}
if ($gitOk) {
  $head = ((& git -C $repo rev-parse HEAD 2>$null) | Out-String).Trim()
  $branch = ((& git -C $repo rev-parse --abbrev-ref HEAD 2>$null) | Out-String).Trim()
  $dirty = [bool]((& git -C $repo status --porcelain 2>$null | Out-String).Trim())
}

$identityOk = $exists
if ($lifecycle -eq 'modify_existing') {
  $identityOk = $exists -and $gitOk
  if ($markers.Count -gt 0 -and $found.Count -eq 0) { $identityOk = $false }
}
$reason = $null
$status = 'COMPLETED'
if ($lifecycle -eq 'create_new') {
  $reason = $null
} elseif (-not $exists) {
  $status = 'FAILED'
  $reason = "approved repo path is missing on Windows: $repo"
  $identityOk = $false
} elseif (-not $gitOk) {
  $status = 'FAILED'
  $reason = "repository identity could not be established (no .git): $repo"
  $identityOk = $false
} elseif (-not $identityOk) {
  $status = 'FAILED'
  $reason = "stack markers not found: " + ($missing -join ', ')
}

$extra = [ordered]@{
  approved_path = $repo
  exists = $exists
  git_ok = $gitOk
  head = $head
  branch = $branch
  dirty = $dirty
  stack_markers_found = ($found -join ',')
  stack_markers_missing = ($missing -join ',')
  test_commands = ($testCmds -join ',')
  relevant_files = ($relevant -join ',')
  identity_ok = $identityOk
  reason = $reason
  project_lifecycle = $lifecycle
  bootstrap = $bootstrap
  target_directory_state = $bootstrap.target_directory_state
  bootstrap_result = $bootstrap.bootstrap_result
}
$r = New-PreflightResult $status $reason $identityOk $extra
[System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
$r.artifact = $artifact
return $r
