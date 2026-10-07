# Read-only Codex review through ChatGPT sign-in. No OPENAI_API_KEY fallback.
[CmdletBinding()]
param(
  [Parameter(Mandatory)][pscustomobject]$Job,
  [Parameter(Mandatory)][string]$JobsDir
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$policy = Get-Content -Raw -LiteralPath (Join-Path $here 'cursor-call-policy.json') | ConvertFrom-Json
. (Join-Path $here 'NeewaPersonalWorkspace.ps1')

function New-CodexResult([string]$Status, [string]$Reason, [string]$Model, [string]$Artifact) {
  return [pscustomobject]@{
    job_id = [string]$Job.job_id
    status = $Status
    reason = $Reason
    model = $Model
    auth = 'chatgpt'
    artifact = $Artifact
    failure_class = $(if ($Status -eq 'BLOCKED') { 'UNAPPROVED_PATH' } elseif ($Status -eq 'FAILED') { 'CODEX_AUTH' } else { $null })
  }
}

$prompt = [string]$Job.prompt
$requested = [string]$Job.repo
if (-not $requested) { $requested = [string]$Job.workspace_path }
if (-not $prompt) {
  return New-CodexResult 'FAILED' 'codex_review requires prompt' $null $null
}
$repo = Resolve-ApprovedRepo $requested
if (-not $repo) {
  return New-CodexResult 'BLOCKED' 'repo is outside the personal workspace roots or is explicitly excluded' $null $null
}

$codex = Get-Command codex -ErrorAction SilentlyContinue
if (-not $codex) {
  return New-CodexResult 'FAILED' 'codex CLI is not installed for this identity' $null $null
}
$login = & $codex.Source login status 2>&1 | Out-String
if ($login -notmatch 'Logged in using ChatGPT') {
  return New-CodexResult 'FAILED' 'ChatGPT sign-in is not active for this identity' $null $null
}

$model = [string]$Job.model
if (-not $model) { $model = 'gpt-6-astra' }
$effort = [string]$Job.effort
if (-not $effort) { $effort = 'high' }
$last = Join-Path $JobsDir "$($Job.job_id)-codex-last.txt"
$events = Join-Path $JobsDir "$($Job.job_id)-codex.jsonl"
$savedKey = $env:OPENAI_API_KEY
Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
try {
  $configArg = 'model_reasoning_effort="' + $effort + '"'
  & $codex.Source exec --skip-git-repo-check -s read-only -C $repo -m $model -c $configArg --json -o $last $prompt 1> $events 2>&1
  $code = $LASTEXITCODE
} finally {
  if ($null -ne $savedKey) { $env:OPENAI_API_KEY = $savedKey }
}
if ($code -ne 0) {
  return New-CodexResult 'FAILED' "codex exec exited $code; API-key fallback was not used" $model $events
}
return New-CodexResult 'COMPLETED' "chatgpt codex exec model=$model effort=$effort" $model $last
