# Allowlisted product test runner. Fixed argv only. Writable scratch for TEMP.
# Dot-source safe. A collected count of zero is not a pass.
# No param block: a dotted param() would clear the caller's variables.

. (Join-Path $PSScriptRoot 'Invoke-NeewaTempProbe.ps1')

function Test-NeewaSafeToken {
  param([string]$Token)
  if (-not $Token) { return $false }
  if ($Token -match '[\r\n;&|`$<>]') { return $false }
  if ($Token -match '\.\.') { return $false }
  return $true
}

function Resolve-NeewaInsideRepo {
  param(
    [Parameter(Mandatory)][string]$Repo,
    [Parameter(Mandatory)][string]$Relative
  )
  if (-not (Test-NeewaSafeToken $Relative)) { return $null }
  if ([System.IO.Path]::IsPathRooted($Relative)) { return $null }
  $repoFull = [System.IO.Path]::GetFullPath($Repo)
  $full = [System.IO.Path]::GetFullPath((Join-Path $repoFull $Relative))
  $prefix = $repoFull.TrimEnd('\') + '\'
  if (-not $full.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) { return $null }
  return $full
}

function ConvertTo-AllowlistedTestArgs {
  param([string[]]$Tokens)
  $clean = @($Tokens | ForEach-Object { [string]$_ })
  if ($clean.Count -lt 3) { return $null }
  if ($clean[0] -ne '-m') { return $null }
  if ($clean[1] -notin @('pytest', 'unittest')) { return $null }
  foreach ($token in $clean) {
    if (-not (Test-NeewaSafeToken $token)) { return $null }
  }
  if ($clean[1] -eq 'pytest') {
    $path = $clean[2]
    if ($path -notmatch '^tests/[A-Za-z0-9_./-]+\.py$') { return $null }
    foreach ($extra in @($clean | Select-Object -Skip 3)) {
      if ($extra -notin @('-q', '--tb=line', '--tb=short')) { return $null }
    }
    return $clean
  }
  $rest = @($clean | Select-Object -Skip 2) -join ' '
  if ($rest -eq '' -or $rest -eq 'discover -s tests -p test_*.py') { return $clean }
  return $null
}

function Get-NeewaPytestOutcome {
  param([string]$Stdout, [string]$Stderr, [int]$ExitCode)
  $blob = "{0}`n{1}" -f $Stdout, $Stderr
  if ($blob -match 'No usable temporary directory') {
    return [pscustomobject]@{ collected = 0; passed = $false; failure_class = 'NO_USABLE_TEMP' }
  }
  $collected = 0
  $lines = $blob -split "`n"
  $summary = $null
  foreach ($line in $lines) {
    if ($line -match '\d+\s+(passed|failed|error|errors)\b') { $summary = $line }
  }
  if ($summary) {
    foreach ($match in [regex]::Matches($summary, '(\d+)\s+(passed|failed|error|errors)\b')) {
      $collected += [int]$match.Groups[1].Value
    }
  }
  if ($blob -match 'collected\s+(\d+)\s+item') {
    if ([int]$Matches[1] -eq 0) { $collected = 0 }
  }
  if ($collected -le 0) {
    return [pscustomobject]@{ collected = 0; passed = $false; failure_class = 'ZERO_COLLECTED' }
  }
  $ok = ($ExitCode -eq 0)
  return [pscustomobject]@{
    collected = $collected
    passed = $ok
    failure_class = $(if ($ok) { $null } else { 'INDEPENDENT_TEST_FAIL' })
  }
}

function Get-NeewaRepoIdentity {
  param([string]$Repo)
  $head = $null
  $diffHash = $null
  $git = Get-Command git -ErrorAction SilentlyContinue
  if (-not $git) { return [pscustomobject]@{ head = $null; diff_sha256 = $null } }
  $native = $PSNativeCommandUseErrorActionPreference
  $PSNativeCommandUseErrorActionPreference = $false
  try {
    $head = (& $git.Source -C $Repo rev-parse HEAD 2>$null | Select-Object -First 1)
    $diff = & $git.Source -C $Repo diff 2>$null | Out-String
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $bytes = [System.Text.Encoding]::UTF8.GetBytes([string]$diff)
    $diffHash = ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
  } finally {
    $PSNativeCommandUseErrorActionPreference = $native
  }
  return [pscustomobject]@{ head = $head; diff_sha256 = $diffHash }
}

function Invoke-AllowlistedProductTest {
  param(
    [Parameter(Mandatory)][string]$Repo,
    [string]$PythonRelative = 'backend\.venv\Scripts\python.exe',
    [string]$CwdRelative = 'backend',
    [string[]]$ArgumentList,
    [string]$TestCommand
  )
  $result = [ordered]@{
    command = $null
    argv = @()
    cwd = $null
    python = $null
    exit_code = $null
    passed = $false
    collected = 0
    stdout = ''
    stderr = ''
    failure_class = $null
    scratch = $null
    candidate_head = $null
    candidate_diff_sha256 = $null
  }
  if (-not $PythonRelative) { $PythonRelative = 'backend\.venv\Scripts\python.exe' }
  if (-not $CwdRelative) { $CwdRelative = 'backend' }
  $identity = Get-NeewaRepoIdentity -Repo $Repo
  $result.candidate_head = $identity.head
  $result.candidate_diff_sha256 = $identity.diff_sha256
  $args = @($ArgumentList)
  if (-not $args -and $TestCommand) {
    $args = @($TestCommand -split '\s+' | Where-Object { $_ })
    if ($args.Count -ge 1 -and $args[0] -match 'python(\.exe)?$') {
      $PythonRelative = $args[0]
      $args = @($args | Select-Object -Skip 1)
    }
  }
  $allow = ConvertTo-AllowlistedTestArgs -Tokens $ArgumentList
  if (-not $allow) {
    $result.stderr = 'test argv is not allowlisted'
    $result.failure_class = 'UNAPPROVED_TEST_COMMAND'
    return [pscustomobject]$result
  }
  $python = Resolve-NeewaInsideRepo -Repo $Repo -Relative $PythonRelative
  $cwd = Resolve-NeewaInsideRepo -Repo $Repo -Relative $CwdRelative
  if (-not $python -or -not (Test-Path -LiteralPath $python)) {
    $venv = Resolve-NeewaInsideRepo -Repo $Repo -Relative 'backend\.venv\Scripts\python.exe'
    if ($venv -and (Test-Path -LiteralPath $venv)) { $python = $venv }
  }
  if (-not $python -or -not (Test-Path -LiteralPath $python)) {
    $result.stderr = 'allowlisted python interpreter is missing'
    $result.failure_class = 'PYTHON_MISSING'
    return [pscustomobject]$result
  }
  if (-not $cwd -or -not (Test-Path -LiteralPath $cwd)) {
    $result.stderr = 'allowlisted working directory is missing'
    $result.failure_class = 'UNAPPROVED_TEST_COMMAND'
    return [pscustomobject]$result
  }
  $probe = Invoke-NeewaTempProbeReport
  if ($probe.failure_class) {
    $result.stderr = 'No usable temporary directory'
    $result.failure_class = 'NO_USABLE_TEMP'
    $result.scratch = $probe.scratch
    return [pscustomobject]$result
  }
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $python
  $psi.WorkingDirectory = $cwd
  $psi.UseShellExecute = $false
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.CreateNoWindow = $true
  if ($psi.ArgumentList) {
    foreach ($token in $allow) { [void]$psi.ArgumentList.Add($token) }
  } else {
    $psi.Arguments = ($allow -join ' ')
  }
  $chosen = $probe.usable_temp
  foreach ($row in @($probe.candidates)) {
    if ($row.path -eq $probe.scratch -and $row.file_ok -and $row.directory_ok) { $chosen = $probe.scratch }
  }
  $scratch = Set-NeewaChildTemp -StartInfo $psi -Scratch $chosen
  $proc = New-Object System.Diagnostics.Process
  $proc.StartInfo = $psi
  [void]$proc.Start()
  $stdout = $proc.StandardOutput.ReadToEnd()
  $stderr = $proc.StandardError.ReadToEnd()
  if (-not $proc.WaitForExit(900000)) {
    try { $proc.Kill() } catch { }
    $result.failure_class = 'CHILD_TIMEOUT'
    $result.stderr = 'independent test exceeded 900 seconds'
    return [pscustomobject]$result
  }
  $outcome = Get-NeewaPytestOutcome -Stdout $stdout -Stderr $stderr -ExitCode ([int]$proc.ExitCode)
  $result.command = (@($python) + $allow) -join ' '
  $result.argv = @($allow)
  $result.cwd = $cwd
  $result.python = $python
  $result.exit_code = [int]$proc.ExitCode
  $result.stdout = [string]$stdout
  $result.stderr = [string]$stderr
  $result.collected = $outcome.collected
  $result.passed = [bool]$outcome.passed
  $result.failure_class = $outcome.failure_class
  $result.scratch = $scratch
  return [pscustomobject]$result
}

if ($MyInvocation.InvocationName -ne '.') {
$ErrorActionPreference = 'Stop'
$JobFile = $null
$OutDir = $null
for ($i = 0; $i -lt $args.Count; $i++) {
  if ($args[$i] -eq '-JobFile') { $JobFile = [string]$args[$i + 1] }
  if ($args[$i] -eq '-OutDir') { $OutDir = [string]$args[$i + 1] }
}
if ($JobFile) {
$job = Get-Content -Raw -LiteralPath $JobFile | ConvertFrom-Json
if (-not $OutDir) { $OutDir = Split-Path -Parent $JobFile }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$repo = [string]$job.repo
if (-not $repo) { $repo = [string]$job.workspace }
$argList = @()
if ($job.PSObject.Properties['args'] -and $job.args) { $argList = @($job.args) }
$ran = Invoke-AllowlistedProductTest -Repo $repo -PythonRelative ([string]$job.python) -CwdRelative ([string]$(if ($job.cwd) { $job.cwd } else { 'backend' })) -ArgumentList $argList -TestCommand ([string]$job.test_command)
$artifact = Join-Path $OutDir ("{0}-independent-test.json" -f $job.job_id)
$status = if ($ran.passed) { 'COMPLETED' } else { 'FAILED' }
$reason = if ($ran.passed) { $null } else { $ran.failure_class }
$payload = [ordered]@{
  job_id = $job.job_id
  action = 'independent_test'
  status = $status
  reason = $reason
  failure_class = $ran.failure_class
  command = $ran.command
  argv = @($ran.argv)
  cwd = $ran.cwd
  python = $ran.python
  exit_code = $ran.exit_code
  collected = $ran.collected
  passed = $ran.passed
  scratch = $ran.scratch
  candidate_head = $ran.candidate_head
  candidate_diff_sha256 = $ran.candidate_diff_sha256
  stdout_tail = $(if ($ran.stdout -and $ran.stdout.Length -gt 2000) { $ran.stdout.Substring($ran.stdout.Length - 2000) } else { [string]$ran.stdout })
  stderr_tail = $(if ($ran.stderr -and $ran.stderr.Length -gt 2000) { $ran.stderr.Substring($ran.stderr.Length - 2000) } else { [string]$ran.stderr })
}
$payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $artifact -Encoding utf8
[pscustomobject]@{
  job_id = $job.job_id
  status = $status
  reason = $reason
  artifact = $artifact
  failure_class = $ran.failure_class
}
}
}
