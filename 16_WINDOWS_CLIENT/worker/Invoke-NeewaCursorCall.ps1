# Governed Cursor Agent CLI invocation. No raw shell. Approved repos only.
[CmdletBinding()]
param(
  [Parameter(Mandatory)][pscustomobject]$Job,
  [Parameter(Mandatory)][string]$JobsDir,
  [string]$PolicyPath,
  [string]$CliPathOverride
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $PolicyPath) { $PolicyPath = Join-Path $here 'cursor-call-policy.json' }
$policy = Get-Content -Raw -LiteralPath $PolicyPath | ConvertFrom-Json

function Expand-UserPath([string]$value) {
  if (-not $value) { return $value }
  return [Environment]::ExpandEnvironmentVariables($value)
}

function Get-AgentCli {
  if ($CliPathOverride) {
    if (Test-Path -LiteralPath $CliPathOverride) { return (Resolve-Path -LiteralPath $CliPathOverride).Path }
    return $null
  }
  foreach ($rel in @($policy.cli_rel_paths)) {
    $candidate = Expand-UserPath $rel
    if (Test-Path -LiteralPath $candidate) { return $candidate }
  }
  foreach ($name in @($policy.cli_names)) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -and ($cmd.Source -match '\.(cmd|exe)$') -and ($cmd.Source -notmatch '\\cursor\\resources\\app\\bin\\cursor')) {
      return $cmd.Source
    }
  }
  return $null
}

function Test-SensitivePrompt([string]$text) {
  $lower = $text.ToLowerInvariant()
  foreach ($frag in @($policy.sensitive_prompt_substrings)) {
    if ($frag -and $lower.Contains($frag.ToLowerInvariant())) { return $true }
  }
  return $false
}

function Resolve-ApprovedRepo([string]$requested) {
  $workspaceRoot = [string]$policy.workspace_root
  $sandbox = Expand-UserPath ([string]$policy.sandbox_repo)
  $candidates = @()
  if ($sandbox) { $candidates += $sandbox }
  foreach ($name in @($policy.approved_repo_names)) {
    $candidates += (Join-Path $workspaceRoot $name)
  }
  $fullRequested = [System.IO.Path]::GetFullPath($requested)
  foreach ($c in $candidates) {
    $full = [System.IO.Path]::GetFullPath($c)
    if ($fullRequested.Equals($full, [System.StringComparison]::OrdinalIgnoreCase)) { return $full }
  }
  return $null
}

$jobId = [string]$Job.job_id
$prompt = [string]$Job.prompt
$requestedRepo = [string]$Job.repo
if (-not $requestedRepo) { $requestedRepo = [string]$Job.workspace_path }
$write = [bool]($Job.write)
$timeoutSec = 180
if ($Job.timeout_sec) { $timeoutSec = [int]$Job.timeout_sec }
$maxTimeout = [int]$policy.max_timeout_sec
if ($timeoutSec -lt 15) { $timeoutSec = 15 }
if ($timeoutSec -gt $maxTimeout) { $timeoutSec = $maxTimeout }

function New-CursorResult($status, $reason, $artifact, $extra) {
  $obj = [ordered]@{
    job_id = $jobId
    action = 'cursor_call'
    status = $status
    reason = $reason
    artifact = $artifact
    host = $env:COMPUTERNAME
    worker = 'neewa-windows-worker'
    git_writer = 'Cursor'
    public_listener = $false
    unrestricted_shell = $false
  }
  if ($extra) { foreach ($k in $extra.Keys) { $obj[$k] = $extra[$k] } }
  return [pscustomobject]$obj
}

$artifact = Join-Path $JobsDir "$jobId-cursor-call.json"
$logPath = Join-Path $JobsDir "$jobId-cursor-call.log"

