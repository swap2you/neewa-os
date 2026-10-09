# Allowlisted product test runner. Fixed argv only. Writable scratch for TEMP.
# Dot-source safe. A collected count of zero is not a pass.
# No param block: a dotted param() would clear the caller's variables.

. (Join-Path $PSScriptRoot 'Invoke-NeewaTempProbe.ps1')
. (Join-Path $PSScriptRoot 'Invoke-NeewaDrainedProcess.ps1')

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
  $clean = @($Tokens | ForEach-Object { [string]$_ } | Where-Object { $_ })
  if ($clean.Count -lt 2) { return $null }
  if ($clean[0] -ne '-m') { return $null }
  if ($clean[1] -notin @('pytest', 'unittest')) { return $null }
  foreach ($token in $clean) {
    if (-not (Test-NeewaSafeToken $token)) { return $null }
  }
  if ($clean[1] -eq 'pytest') {
    if ($clean.Count -lt 3) { return $null }
    $path = $clean[2]
    if ($path -notmatch '^(tests/)?[A-Za-z0-9_./-]+\.py$') { return $null }
    foreach ($extra in @($clean | Select-Object -Skip 3)) {
      if ($extra -notin @('-q', '--tb=line', '--tb=short')) { return $null }
    }
    return $clean
  }
  if ($clean.Count -eq 2) { return $clean }
  $rest = @($clean | Select-Object -Skip 2)
  $joined = $rest -join ' '
  if ($joined -eq 'discover -s tests -p test_*.py') { return $clean }
  if ($rest.Count -eq 1 -and $rest[0] -match '^[A-Za-z0-9_.]+$') { return $clean }
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
  if ($blob -match '(?m)^(ERROR|ImportError|ModuleNotFoundError)\b' -and -not $summary) {
    return [pscustomobject]@{ collected = 0; passed = $false; failure_class = 'PRECOLLECTION_FAIL' }
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

function Get-NeewaUnittestOutcome {
  param([string]$Stdout, [string]$Stderr, [int]$ExitCode)
  $blob = "{0}`n{1}" -f $Stdout, $Stderr
  if ($blob -match 'No usable temporary directory') {
    return [pscustomobject]@{ collected = 0; passed = $false; failure_class = 'NO_USABLE_TEMP' }
  }
  $collected = 0
  if ($blob -match 'Ran\s+(\d+)\s+tests?') { $collected = [int]$Matches[1] }
  if ($blob -match '(?m)^(ERROR|ImportError|ModuleNotFoundError)\b' -and $collected -le 0) {
    return [pscustomobject]@{ collected = 0; passed = $false; failure_class = 'PRECOLLECTION_FAIL' }
  }
  if ($collected -le 0) {
    return [pscustomobject]@{ collected = 0; passed = $false; failure_class = 'ZERO_COLLECTED' }
  }
  $ok = ($ExitCode -eq 0) -and ($blob -match '(?m)^OK\s*$') -and ($blob -notmatch 'FAILED \(')
  return [pscustomobject]@{
    collected = $collected
    passed = [bool]$ok
    failure_class = $(if ($ok) { $null } else { 'INDEPENDENT_TEST_FAIL' })
  }
}

function Get-NeewaRepoIdentity {
  param([string]$Repo)
  $git = Get-Command git -ErrorAction SilentlyContinue
  if (-not $git) { return [pscustomobject]@{ head = $null; diff_sha256 = $null; worktree_sha256 = $null } }
  try {
    $head = (Invoke-NeewaGitRead -Git $git.Source -Repo $Repo -Arguments 'rev-parse HEAD').Trim()
    # Preserve Git's exact bytes/newlines, and include staged plus unstaged changes.
    [byte[]]$bytes = Invoke-NeewaGitRead -Git $git.Source -Repo $Repo -Arguments 'diff --binary --no-ext-diff --no-textconv HEAD --' -AsBytes
    $status = Invoke-NeewaGitRead -Git $git.Source -Repo $Repo -Arguments 'status --porcelain=v1 --untracked-files=all'
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $diffHash = ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
    $untracked = Invoke-NeewaGitRead -Git $git.Source -Repo $Repo -Arguments 'ls-files -z --others --exclude-standard'
    $parts = @($diffHash, $status)
    foreach ($relative in @($untracked -split "`0" | Where-Object { $_ })) {
      $file = Join-Path $Repo $relative
      if ((Get-Item -LiteralPath $file -Force).Attributes -band [System.IO.FileAttributes]::ReparsePoint) { throw 'untracked reparse point cannot establish candidate identity' }
      $parts += $relative + "`t" + (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    $worktreeHash = ([System.BitConverter]::ToString($sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes(($parts -join "`n"))))).Replace('-', '').ToLowerInvariant()
    $sha.Dispose()
    return [pscustomobject]@{ head = $head; diff_sha256 = $diffHash; worktree_sha256 = $worktreeHash }
  } catch {
    return [pscustomobject]@{ head = $null; diff_sha256 = $null; worktree_sha256 = $null }
  }
}

function Invoke-NeewaGitRead {
  param([string]$Git, [string]$Repo, [string]$Arguments, [switch]$AsBytes)
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $Git
  $psi.Arguments = '-C "' + $Repo.Replace('"', '\"') + '" ' + $Arguments
  $psi.UseShellExecute = $false
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.StandardOutputEncoding = [System.Text.UTF8Encoding]::new($false)
  $psi.StandardErrorEncoding = [System.Text.UTF8Encoding]::new($false)
  $ran = Invoke-NeewaDrainedProcess -StartInfo $psi -TimeoutMs 20000 -MaxChars 16777216 -BinaryOutput:$AsBytes
  $length = if ($AsBytes) { $ran.StdoutBytes.Length } else { $ran.Stdout.Length }
  if ($ran.TimedOut -or $ran.ExitCode -ne 0 -or $length -ge 16777216) { throw 'Git identity command failed or exceeded its limit' }
  if ($AsBytes) { return ,([byte[]]$ran.StdoutBytes) }
  return [string]$ran.Stdout
}

function Get-NeewaWorkspaceEvidenceDir {
  param([string]$Repo, [string]$JobId)
  if ($JobId -notmatch '^[A-Za-z0-9_-]+$') { throw 'invalid evidence job id' }
  $git = (Get-Command git -ErrorAction Stop).Source
  $exclude = (Invoke-NeewaGitRead -Git $git -Repo $Repo -Arguments 'rev-parse --git-path info/exclude').Trim()
  if (-not [System.IO.Path]::IsPathRooted($exclude)) { $exclude = Join-Path $Repo $exclude }
  $old = if (Test-Path -LiteralPath $exclude) { [System.IO.File]::ReadAllText($exclude) } else { '' }
  if (($old -split "`n" | ForEach-Object { $_.Trim() }) -notcontains '/.neewa/evidence/') {
    [System.IO.Directory]::CreateDirectory((Split-Path -Parent $exclude)) | Out-Null
    [System.IO.File]::WriteAllText($exclude, $old.TrimEnd() + "`n/.neewa/evidence/`n", [System.Text.UTF8Encoding]::new($false))
  }
  $dir = [System.IO.Path]::GetFullPath($Repo)
  foreach ($part in @('.neewa', 'evidence', $JobId)) {
    $dir = Join-Path $dir $part
    if ((Test-Path -LiteralPath $dir) -and ((Get-Item -LiteralPath $dir -Force).Attributes -band [System.IO.FileAttributes]::ReparsePoint)) { throw 'evidence directory cannot be a reparse point' }
    [System.IO.Directory]::CreateDirectory($dir) | Out-Null
  }
  return $dir
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
    candidate_worktree_sha256 = $null
    candidate_stable = $false
  }
  $identity = Get-NeewaRepoIdentity -Repo $Repo
  $result.candidate_head = $identity.head
  $result.candidate_diff_sha256 = $identity.diff_sha256
  $result.candidate_worktree_sha256 = $identity.worktree_sha256
  if (-not $identity.head -or -not $identity.worktree_sha256) {
    $result.failure_class = 'CANDIDATE_IDENTITY_MISSING'
    $result.stderr = 'Cannot bind tests to a Git candidate'
    return [pscustomobject]$result
  }
  $parsed = @($ArgumentList | Where-Object { $_ })
  if (-not $parsed -and $TestCommand) {
    $parsed = @($TestCommand -split '\s+' | Where-Object { $_ })
    if ($parsed.Count -ge 1 -and $parsed[0] -match 'python(\.exe)?$') {
      if (-not $PythonRelative -or $PythonRelative -eq 'backend\.venv\Scripts\python.exe') {
        $PythonRelative = $parsed[0]
      }
      $parsed = @($parsed | Select-Object -Skip 1)
    }
  }
  $allow = ConvertTo-AllowlistedTestArgs -Tokens $parsed
  if (-not $allow) {
    $result.stderr = 'test argv is not allowlisted'
    $result.failure_class = 'UNAPPROVED_TEST_COMMAND'
    $result.argv = @($parsed)
    return [pscustomobject]$result
  }
  if (-not $CwdRelative -or $CwdRelative -eq '.') {
    $cwd = [System.IO.Path]::GetFullPath($Repo)
  } else {
    $cwd = Resolve-NeewaInsideRepo -Repo $Repo -Relative $CwdRelative
  }
  $python = $null
  if ($PythonRelative -match '^(python|python3)(\.exe)?$') {
    $cmd = Get-Command $PythonRelative -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { $python = [string]$cmd.Source }
  } else {
    if (-not $PythonRelative) { $PythonRelative = 'backend\.venv\Scripts\python.exe' }
    $python = Resolve-NeewaInsideRepo -Repo $Repo -Relative $PythonRelative
  }
  if ((-not $python -or -not (Test-Path -LiteralPath $python)) -and $PythonRelative -match '^(python|python3)(\.exe)?$') {
    $uvRoot = Join-Path $env:APPDATA 'uv\python'
    if (Test-Path -LiteralPath $uvRoot) {
      $uv = Get-ChildItem -LiteralPath $uvRoot -Filter python.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
      if ($uv) { $python = $uv.FullName }
    }
  }
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
  $drained = Invoke-NeewaDrainedProcess -StartInfo $psi -TimeoutMs 900000
  $stdout = [string]$drained.Stdout
  $stderr = [string]$drained.Stderr
  if ($drained.TimedOut) {
    $result.failure_class = 'CHILD_TIMEOUT'
    $result.stderr = 'independent test exceeded 900 seconds'
    $result.stdout = $stdout
    return [pscustomobject]$result
  }
  $parser = 'pytest'
  if (@($allow) -contains 'unittest') { $parser = 'unittest' }
  if ($parser -eq 'unittest') {
    $outcome = Get-NeewaUnittestOutcome -Stdout $stdout -Stderr $stderr -ExitCode ([int]$drained.ExitCode)
  } else {
    $outcome = Get-NeewaPytestOutcome -Stdout $stdout -Stderr $stderr -ExitCode ([int]$drained.ExitCode)
  }
  $procExit = [int]$drained.ExitCode
  $result.command = (@($python) + $allow) -join ' '
  $result.argv = @($allow)
  $result.cwd = $cwd
  $result.python = $python
  $result.exit_code = $procExit
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
$pythonRel = $null
$cwdRel = $null
if ($job.PSObject.Properties['python'] -and $job.python) { $pythonRel = [string]$job.python }
if ($job.PSObject.Properties['cwd'] -and $job.cwd) { $cwdRel = [string]$job.cwd }
$evidenceError = $false
try {
  $evidenceDir = Get-NeewaWorkspaceEvidenceDir -Repo $repo -JobId ([string]$job.job_id)
} catch {
  $evidenceError = $true
  $evidenceDir = $OutDir
}
$ran = Invoke-AllowlistedProductTest -Repo $repo -PythonRelative $pythonRel -CwdRelative $cwdRel -ArgumentList $argList -TestCommand ([string]$job.test_command)
$artifact = Join-Path $OutDir ("{0}-independent-test.json" -f $job.job_id)
if ($evidenceError) { $ran.passed = $false; $ran.failure_class = 'REVIEW_EVIDENCE_INVALID' }
$transcript = Join-Path $evidenceDir ("{0}-independent-test-transcript.txt" -f $job.job_id)
$after = Get-NeewaRepoIdentity -Repo $repo
$ran.candidate_stable = ($ran.candidate_head -and $ran.candidate_head -eq $after.head -and $ran.candidate_worktree_sha256 -eq $after.worktree_sha256)
if ($ran.passed -and -not $ran.candidate_stable) { $ran.passed = $false; $ran.failure_class = 'CANDIDATE_CHANGED' }
$status = if ($ran.passed) { 'COMPLETED' } else { 'FAILED' }
$reason = if ($ran.passed) { $null } else { $ran.failure_class }
$stdoutText = [string]$ran.stdout
$stderrText = [string]$ran.stderr
[System.IO.File]::WriteAllText($transcript, ("STDOUT`n{0}`nSTDERR`n{1}`n" -f $stdoutText, $stderrText), [System.Text.UTF8Encoding]::new($false))
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
  candidate_worktree_sha256 = $ran.candidate_worktree_sha256
  candidate_identity_schema = 2
  candidate_stable = [bool]$ran.candidate_stable
  transcript = $transcript
  transcript_sha256 = (Get-FileHash -LiteralPath $transcript -Algorithm SHA256).Hash.ToLowerInvariant()
  workspace_artifacts = @($transcript)
  stdout_tail = $(if ($stdoutText.Length -gt 2000) { $stdoutText.Substring($stdoutText.Length - 2000) } else { $stdoutText })
  stderr_tail = $(if ($stderrText.Length -gt 2000) { $stderrText.Substring($stderrText.Length - 2000) } else { $stderrText })
}
$payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $artifact -Encoding utf8
if ($evidenceDir -ne $OutDir) {
  Copy-Item -LiteralPath $artifact -Destination (Join-Path $evidenceDir (Split-Path -Leaf $artifact)) -Force
}
[pscustomobject]@{
  job_id = $job.job_id
  status = $status
  reason = $reason
  artifact = $artifact
  artifact_paths = @($artifact, $transcript)
  independent_test = $payload
  test_results = $payload
  stdout_tail = $payload.stdout_tail
  failure_class = $ran.failure_class
  collected = $ran.collected
  passed = $ran.passed
  candidate_head = $ran.candidate_head
  candidate_diff_sha256 = $ran.candidate_diff_sha256
}
}
}

