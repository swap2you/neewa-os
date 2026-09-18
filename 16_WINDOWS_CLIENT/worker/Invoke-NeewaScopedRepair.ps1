# Execute an allowlisted scoped-repair job. No caller shell. No arbitrary destination.
[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$JobFile,
  [string]$OutDir
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$mod = Join-Path $here '..\..\12_SCRIPTS\neewa_scoped_repair.py'
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $py) { throw 'python interpreter is not installed' }
if (-not (Test-Path -LiteralPath $mod)) { throw "scoped repair module missing: $mod" }
$job = Get-Content -Raw -LiteralPath $JobFile | ConvertFrom-Json
$out = & $py.Source $mod dispatch --job-file $JobFile
if (-not $out) { throw 'scoped repair dispatch returned no receipt' }
$parsed = $out | ConvertFrom-Json
$artifact = $null
if ($OutDir) {
  New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
  $artifact = Join-Path $OutDir "$($job.job_id)-scoped-repair.json"
  [System.IO.File]::WriteAllText(
    $artifact,
    ($parsed | ConvertTo-Json -Depth 12),
    [System.Text.UTF8Encoding]::new($false)
  )
}
return [pscustomobject]@{
  job_id = $job.job_id
  status = [string]$parsed.status
  reason = $parsed.failure_reason
  artifact = $artifact
  failure_class = $parsed.failure_reason
  authorization = $parsed.authorization
  receipt = $parsed
}