if (-not $prompt) {
  $r = New-CursorResult 'FAILED' 'cursor_call requires prompt' $null $null
  [System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
  $r.artifact = $artifact
  return $r
}
if (Test-SensitivePrompt $prompt) {
  $r = New-CursorResult 'BLOCKED' 'prompt matches a sensitive pattern; A2/A3 owner gate required' $null $null
  [System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
  $r.artifact = $artifact
  return $r
}
if (-not $requestedRepo) {
  $r = New-CursorResult 'FAILED' 'cursor_call requires repo or workspace_path' $null $null
  [System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
  $r.artifact = $artifact
  return $r
}

$deniedHit = $false
foreach ($denied in @($policy.denied_name_equals)) {
  if ($requestedRepo.ToLowerInvariant().Contains($denied.ToLowerInvariant())) { $deniedHit = $true }
}
if ($deniedHit) {
  $r = New-CursorResult 'BLOCKED' 'repo is on the denied list' $null $null
  [System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
  $r.artifact = $artifact
  return $r
}

$repo = Resolve-ApprovedRepo $requestedRepo
if (-not $repo) {
  $r = New-CursorResult 'BLOCKED' 'repo is not on the approved personal cursor_call list' $null $null
  [System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
  $r.artifact = $artifact
  return $r
}
if (-not (Test-Path -LiteralPath $repo)) {
  $r = New-CursorResult 'FAILED' "approved repo path is missing: $repo" $null $null
  [System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
  $r.artifact = $artifact
  return $r
}

$cli = Get-AgentCli
if (-not $cli) {
  $r = New-CursorResult 'BLOCKED' 'Cursor Agent CLI (agent --print) is not installed' $null @{
    ide_launcher_note = 'cursor.cmd is the IDE launcher and is not this interface'
  }
  [System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
  $r.artifact = $artifact
  return $r
}

$argList = @(
  '--print',
  '--output-format', 'json',
  '--trust',
  '--sandbox', 'enabled',
  '--workspace', $repo
)
if ($write) { $argList += '--force' } else { $argList += '--mode'; $argList += 'ask' }
$argList += $prompt

$stdoutFile = Join-Path $JobsDir "$jobId-cursor-call.stdout.txt"
$stderrFile = Join-Path $JobsDir "$jobId-cursor-call.stderr.txt"
$started = Get-Date
$proc = Start-Process -FilePath $cli -ArgumentList $argList -WorkingDirectory $repo -PassThru -NoNewWindow -RedirectStandardOutput $stdoutFile -RedirectStandardError $stderrFile
$exited = $proc.WaitForExit($timeoutSec * 1000)
if (-not $exited) {
  try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch {}
  $r = New-CursorResult 'FAILED' "cursor_call timed out after ${timeoutSec}s and was cancelled" $null @{
    cli = $cli
    repo = $repo
    log = $logPath
    cancelled = $true
  }
  [System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
  $r.artifact = $artifact
  return $r
}
$exitCode = $proc.ExitCode
$duration = [int]((Get-Date) - $started).TotalSeconds
$stdout = if (Test-Path $stdoutFile) { Get-Content -Raw -LiteralPath $stdoutFile } else { '' }
$stderr = if (Test-Path $stderrFile) { Get-Content -Raw -LiteralPath $stderrFile } else { '' }
$combined = @("exit=$exitCode duration_sec=$duration cli=$cli repo=$repo", $stdout, $stderr) -join "`n"
[System.IO.File]::WriteAllText($logPath, $combined, [System.Text.UTF8Encoding]::new($false))

$authFail = ($stderr + $stdout) -match '(?i)(authentication required|not logged in|login required|unauthorized|unauthenticated|please run ''agent login'')'
if ($exitCode -ne 0 -or $authFail) {
  $status = if ($authFail -or $exitCode -eq $null) { 'BLOCKED' } else { 'FAILED' }
  if ($authFail) { $status = 'BLOCKED' }
  $reason = if ($authFail) { 'Cursor Agent CLI is not authenticated' } else { "Cursor Agent CLI exited $exitCode" }
  $r = New-CursorResult $status $reason $artifact @{
    cli = $cli
    repo = $repo
    exit_code = $exitCode
    duration_sec = $duration
    log = $logPath
    stdout_tail = if ($stdout) { $stdout.Substring([Math]::Max(0, $stdout.Length - 2000)) } else { '' }
  }
  [System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
  $r.artifact = $artifact
  return $r
}

$r = New-CursorResult 'complete' $null $artifact @{
  cli = $cli
  repo = $repo
  exit_code = $exitCode
  duration_sec = $duration
  log = $logPath
  write = $write
  stdout_tail = if ($stdout) { $stdout.Substring([Math]::Max(0, $stdout.Length - 4000)) } else { '' }
}
[System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
$r.artifact = $artifact
return $r
