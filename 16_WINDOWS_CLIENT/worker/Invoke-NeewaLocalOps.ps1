# Local ChakraOps health, restart, and UI screenshot. Loopback only.
[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$JobFile,
  [string]$OutDir,
  [Parameter(Mandatory)][ValidateSet('local_health', 'local_app_restart', 'ui_verify')][string]$Action
)
$ErrorActionPreference = 'Stop'
$job = Get-Content -Raw -LiteralPath $JobFile | ConvertFrom-Json
if (-not $OutDir) { $OutDir = Split-Path -Parent $JobFile }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$canonical = 'C:\Users\swap2\NEEWA-Personal\projects\ChakraOps'
$repo = [string]$job.repo
if (-not $repo) { $repo = $canonical }
$repoFull = [System.IO.Path]::GetFullPath($repo).TrimEnd('\')
$healthUrls = @(
  'http://127.0.0.1:18800/health',
  'http://127.0.0.1:18873/api/healthz'
)

function Get-LoopbackHealth {
  $rows = @()
  foreach ($url in $healthUrls) {
    $row = [ordered]@{ url = $url; status_code = $null; ok = $false; error = $null }
    try {
      $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
      $row.status_code = [int]$resp.StatusCode
      $row.ok = ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 300)
    } catch {
      $row.error = [string]$_.Exception.Message
    }
    $rows += [pscustomobject]$row
  }
  return $rows
}

$status = 'COMPLETED'
$reason = $null
$failure = $null
$extra = [ordered]@{}
if ($repoFull -ne $canonical) {
  $status = 'BLOCKED'
  $reason = 'local ops are bound to the canonical ChakraOps checkout'
  $failure = 'UNAPPROVED_PATH'
} elseif ($Action -eq 'local_health') {
  $extra.checks = @(Get-LoopbackHealth)
  if (@($extra.checks | Where-Object { -not $_.ok }).Count -gt 0) {
    $status = 'FAILED'
    $failure = 'LOCAL_HEALTH_FAILED'
    $reason = 'one or more loopback health checks failed'
  }
} elseif ($Action -eq 'local_app_restart') {
  $script = Join-Path $canonical 'chakra.ps1'
  if (-not (Test-Path -LiteralPath $script)) {
    $status = 'FAILED'
    $failure = 'LOCAL_RESTART_MISSING'
    $reason = 'chakra.ps1 is missing'
  } else {
    $native = $PSNativeCommandUseErrorActionPreference
    $PSNativeCommandUseErrorActionPreference = $false
    try {
      & powershell.exe -NoProfile -File $script stop
      $stopCode = $LASTEXITCODE
      & powershell.exe -NoProfile -File $script start
      $startCode = $LASTEXITCODE
    } finally {
      $PSNativeCommandUseErrorActionPreference = $native
    }
    $extra.stop_exit = $stopCode
    $extra.start_exit = $startCode
    $extra.checks = @(Get-LoopbackHealth)
    if ($startCode -ne 0 -or @($extra.checks | Where-Object { -not $_.ok }).Count -gt 0) {
      $status = 'FAILED'
      $failure = 'LOCAL_RESTART_FAILED'
      $reason = 'local restart did not leave both health endpoints up'
    }
  }
} else {
  $extra.checks = @(Get-LoopbackHealth)
  $shotDir = Join-Path $env:LOCALAPPDATA 'NEEWA\scratch\ui'
  New-Item -ItemType Directory -Force -Path $shotDir | Out-Null
  $shot = Join-Path $shotDir ("{0}-18873.png" -f $job.job_id)
  $playwright = Join-Path $canonical 'frontend\node_modules\.bin\playwright.cmd'
  if (-not (Test-Path -LiteralPath $playwright)) {
    $status = 'FAILED'
    $failure = 'UI_TOOLING_MISSING'
    $reason = 'frontend playwright is not installed; loopback health was still recorded'
  } else {
    $native = $PSNativeCommandUseErrorActionPreference
    $PSNativeCommandUseErrorActionPreference = $false
    try {
      & $playwright screenshot --browser chromium 'http://127.0.0.1:18873/' $shot
      $code = $LASTEXITCODE
    } finally {
      $PSNativeCommandUseErrorActionPreference = $native
    }
    $extra.screenshot = $shot
    $extra.screenshot_exit = $code
    $extra.screenshot_exists = (Test-Path -LiteralPath $shot)
    if ($code -ne 0 -or -not $extra.screenshot_exists) {
      $status = 'FAILED'
      $failure = 'UI_VERIFY_FAILED'
      $reason = 'playwright screenshot did not produce a file'
    }
  }
}

$artifact = Join-Path $OutDir ("{0}-{1}.json" -f $job.job_id, $Action)
$payload = [ordered]@{
  job_id = $job.job_id
  action = $Action
  status = $status
  reason = $reason
  failure_class = $failure
  repo = $repoFull
}
foreach ($key in $extra.Keys) { $payload[$key] = $extra[$key] }
$payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $artifact -Encoding utf8
[pscustomobject]@{
  job_id = $job.job_id
  status = $status
  reason = $reason
  artifact = $artifact
  failure_class = $failure
}
