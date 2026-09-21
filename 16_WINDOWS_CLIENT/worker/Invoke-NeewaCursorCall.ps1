# Governed Cursor Agent CLI invocation. No raw shell. Personal roots except deny-list.
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
. (Join-Path $here 'NeewaPersonalWorkspace.ps1')
# Keep approved child folders (e.g. KidsProjects\ScienceQuest) as the Cursor workspace.

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

function Get-OperativePrompt([string]$text) {
  if (-not $text) { return '' }
  $work = [regex]::Replace($text, '"[^"]*"', ' ')
  $parts = [regex]::Split($work, '(?<=[.!?;])\s+|\s+(?i:but|however)\s+')
  $keep = New-Object System.Collections.Generic.List[string]
  foreach ($p in $parts) {
    $t = [regex]::Replace(([string]$p).Trim(), '^[\s>*\-•]+', '')
    if (-not $t) { continue }
    if ($t -match '^(?i)(?:please\s+)?(?:do not|does not|don''t|dont|must not|cannot|can''t|never|without|no|not to|avoid|refrain from|not for)\b') {
      continue
    }
    $keep.Add($t)
  }
  return ($keep -join ' ')
}

function Get-NeewaAuthorizationFallback([string]$text) {
  $operative = Get-OperativePrompt $text
  $requested = @()
  $prohibited = @()
  $families = [ordered]@{
    publish = 'publish|publication'
    deploy = 'deploy|production rollout|rollout to production|roll this out'
    purchase = 'purchase|purchases|purchasing|buy|buys|buying|subscribe'
    send_message = 'send email|external messages|email the client'
    destructive = 'drop database|format c:|rm -rf|delete everything|destructive actions'
    financial = 'live trade|place order|wire transfer|bank transfer|send money'
  }
  $lower = $operative.ToLowerInvariant()
  foreach ($name in $families.Keys) {
    if ($lower -match ('\b(?:' + $families[$name] + ')')) { $requested += $name }
  }
  $prohibitedText = [regex]::Replace($text, '"[^"]*"', ' ')
  $parts = [regex]::Split($prohibitedText, '(?<=[.!?;])\s+|\s+(?i:but|however)\s+')
  foreach ($p in $parts) {
    $t = [regex]::Replace(([string]$p).Trim(), '^[\s>*\-•]+', '')
    if ($t -match '^(?i)(?:please\s+)?(?:do not|does not|don''t|dont|must not|cannot|can''t|never|without|no|not to|avoid|refrain from|not for)\b') {
      $pt = $t.ToLowerInvariant()
      foreach ($name in $families.Keys) {
        if ($pt -match ('\b(?:' + $families[$name] + ')') -and $prohibited -notcontains $name) { $prohibited += $name }
      }
    }
  }
  $matched = $null
  foreach ($frag in @($policy.blocked_intent_substrings)) {
    if (-not $frag) { continue }
    $needle = $frag.ToLowerInvariant()
    $familyHit = $false
    foreach ($name in $families.Keys) {
      if ($needle -match ('\b(?:' + $families[$name] + ')')) {
        $familyHit = $true
        if ($requested -contains $name) { $matched = $frag; break }
      }
    }
    if ($matched) { break }
    if (-not $familyHit -and $lower.Contains($needle)) { $matched = $frag; break }
  }
  $needed = 'A1'
  if ($requested -contains 'financial' -or ($matched -and ($matched -match '(?i)live trade|place order|wire transfer|bank transfer|send money'))) { $needed = 'A3' }
  elseif ($matched -or $requested.Count -gt 0) { $needed = 'A2' }
  $allowed = $needed -in @('A0', 'A1')
  return [pscustomobject]@{
    allowed = $allowed
    needed = $needed
    reason = $(if ($allowed) { 'ALLOW' } elseif ($matched) { 'BLOCKED_INTENT' } else { ($needed + '_OWNER_GATE') })
    matched_rule = $matched
    requested_action = $(if ($requested.Count) { ($requested -join ',') } else { 'local_write' })
    requested_families = $requested
    prohibited_actions = $prohibited
    effective_approval = $needed
    detail = $matched
  }
}

