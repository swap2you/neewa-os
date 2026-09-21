# Install the NEEWA Windows worker to a stable LocalAppData path and HKCU Run entry.
# Reversible: re-run with -Remove to clear the Run key and optionally -PurgeFiles.
# Does not touch the canonical Workspace checkout or create a SYSTEM service.
[CmdletBinding()]
param(
  [string]$SourceDir,
  [string]$TargetDir = (Join-Path $env:LOCALAPPDATA 'NEEWA\worker'),
  [switch]$Start,
  [switch]$Remove,
  [switch]$PurgeFiles
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $SourceDir) { $SourceDir = $here }

$required = @(
  'Start-NeewaWindowsWorker.ps1',
  'Invoke-NeewaWindowsJob.ps1',
  'Invoke-NeewaCursorCall.ps1',
  'cursor-call-policy.json',
  'NeewaPersonalWorkspace.ps1',
  'Resolve-NeewaResultFolder.ps1',
  'allowlist.json',
  'neewa_a2_receipt_auth.py'
)
$run = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
if (-not $pwsh) { $pwsh = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe' }

if ($Remove) {
  Remove-ItemProperty -Path $run -Name 'NEEWA-WindowsWorker' -ErrorAction SilentlyContinue
  if ($PurgeFiles -and (Test-Path -LiteralPath $TargetDir)) {
    Remove-Item -LiteralPath $TargetDir -Recurse -Force
  }
  Write-Output ([pscustomobject]@{
    status = 'REMOVED'
    target_dir = $TargetDir
    hkcu_cleared = $true
    purged_files = [bool]$PurgeFiles
  } | ConvertTo-Json -Compress)
  return
}

foreach ($name in $required) {
  $src = Join-Path $SourceDir $name
  if (-not (Test-Path -LiteralPath $src)) {
    throw "Missing required worker file: $src"
  }
}

New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
$copied = @()
Get-ChildItem -LiteralPath $SourceDir -File | ForEach-Object {
  if ($_.Name -match '(?i)\.(ps1|json|yaml|yml|py)$' -or $_.Name -eq 'README.md') {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $TargetDir $_.Name) -Force
    $copied += $_.Name
  }
}
$scriptRoot = Split-Path -Parent $SourceDir
$repoScripts = Join-Path (Split-Path -Parent $scriptRoot) '12_SCRIPTS'
foreach ($name in @('neewa_a2_receipt_auth.py', 'neewa_action_semantics.py')) {
  $extra = Join-Path $repoScripts $name
  if (Test-Path -LiteralPath $extra) {
    Copy-Item -LiteralPath $extra -Destination (Join-Path $TargetDir $name) -Force
    if ($copied -notcontains $name) { $copied += $name }
  }
}

$workerScript = Join-Path $TargetDir 'Start-NeewaWindowsWorker.ps1'
$policyPath = Join-Path $TargetDir 'cursor-call-policy.json'
$policy = Get-Content -Raw -LiteralPath $policyPath | ConvertFrom-Json
$runValue = '"{0}" -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{1}"' -f $pwsh, $workerScript
New-ItemProperty -Path $run -Name 'NEEWA-WindowsWorker' -PropertyType String -Force -Value $runValue | Out-Null

$startedPid = $null
if ($Start) {
  $existing = @(
    Get-CimInstance Win32_Process |
    Where-Object {
      $_.Name -match '^(pwsh|powershell)\.exe$' -and
      $_.CommandLine -match 'Start-NeewaWindowsWorker\.ps1'
    }
  )
  foreach ($proc in $existing) {
    try { Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop } catch { }
  }
  Start-Sleep -Milliseconds 800
  Start-Process -FilePath $pwsh -ArgumentList @(
    '-NoProfile',
    '-ExecutionPolicy', 'Bypass',
    '-WindowStyle', 'Hidden',
    '-File', $workerScript
  ) -WindowStyle Hidden | Out-Null
  Start-Sleep -Seconds 2
  $live = @(
    Get-CimInstance Win32_Process |
    Where-Object {
      $_.Name -match '^(pwsh|powershell)\.exe$' -and
      $_.CommandLine -match [regex]::Escape($workerScript)
    }
  )
  if ($live.Count -ne 1) {
    throw "Expected exactly one worker at $workerScript; count=$($live.Count)"
  }
  $startedPid = $live[0].ProcessId
}

Write-Output ([pscustomobject]@{
  status = 'INSTALLED'
  source_dir = $SourceDir
  target_dir = $TargetDir
  worker_script = $workerScript
  policy_path = $policyPath
  default_timeout_sec = [int]$policy.default_timeout_sec
  max_timeout_sec = [int]$policy.max_timeout_sec
  copied_files = $copied
  hkcu_run = $runValue
  worker_pid = $startedPid
} | ConvertTo-Json -Compress)
