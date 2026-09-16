# User-logon startup for cua-driver and the NEEWA Windows worker.
# HKCU Run only. Not a SYSTEM service. Not RunLevel=Highest.
[CmdletBinding()]
param([switch]$Remove)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$run = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
if (-not $pwsh) { $pwsh = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe' }
$driver = Join-Path $here 'Start-CuaDriver.ps1'
$worker = Join-Path $here 'Start-NeewaWindowsWorker.ps1'
if ($Remove) {
  Remove-ItemProperty -Path $run -Name 'NEEWA-CuaDriver' -ErrorAction SilentlyContinue
  Remove-ItemProperty -Name 'NEEWA-WindowsWorker' -Path $run -ErrorAction SilentlyContinue
  Write-Output 'removed HKCU Run entries'
  return
}
New-ItemProperty -Path $run -Name 'NEEWA-CuaDriver' -PropertyType String -Force -Value "`"$pwsh`" -NoProfile -WindowStyle Hidden -File `"$driver`"" | Out-Null
New-ItemProperty -Path $run -Name 'NEEWA-WindowsWorker' -PropertyType String -Force -Value "`"$pwsh`" -NoProfile -WindowStyle Hidden -File `"$worker`"" | Out-Null
Write-Output 'registered HKCU Run entries for cua-driver and NEEWA Windows worker'
