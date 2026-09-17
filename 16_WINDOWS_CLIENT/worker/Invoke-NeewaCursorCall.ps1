# Governed Cursor Agent CLI invocation. No raw shell. Approved repos only.
# Flags are the official headless set for Agent CLI 2026.09.15-d2fe57e:
#   --print --output-format json --workspace <approved> --sandbox enabled
#   --trust (headless workspace trust only; not system-wide)
#   --mode ask for read-only; --force only for authorized writes
# Never pass yolo, approve-mcps, sandbox disabled, add-dir, or caller-supplied cmd.
[CmdletBinding()]
param(
  [Parameter(Mandatory)][pscustomobject]$Job,
  [Parameter(Mandatory)][string]$JobsDir,
  [string]$PolicyPath,
  [string]$CliPathOverride,
  [switch]$DryRun
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

function Test-BlockedIntent([string]$text) {
  $lower = $text.ToLowerInvariant()
  foreach ($frag in @($policy.blocked_intent_substrings)) {
    if ($frag -and $lower.Contains($frag.ToLowerInvariant())) { return $true }
  }
  return $false
}

function Test-ReparseEscape([string]$path, [string]$approvedRoot) {
  if (-not (Test-Path -LiteralPath $path)) { return $false }
  $item = Get-Item -LiteralPath $path -Force
  if (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { return $false }
  $targets = @($item.Target)
  foreach ($t in $targets) {
    if (-not $t) { continue }
    $fullTarget = [System.IO.Path]::GetFullPath($t)
    $root = $approvedRoot.TrimEnd('\') + '\'
    if (-not $fullTarget.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase) -and
        -not $fullTarget.Equals($approvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
      return $true
    }
  }
  return $false
}

function Resolve-ApprovedRepo([string]$requested) {
  if (-not $requested) { return $null }
  if ($requested -match '\.\.') { return $null }
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
    $prefix = $full.TrimEnd('\') + '\'
    $isExact = $fullRequested.Equals($full, [System.StringComparison]::OrdinalIgnoreCase)
    $isChild = $fullRequested.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)
    if ($isExact -or $isChild) {
      if (Test-ReparseEscape $fullRequested $full) { return $null }
      if (Test-ReparseEscape $full $full) { return $null }
      # Keep approved child folders (e.g. KidsProjects\ScienceQuest) as the Cursor workspace.
      # Returning only the parent root made expected files miss and skipped the real stack.
      return $fullRequested
    }
  }
  return $null
}

function Protect-Log([string]$text) {
  if (-not $text) { return $text }
  $text = [regex]::Replace($text, '(?i)(CURSOR_API_KEY|api[_-]?key|authorization|bearer)\s*[:=]\s*\S+', '$1=[redacted]')
  $text = [regex]::Replace($text, 'sk-[A-Za-z0-9_-]{8,}', '[redacted]')
  $text = [regex]::Replace($text, 'cursor_[A-Za-z0-9_-]{8,}', '[redacted]')
  $text = [regex]::Replace($text, '-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----', '[redacted-private-key]')
  return $text
}

function Stop-ProcessTree([int]$ProcessId) {
  if ($ProcessId -le 0) { return }
  try { & taskkill.exe /PID $ProcessId /T /F | Out-Null } catch {}
  try { Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue } catch {}
}

function Test-RelPathInside([string]$repo, [string]$rel) {
  if (-not $rel) { return $false }
  if ($rel -match '\.\.' -or $rel -match '^[a-zA-Z]:\\' -or $rel.StartsWith('/') -or $rel.StartsWith('\\')) { return $false }
  $full = [System.IO.Path]::GetFullPath((Join-Path $repo $rel))
  $root = $repo.TrimEnd('\') + '\'
  return $full.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)
}

$jobId = [string]$Job.job_id
$prompt = [string]$Job.prompt
$requestedRepo = [string]$Job.repo
if (-not $requestedRepo) { $requestedRepo = [string]$Job.workspace_path }
$write = [bool]($Job.write)
$timeoutSec = [int]$policy.default_timeout_sec
if ($Job.timeout_sec) { $timeoutSec = [int]$Job.timeout_sec }
$maxTimeout = [int]$policy.max_timeout_sec
if ($timeoutSec -lt 15) { $timeoutSec = 15 }
if ($timeoutSec -gt $maxTimeout) { $timeoutSec = $maxTimeout }
$expected = @()
if ($Job.expected_paths) { $expected = @($Job.expected_paths) }

function Get-CursorUsage([string]$text) {
  if (-not $text) { return $null }
  try {
    $obj = $text.Trim() | ConvertFrom-Json
    if ($obj.usage) { return $obj.usage }
  } catch {
    return $null
  }
  return $null
}

function New-CursorResult($status, $reason, $artifact, $extra) {
  $obj = [ordered]@{
    job_id = $jobId
    action = 'cursor_call'
    status = $status
    reason = $reason
    artifact = $artifact
    host = $env:COMPUTERNAME
    worker = 'neewa-windows-worker'
    selected_worker = 'cursor-agent-cli'
    git_writer = 'Cursor'
    public_listener = $false
    unrestricted_shell = $false
    write = $write
  }
  if ($extra) { foreach ($k in $extra.Keys) { $obj[$k] = $extra[$k] } }
  return [pscustomobject]$obj
}

$artifact = Join-Path $JobsDir "$jobId-cursor-call.json"
$logPath = Join-Path $JobsDir "$jobId-cursor-call.log"
$argsPath = Join-Path $JobsDir "$jobId-cursor-call.args.txt"
$pidPath = Join-Path $JobsDir "$jobId-cursor-call.pid"

if (-not $prompt) {
  $r = New-CursorResult 'FAILED' 'cursor_call requires prompt' $null $null
  [System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
  $r.artifact = $artifact
  return $r
}
if (Test-BlockedIntent $prompt) {
  $r = New-CursorResult 'BLOCKED' 'prompt requests a sensitive or consequential A2/A3 action; owner gate required' $null @{
    failure_class = 'POLICY'
  }
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

$leaf = [System.IO.Path]::GetFileName($requestedRepo.TrimEnd('\', '/'))
foreach ($denied in @($policy.denied_name_equals)) {
  if ($leaf -and $leaf.Equals($denied, [System.StringComparison]::OrdinalIgnoreCase)) {
    $r = New-CursorResult 'BLOCKED' 'repo is on the denied list' $null @{ failure_class = 'DENIED_REPO' }
    [System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
    $r.artifact = $artifact
    return $r
  }
}

$repo = Resolve-ApprovedRepo $requestedRepo
if (-not $repo) {
  $r = New-CursorResult 'BLOCKED' 'repo is not on the approved personal cursor_call list' $null @{ failure_class = 'UNAPPROVED_PATH' }
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

foreach ($rel in $expected) {
  if (-not (Test-RelPathInside $repo ([string]$rel))) {
    $r = New-CursorResult 'BLOCKED' "expected path escapes the approved repository: $rel" $null @{ failure_class = 'PATH_ESCAPE' }
    [System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
    $r.artifact = $artifact
    return $r
  }
}

$cli = if ($DryRun) { 'DRY-RUN' } else { Get-AgentCli }
if (-not $cli) {
  $r = New-CursorResult 'BLOCKED' 'Cursor Agent CLI (agent --print) is not installed' $null @{
    ide_launcher_note = 'cursor.cmd is the IDE launcher and is not this interface'
    failure_class = 'CLI_MISSING'
  }
  [System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
  $r.artifact = $artifact
  return $r
}

$argList = @(
  '--print',
  '--output-format', 'json',
  '--trust',
  '--workspace', $repo
)
# Official --sandbox enabled is macOS/Linux only. Windows Agent CLI rejects it.
if ($env:OS -ne 'Windows_NT') {
  $argList += '--sandbox'
  $argList += 'enabled'
}
if ($write) {
  $argList += '--force'
} else {
  $argList += '--mode'
  $argList += 'ask'
}
$argList += $prompt
[System.IO.File]::WriteAllText($argsPath, (($argList | ForEach-Object { $_ }) -join "`n"), [System.Text.UTF8Encoding]::new($false))

$gitBefore = ''
$gitAvail = Test-Path -LiteralPath (Join-Path $repo '.git')
if ($gitAvail) {
  $gitBefore = (& git -C $repo status --porcelain 2>$null | Out-String)
}

$stdoutFile = Join-Path $JobsDir "$jobId-cursor-call.stdout.txt"
$stderrFile = Join-Path $JobsDir "$jobId-cursor-call.stderr.txt"
$started = Get-Date
if ($DryRun) {
  [System.IO.File]::WriteAllText($stdoutFile, '{"dry_run":true}', [System.Text.UTF8Encoding]::new($false))
  [System.IO.File]::WriteAllText($stderrFile, '', [System.Text.UTF8Encoding]::new($false))
  $exitCode = 0
  $exited = $true
  $proc = $null
} else {
  $filePath = $cli
  $startArgs = @($argList)
  if ($cli -match '(?i)agent\.cmd$') {
    $ps1 = Join-Path (Split-Path -Parent $cli) 'cursor-agent.ps1'
    if (Test-Path -LiteralPath $ps1) {
      $filePath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
      $startArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $ps1) + @($argList)
    }
  }
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $filePath
  $psi.WorkingDirectory = $repo
  $psi.UseShellExecute = $false
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.CreateNoWindow = $true
  $argListProp = $psi.GetType().GetProperty('ArgumentList')
  if ($argListProp) {
    foreach ($a in $startArgs) { [void]$psi.ArgumentList.Add([string]$a) }
  } else {
    $psi.Arguments = (($startArgs | ForEach-Object {
      $s = [string]$_
      if ($s -match '[\s"]') { '"' + ($s -replace '"', '\"') + '"' } else { $s }
    }) -join ' ')
  }
  $proc = New-Object System.Diagnostics.Process
  $proc.StartInfo = $psi
  [void]$proc.Start()
  [System.IO.File]::WriteAllText($pidPath, [string]$proc.Id, [System.Text.UTF8Encoding]::new($false))
  $exited = $proc.WaitForExit($timeoutSec * 1000)
  if ($exited) {
    $stdoutText = $proc.StandardOutput.ReadToEnd()
    $stderrText = $proc.StandardError.ReadToEnd()
    [System.IO.File]::WriteAllText($stdoutFile, $stdoutText, [System.Text.UTF8Encoding]::new($false))
    [System.IO.File]::WriteAllText($stderrFile, $stderrText, [System.Text.UTF8Encoding]::new($false))
  }
}
if (-not $exited) {
  Stop-ProcessTree -ProcessId $proc.Id
  $r = New-CursorResult 'CANCELLED' "cursor_call timed out after ${timeoutSec}s and was cancelled" $null @{
    cli = $cli
    repo = $repo
    log = $logPath
    cancelled = $true
    failure_class = 'TIMEOUT'
  }
  [System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
  $r.artifact = $artifact
  return $r
}
if (-not $DryRun) {
  $exitCode = $proc.ExitCode
}
$duration = [int]((Get-Date) - $started).TotalSeconds
$stdout = if (Test-Path $stdoutFile) { Get-Content -Raw -LiteralPath $stdoutFile } else { '' }
$stderr = if (Test-Path $stderrFile) { Get-Content -Raw -LiteralPath $stderrFile } else { '' }
$stdout = Protect-Log $stdout
$stderr = Protect-Log $stderr
$usage = Get-CursorUsage $stdout
$combined = @("exit=$exitCode duration_sec=$duration cli=$cli repo=$repo write=$write", $stdout, $stderr) -join "`n"
[System.IO.File]::WriteAllText($logPath, $combined, [System.Text.UTF8Encoding]::new($false))

$authFail = ($stderr + $stdout) -match '(?i)(authentication required|not logged in|login required|unauthorized|unauthenticated|please run ''agent login''|AUTH_REQUIRED)'
if ($exitCode -ne 0 -or $authFail) {
  $status = if ($authFail) { 'BLOCKED' } else { 'FAILED' }
  $reason = if ($authFail) { 'Cursor Agent CLI is not authenticated' } else { "Cursor Agent CLI exited $exitCode" }
  $failureClass = if ($authFail) { 'AUTH_REQUIRED' } else { 'CLI_EXIT' }
  $r = New-CursorResult $status $reason $artifact @{
    cli = $cli
    repo = $repo
    exit_code = $exitCode
    duration_sec = $duration
    log = $logPath
    failure_class = $failureClass
    stdout_tail = if ($stdout) { $stdout.Substring([Math]::Max(0, $stdout.Length - 2000)) } else { '' }
    usage = $usage
  }
  [System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
  $r.artifact = $artifact
  return $r
}

if (-not $write -and $gitAvail) {
  $gitAfter = (& git -C $repo status --porcelain 2>$null | Out-String)
  if ($gitAfter -ne $gitBefore) {
    $r = New-CursorResult 'FAILED' 'read-only cursor_call modified the worktree' $artifact @{
      cli = $cli
      repo = $repo
      failure_class = 'READONLY_VIOLATION'
    }
    [System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
    $r.artifact = $artifact
    return $r
  }
}

$missing = @()
$created = @()
foreach ($rel in $expected) {
  $full = [System.IO.Path]::GetFullPath((Join-Path $repo ([string]$rel)))
  if (Test-Path -LiteralPath $full) { $created += $full } else { $missing += [string]$rel }
}
if ($write -and $expected.Count -gt 0 -and $missing.Count -gt 0) {
  $r = New-CursorResult 'FAILED' ("validation failed; missing expected files: " + ($missing -join ', ')) $artifact @{
    cli = $cli
    repo = $repo
    exit_code = $exitCode
    duration_sec = $duration
    log = $logPath
    failure_class = 'VALIDATION'
    missing_paths = $missing
    artifact_paths = $created
  }
  [System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
  $r.artifact = $artifact
  return $r
}

$r = New-CursorResult 'COMPLETED' $null $artifact @{
  cli = $cli
  repo = $repo
  exit_code = $exitCode
  duration_sec = $duration
  log = $logPath
  artifact_paths = $created
  stdout_tail = if ($stdout) { $stdout.Substring([Math]::Max(0, $stdout.Length - 4000)) } else { '' }
  usage = $usage
}
[System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
$r.artifact = $artifact
return $r