function Find-NeewaPythonModule([string]$Name) {
  $candidates = @(
    (Join-Path $here $Name)
    (Join-Path $here (Join-Path '..\..\12_SCRIPTS' $Name))
  )
  foreach ($candidate in $candidates) {
    if (Test-Path -LiteralPath $candidate) { return (Resolve-Path -LiteralPath $candidate).Path }
  }
  return $null
}

function Get-NeewaPython {
  $py = Get-Command python -ErrorAction SilentlyContinue
  if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
  return $py
}

function Get-NeewaStructuredAuthorization($JobObject, $PromptAuth) {
  $mod = Find-NeewaPythonModule 'neewa_a2_receipt_auth.py'
  $py = Get-NeewaPython
  if (-not $py -or -not $mod) {
    return [pscustomobject]@{
      allowed = $false
      needed = $(if ($PromptAuth) { $PromptAuth.needed } else { 'A2' })
      reason = 'MISSING_SSH'
      receipt_backed = $true
      detail = 'a2 verifier unavailable'
    }
  }
  $tmpJob = Join-Path $env:TEMP ('neewa-a2-job-' + [guid]::NewGuid().ToString() + '.json')
  $tmpPrompt = Join-Path $env:TEMP ('neewa-a2-prompt-' + [guid]::NewGuid().ToString() + '.json')
  try {
    $jobJson = $JobObject | ConvertTo-Json -Depth 16 -Compress
    [System.IO.File]::WriteAllText($tmpJob, $jobJson, [System.Text.UTF8Encoding]::new($false))
    if ($PromptAuth) {
      [System.IO.File]::WriteAllText($tmpPrompt, ($PromptAuth | ConvertTo-Json -Depth 8 -Compress), [System.Text.UTF8Encoding]::new($false))
    }
    $cacheDir = $env:NEEWA_A2_AUTH_CACHE
    if (-not $cacheDir) {
      $cacheDir = Join-Path $env:LOCALAPPDATA 'NEENEEWA\authorizations'
    }
    $argList = @($mod, '--job-file', $tmpJob, '--cache-dir', $cacheDir)
    if ($PromptAuth) { $argList += @('--prompt-auth-file', $tmpPrompt) }
    $nativePref = $PSNativeCommandUseErrorActionPreference
    $PSNativeCommandUseErrorActionPreference = $false
    try {
      $out = & $py.Source @argList 2>$null | Out-String
    } finally {
      $PSNativeCommandUseErrorActionPreference = $nativePref
    }
    if ($out) {
      return ($out | ConvertFrom-Json)
    }
  } catch {
    return [pscustomobject]@{
      allowed = $false
      needed = 'A2'
      reason = 'MISSING_SSH'
      receipt_backed = $true
      detail = $_.Exception.Message
    }
  } finally {
    Remove-Item -LiteralPath $tmpJob -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tmpPrompt -Force -ErrorAction SilentlyContinue
  }
  return [pscustomobject]@{
    allowed = $false
    needed = 'A2'
    reason = 'MISSING_AUTHORIZATION'
    receipt_backed = $true
  }
}

