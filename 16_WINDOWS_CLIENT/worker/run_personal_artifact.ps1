# Allowlisted: create one documented artifact in the personal test directory.
$ErrorActionPreference = 'Stop'
$root = Join-Path $env:USERPROFILE 'NEEWA-Personal'
$jobs = Join-Path $root 'jobs'
New-Item -ItemType Directory -Force -Path $jobs | Out-Null
$stamp = Get-Date -Format 'yyyyMMddTHHmmss'
$path = Join-Path $jobs "JOB-$stamp-personal-artifact.txt"
@(
  "NEEWA personal worker artifact"
  "created=$stamp"
  "host=$env:COMPUTERNAME"
  "scope=USERPROFILE\NEEWA-Personal"
  "git_writer=Cursor"
) | Set-Content -Path $path -Encoding utf8
Write-Output $path
