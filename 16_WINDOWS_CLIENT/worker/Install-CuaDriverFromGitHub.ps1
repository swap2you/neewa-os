# Official Cua Driver install that does not resolve cua.ai.
# Downloads the tagged GitHub release install.ps1 plus the sibling
# _install-common.psm1 from the matching git tag, verifies the published
# SHA256 for install.ps1, then runs the official script from disk.
[CmdletBinding()]
param(
  [string]$Version = '0.28.2',
  [switch]$AutoStart
)
$ErrorActionPreference = 'Stop'
$stage = Join-Path $env:USERPROFILE 'NEEWA-Personal\vendor\cua-driver-install'
New-Item -ItemType Directory -Force -Path $stage | Out-Null
$installUrl = "https://github.com/trycua/cua/releases/download/cua-driver-rs-v$Version/install.ps1"
$psm1Url = "https://raw.githubusercontent.com/trycua/cua/cua-driver-rs-v$Version/libs/cua-driver/scripts/_install-common.psm1"
$expected = @{
  '0.28.2' = '3e770fa8c351b80db99ae6b080f696a22f844534498bf44d45816cbd05eb0c3f'
}
Invoke-WebRequest -Uri $installUrl -OutFile (Join-Path $stage 'install.ps1') -UseBasicParsing
Invoke-WebRequest -Uri $psm1Url -OutFile (Join-Path $stage '_install-common.psm1') -UseBasicParsing
$actual = (Get-FileHash -Algorithm SHA256 (Join-Path $stage 'install.ps1')).Hash.ToLowerInvariant()
if ($expected.ContainsKey($Version) -and $actual -ne $expected[$Version]) {
  throw "install.ps1 checksum mismatch: $actual"
}
$env:CUA_DRIVER_RS_VERSION = $Version
$env:CUA_DRIVER_RS_TELEMETRY_ENABLED = '0'
$env:CUA_TELEMETRY_ENABLED = '0'
$arg = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $stage 'install.ps1'), '-Release', $Version)
if (-not $AutoStart) { $arg += '-NoAutoStart' }
& powershell.exe @arg
if ($LASTEXITCODE -ne 0) { throw "install.ps1 exited $LASTEXITCODE" }
$exe = Join-Path $env:LOCALAPPDATA 'Programs\Cua\cua-driver\bin\cua-driver.exe'
if (-not (Test-Path $exe)) { throw 'cua-driver.exe missing after install' }
& $exe telemetry disable | Out-Host
Write-Output $exe