function Get-NeewaAuthorization([string]$text) {
  $sem = Find-NeewaPythonModule 'neewa_action_semantics.py'
  $py = Get-NeewaPython
  if ($py -and $sem) {
    $tmpText = Join-Path $env:TEMP ('neewa-auth-' + [guid]::NewGuid().ToString() + '.txt')
    $tmpFrag = Join-Path $env:TEMP ('neewa-auth-frags-' + [guid]::NewGuid().ToString() + '.json')
    try {
      [System.IO.File]::WriteAllText($tmpText, $text, [System.Text.UTF8Encoding]::new($false))
      $fragJson = (@($policy.blocked_intent_substrings) | ConvertTo-Json -Compress)
      if ($fragJson -notmatch '^\s*\[') { $fragJson = '[' + $fragJson + ']' }
      [System.IO.File]::WriteAllText($tmpFrag, $fragJson, [System.Text.UTF8Encoding]::new($false))
      $writeFlag = @()
      if ($write) { $writeFlag = @('--write') }
      $out = & $py.Source $sem --authorize --text-file $tmpText --fragments-file $tmpFrag @writeFlag
      if ($LASTEXITCODE -eq 0 -and $out) {
        return ($out | ConvertFrom-Json)
      }
    } catch {
    } finally {
      Remove-Item -LiteralPath $tmpText -Force -ErrorAction SilentlyContinue
      Remove-Item -LiteralPath $tmpFrag -Force -ErrorAction SilentlyContinue
    }
  }
  return Get-NeewaAuthorizationFallback $text
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

function Test-MalformedExpectedPath([string]$rel) {
  # Reject catalog stack labels such as FastAPI/Next.js before invoking the agent.
  if (-not $rel) { return $true }
  $norm = $rel.Trim().Replace('\', '/').TrimStart('.')
  while ($norm.StartsWith('/')) { $norm = $norm.TrimStart('/') }
  $lower = $norm.ToLowerInvariant()
  $labels = @(
    'fastapi/next.js',
    'fastapi/next.js/postgresql',
    'next.js/postgresql',
    'fastapi',
    'next.js',
    'postgresql',
    'postgres',
    'typescript',
    'react'
  )
  if ($labels -contains $lower) { return $true }
  $leaf = [System.IO.Path]::GetFileName($norm)
  if ($leaf -and $labels -contains $leaf.ToLowerInvariant()) { return $true }
  foreach ($part in $norm.Split('/')) {
    if ($labels -contains $part.ToLowerInvariant()) { return $true }
  }
  return $false
}

$jobId = [string]$Job.job_id
$prompt = [string]$Job.prompt
$requestedRepo = [string]$Job.repo
if (-not $requestedRepo) { $requestedRepo = [string]$Job.workspace_path }
$write = [bool]($Job.write)
$timeoutSec = [int]$policy.default_timeout_sec
# timeout_sec=0 means unlimited (no elapsed-time kill). Do not treat 0 as missing.
if ($null -ne $Job.PSObject.Properties['timeout_sec'] -and $null -ne $Job.timeout_sec -and "$($Job.timeout_sec)" -ne '') {
  $timeoutSec = [int]$Job.timeout_sec
}
$maxTimeout = [int]$policy.max_timeout_sec
$unlimitedTimeout = ($timeoutSec -eq 0)
if (-not $unlimitedTimeout) {
  if ($timeoutSec -lt 15) { $timeoutSec = 15 }
  if ($timeoutSec -gt $maxTimeout) { $timeoutSec = $maxTimeout }
}
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
  if ($authorization) { $obj['authorization'] = $authorization }
  if ($extra) { foreach ($k in $extra.Keys) { $obj[$k] = $extra[$k] } }
  if ($phase) { $obj['execution_phase'] = $phase }
  if ($bootstrap) {
    $obj['project_lifecycle'] = $lifecycle
    $obj['bootstrap'] = $bootstrap
    if (-not $obj.Contains('preflight')) { $obj['preflight'] = $bootstrap }
    if (-not $obj.Contains('repo') -and $repo) { $obj['repo'] = $repo }
  }
  return [pscustomobject]$obj
}

$authorization = $null
$bootstrap = $null
$lifecycle = $null
$phase = $null
$repo = $null
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
$authorization = Get-NeewaAuthorization $prompt
$hasReceipt = $false
if ($Job.PSObject.Properties['authorization'] -and $null -ne $Job.authorization) { $hasReceipt = $true }
if ($hasReceipt -or [string]$Job.approval -in @('A2', 'A3')) {
  $authorization = Get-NeewaStructuredAuthorization $Job $authorization
}
if (-not [bool]$authorization.allowed) {
  $authReason = [string]$authorization.reason
  $message = 'prompt requests a sensitive or consequential A2/A3 action; owner gate required'
  if ($hasReceipt -and $authReason) {
    $message = "A2 receipt authorization failed: $authReason"
  }
  $r = New-CursorResult 'BLOCKED' $message $null @{
    failure_class = 'POLICY'
    authorization = $authorization
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
  $r = New-CursorResult 'BLOCKED' 'repo is outside the personal workspace roots or is explicitly excluded' $null @{ failure_class = 'UNAPPROVED_PATH' }
  [System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
  $r.artifact = $artifact
  return $r
}
$lifecycle = [string]$Job.project_lifecycle
if (-not $lifecycle) { $lifecycle = 'modify_existing' }
$phase = [string]$Job.execution_phase
if (-not $phase) { $phase = 'implementation' }
$workspaceRoot = [string]$Job.workspace_root
$bootstrapComplete = $false
if ($Job.PSObject.Properties['bootstrap_complete'] -and $Job.bootstrap_complete) { $bootstrapComplete = [bool]$Job.bootstrap_complete }
$implCompleted = $false
if ($Job.PSObject.Properties['implementation_completed'] -and $Job.implementation_completed) { $implCompleted = [bool]$Job.implementation_completed }
$implRepo = [string]$Job.implementation_repo
$bootstrap = Invoke-ProjectBootstrap -Repo $repo -Lifecycle $lifecycle -WorkspaceRoot $workspaceRoot -ExecutionPhase $phase -BootstrapComplete $bootstrapComplete -ExpectedPaths $expected -ImplementationRepo $implRepo -ImplementationCompleted $implCompleted
function Add-Bootstrap($obj) {
  $ht = [ordered]@{}
  if ($obj -is [hashtable]) { foreach ($k in $obj.Keys) { $ht[$k] = $obj[$k] } }
  else { foreach ($p in $obj.PSObject.Properties) { $ht[$p.Name] = $p.Value } }
  $ht['project_lifecycle'] = $lifecycle
  $ht['execution_phase'] = $phase
  $ht['bootstrap'] = $bootstrap
  $ht['preflight'] = $bootstrap
  $ht['repo'] = $repo
  return $ht
}
if (-not [bool]$bootstrap.identity_ok) {
  $status = if ($bootstrap.failure_class -in @('UNAPPROVED_PATH','DENIED_REPO','PATH_TRAVERSAL')) { 'BLOCKED' } else { 'FAILED' }
  $r = New-CursorResult $status $bootstrap.reason $null (Add-Bootstrap @{
    failure_class = $bootstrap.failure_class
  })
  [System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
  $r.artifact = $artifact
  return $r
}
if (-not (Test-Path -LiteralPath $repo)) {
  $r = New-CursorResult 'FAILED' "approved repo path is missing: $repo" $null (Add-Bootstrap @{ failure_class = 'MISSING_REPO' })
  [System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
  $r.artifact = $artifact
  return $r
}

foreach ($rel in $expected) {
  if (Test-MalformedExpectedPath ([string]$rel)) {
    $r = New-CursorResult 'BLOCKED' "malformed expected path (stack label or non-file): $rel" $null @{ failure_class = 'MALFORMED_EXPECTED_PATH' }
    [System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
    $r.artifact = $artifact
    return $r
  }
  if (-not (Test-RelPathInside $repo ([string]$rel))) {
    $r = New-CursorResult 'BLOCKED' "expected path escapes the approved repository: $rel" $null @{ failure_class = 'PATH_ESCAPE' }
    [System.IO.File]::WriteAllText($artifact, ($r | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
    $r.artifact = $artifact
    return $r
  }
}

if ($phase -eq 'independent_validation') {
  $write = $false
  $testCmd = [string]$Job.test_command
  if (-not $testCmd) { $testCmd = 'python -m unittest' }
  if ($testCmd -match '^python(?:3)?\s+-m\s+unittest\b') {
    $tests = Invoke-ProductUnittest -Repo $repo -TestCommand $testCmd
    $stdoutCombined = ([string]$tests.stdout) + "`n" + ([string]$tests.stderr)
    $jsonPayload = @{
      exit_code = $tests.exit_code
      passed = [bool]$tests.passed
      stdout = [string]$tests.stdout
      stderr = [string]$tests.stderr
      command = $tests.command
      cwd = $tests.cwd
    }
    $stdoutTail = $stdoutCombined
    if ($stdoutTail.Length -gt 3500) { $stdoutTail = $stdoutTail.Substring($stdoutTail.Length - 3500) }
    $stdoutTail = $stdoutTail + "`nTEST_JSON:" + ($jsonPayload | ConvertTo-Json -Compress)
    $status = if ([bool]$tests.passed) { 'COMPLETED' } else { 'FAILED' }
    $reason = $null
    $failureClass = $null
    if (-not [bool]$tests.passed) {
      $reason = if ($tests.failure_class) { [string]$tests.stderr } else { "independent product tests failed with exit $($tests.exit_code)" }
      $failureClass = $(if ($tests.failure_class) { $tests.failure_class } else { 'INDEPENDENT_TEST_FAIL' })
    }
    $r = New-CursorResult $status $reason $null (Add-Bootstrap @{
      failure_class = $failureClass
      selected_worker = 'neewa-windows-worker'
      cli = $tests.command
      repo = $repo
      exit_code = $tests.exit_code
      write = $false
      cursor_started = $false
      independent_test = $jsonPayload
      test_results = $jsonPayload
      stdout_tail = $stdoutTail
    })
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
  $heartbeatPath = Join-Path $JobsDir "$jobId-cursor-call.heartbeat.json"
  $publish = Join-Path $here 'Publish-NeewaJobProgress.ps1'
  $workerPid = [int]$PID
  $cmdLine = $proc.StartInfo.FileName + ' ' + (($startArgs | ForEach-Object { $_ }) -join ' ')
  function Write-ExecutionHeartbeat {
    $hb = [ordered]@{
      at = (Get-Date).ToUniversalTime().ToString('o')
      pid = $proc.Id
      worker_pid = $workerPid
      job_id = $jobId
      current_operation = 'cursor_call'
    }
    [System.IO.File]::WriteAllText($heartbeatPath, ($hb | ConvertTo-Json -Compress), [System.Text.UTF8Encoding]::new($false))
    if (Test-Path -LiteralPath $publish) {
      try {
        & $publish -JobId $jobId -State 'RUNNING' -WorkerPid $workerPid -ChildPid $proc.Id -CommandLine $cmdLine | Out-Null
      } catch { }
    }
  }
  Write-ExecutionHeartbeat
  $exited = $false
  while (-not $proc.HasExited) {
    $elapsed = ((Get-Date) - $started).TotalSeconds
    if (-not $unlimitedTimeout -and $elapsed -ge $timeoutSec) { break }
    Write-ExecutionHeartbeat
    [void]$proc.WaitForExit(15000)
  }
  $exited = $proc.HasExited
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
    timeout_sec = $timeoutSec
    unlimited_timeout = $false
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
if ($write -and $expected.Count -eq 0 -and $gitAvail) {
  $changed = @()
  $changed += @(& git -C $repo diff --name-only 2>$null)
  $changed += @(& git -C $repo diff --name-only --cached 2>$null)
  $changed += @(& git -C $repo ls-files --others --exclude-standard 2>$null)
  foreach ($rel in $changed) {
    if (-not $rel) { continue }
    if (Test-MalformedExpectedPath ([string]$rel)) { continue }
    if ($rel -match '(?i)AarohanSecrets|Keys & secrets') { continue }
    if (-not (Test-RelPathInside $repo ([string]$rel))) { continue }
    $full = [System.IO.Path]::GetFullPath((Join-Path $repo ([string]$rel)))
    if ((Test-Path -LiteralPath $full) -and ($created -notcontains $full)) { $created += $full }
  }
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
