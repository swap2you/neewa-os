# Probe and repair a worker scratch directory without using a broken TEMP.
# Dot-source safe. No param block: a dotted param() would clear the caller's variables.

function Get-NeewaScratchRoot {
  $root = Join-Path $env:LOCALAPPDATA 'NEEWA\scratch'
  New-Item -ItemType Directory -Force -Path $root | Out-Null
  return $root
}

function Test-NeewaWritableDirectory {
  param([Parameter(Mandatory)][string]$Path)
  $row = [ordered]@{
    path = $Path
    file_ok = $false
    directory_ok = $false
    error = $null
  }
  $file = $null
  $dir = $null
  try {
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
    $file = Join-Path $Path ('probe-' + [guid]::NewGuid().ToString('n') + '.txt')
    $payload = 'neewa-temp-probe'
    $stream = [System.IO.File]::Create($file)
    try {
      $bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
      $stream.Write($bytes, 0, $bytes.Length)
      $stream.Flush()
    } finally {
      $stream.Dispose()
    }
    $read = [System.IO.File]::ReadAllText($file)
    if ($read -ne $payload) { throw 'read mismatch' }
    [System.IO.File]::Delete($file)
    if (Test-Path -LiteralPath $file) { throw 'probe file remained after delete' }
    $file = $null
    $dir = Join-Path $Path ('probe-dir-' + [guid]::NewGuid().ToString('n'))
    New-Item -ItemType Directory -Path $dir | Out-Null
    if (-not (Test-Path -LiteralPath $dir)) { throw 'probe directory was not created' }
    Remove-Item -LiteralPath $dir -Force
    if (Test-Path -LiteralPath $dir) { throw 'probe directory remained after delete' }
    $dir = $null
    $row.file_ok = $true
    $row.directory_ok = $true
  } catch {
    $row.error = [string]$_.Exception.Message
    if ($file -and (Test-Path -LiteralPath $file)) {
      Remove-Item -LiteralPath $file -Force -ErrorAction SilentlyContinue
    }
    if ($dir -and (Test-Path -LiteralPath $dir)) {
      Remove-Item -LiteralPath $dir -Force -ErrorAction SilentlyContinue
    }
  }
  return [pscustomobject]$row
}

function Get-NeewaFreeBytes {
  param([string]$Path)
  try {
    $item = Get-Item -LiteralPath $Path
    $drive = $item.PSDrive
    if ($drive -and $null -ne $drive.Free) { return [int64]$drive.Free }
  } catch { }
  return $null
}

function Invoke-NeewaTempProbeReport {
  $scratch = Get-NeewaScratchRoot
  $candidates = @()
  foreach ($name in @('TEMP', 'TMP')) {
    $value = [Environment]::GetEnvironmentVariable($name, 'Process')
    if ($value) { $candidates += $value }
  }
  $candidates += $scratch
  $seen = @{}
  $rows = @()
  foreach ($candidate in $candidates) {
    $key = $candidate.TrimEnd('\').ToLowerInvariant()
    if ($seen.ContainsKey($key)) { continue }
    $seen[$key] = $true
    $rows += Test-NeewaWritableDirectory -Path $candidate
  }
  $scratchRow = @($rows | Where-Object { $_.path.TrimEnd('\').ToLowerInvariant() -eq $scratch.TrimEnd('\').ToLowerInvariant() } | Select-Object -First 1)
  $usable = $null
  foreach ($row in $rows) {
    if ($row.file_ok -and $row.directory_ok) { $usable = $row.path; break }
  }
  if (-not $usable -and $scratchRow -and $scratchRow.file_ok) { $usable = $scratch }
  $account = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
  return [pscustomobject]@{
    account = $account
    host = $env:COMPUTERNAME
    scratch = $scratch
    usable_temp = $usable
    free_bytes = (Get-NeewaFreeBytes -Path $scratch)
    candidates = @($rows)
    scratch_persisted = (Test-Path -LiteralPath $scratch)
    failure_class = $(if ($usable) { $null } else { 'TEMP_UNWRITABLE' })
  }
}

function Set-NeewaChildTemp {
  param(
    [Parameter(Mandatory)]$StartInfo,
    [string]$Scratch
  )
  if (-not $Scratch) { $Scratch = Get-NeewaScratchRoot }
  $cache = Join-Path $Scratch 'pytest-cache'
  New-Item -ItemType Directory -Force -Path $cache | Out-Null
  $StartInfo.EnvironmentVariables['TEMP'] = $Scratch
  $StartInfo.EnvironmentVariables['TMP'] = $Scratch
  $StartInfo.EnvironmentVariables['TMPDIR'] = $Scratch
  $StartInfo.EnvironmentVariables['PYTEST_CACHE_DIR'] = $cache
  foreach ($secret in @('OPENAI_API_KEY', 'OPENAI_API_KEY_BEARER')) {
    if ($StartInfo.EnvironmentVariables.ContainsKey($secret)) {
      [void]$StartInfo.EnvironmentVariables.Remove($secret)
    }
  }
  return $Scratch
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
$report = Invoke-NeewaTempProbeReport
$artifact = Join-Path $OutDir ("{0}-temp-probe.json" -f $job.job_id)
$payload = [ordered]@{
  job_id = $job.job_id
  action = 'temp_probe'
  status = $(if ($report.failure_class) { 'FAILED' } else { 'COMPLETED' })
  reason = $(if ($report.failure_class) { 'no candidate directory accepted a file and a directory' } else { $null })
  failure_class = $report.failure_class
  account = $report.account
  host = $report.host
  scratch = $report.scratch
  usable_temp = $report.usable_temp
  free_bytes = $report.free_bytes
  scratch_persisted = $report.scratch_persisted
  candidates = @($report.candidates)
}
$payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $artifact -Encoding utf8
[pscustomobject]@{
  job_id = $job.job_id
  status = $payload.status
  reason = $payload.reason
  artifact = $artifact
  failure_class = $payload.failure_class
}
}
}
