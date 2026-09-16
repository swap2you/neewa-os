# Start the local cua-driver daemon in the interactive user session.
# Not a SYSTEM service. Refuses a second instance via the named pipe.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$env:CUA_DRIVER_RS_TELEMETRY_ENABLED = '0'
$env:CUA_TELEMETRY_ENABLED = '0'
$bin = Join-Path $env:LOCALAPPDATA 'Programs\Cua\cua-driver\bin'
$exe = Join-Path $bin 'cua-driver.exe'
if (-not (Test-Path $exe)) { throw "cua-driver not installed: $exe" }
$env:Path = "$bin;$env:Path"
$status = & $exe status 2>&1 | Out-String
if ($status -match 'daemon is running') {
  Write-Output 'cua-driver already running'
  exit 0
}
$logDir = Join-Path $env:USERPROFILE 'NEEWA-Personal\logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir 'cua-driver-serve.log'
Start-Process -FilePath $exe -ArgumentList @('serve', '--permission-mode', 'standard') -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError ($log + '.err') | Out-Null
$ok = $false
foreach ($i in 1..20) {
  Start-Sleep -Milliseconds 250
  $status = & $exe status 2>&1 | Out-String
  if ($status -match 'daemon is running') { $ok = $true; break }
}
if (-not $ok) { throw 'cua-driver serve did not become ready' }
Write-Output 'cua-driver started'
