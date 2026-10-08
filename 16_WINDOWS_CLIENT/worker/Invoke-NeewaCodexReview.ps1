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

$routes = Get-Content -Raw -LiteralPath (Join-Path $here 'chatgpt_review_routes.json') | ConvertFrom-Json
if ($routes.api_key_fallback -or $routes.paid_api) {
  return New-CodexResult 'FAILED' 'paid API fallback is disabled' $null $null
}
$taskName = [string]$Job.review_task
if (-not $taskName) { $taskName = 'software_review' }
$spec = $routes.tasks.$taskName
if (-not $spec) { $spec = $routes.tasks.acceptance }
$model = [string]$spec.model
$effort = [string]$spec.effort
if (-not $effort) { $effort = 'high' }
$probedNames = @($routes.probed.PSObject.Properties.Name)
if ($probedNames -contains $model) {
  $probe = $routes.probed.$model
  if (-not $probe.available) {
    $fallback = [string]$spec.fallback_model
    $fallbackProbe = $null
    if ($fallback -and ($probedNames -contains $fallback)) { $fallbackProbe = $routes.probed.$fallback }
    if ($fallbackProbe -and $fallbackProbe.available) {
      $model = $fallback
    } else {
      return New-CodexResult 'FAILED' "model unavailable and paid API fallback is disabled" $model $null
    }
  }
}
$prompt = @"
Review context: $($spec.context). Authentication: ChatGPT sign-in. Do not request an API key or credits.
Requested task: $taskName. Requested model: $model. Effort: $effort.
End with one line: DECISION: APPROVE or DECISION: CHANGES_REQUIRED or DECISION: INSUFFICIENT_EVIDENCE or DECISION: OBJECT or DECISION: HOLD.
A process exit of 0 is not approval.

$prompt
"@
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
$decision = $null
if (Test-Path -LiteralPath $last) {
  $reviewText = Get-Content -Raw -LiteralPath $last
  foreach ($match in [regex]::Matches([string]$reviewText, '(?i)DECISION:\s*(APPROVE|CHANGES_REQUIRED|INSUFFICIENT_EVIDENCE|OBJECT|HOLD)')) {
    $decision = $match.Groups[1].Value.ToUpperInvariant()
  }
}
$result = New-CodexResult 'COMPLETED' "chatgpt codex exec model=$model effort=$effort" $model $last
$result | Add-Member -NotePropertyName review_decision -NotePropertyValue $decision -Force
$result | Add-Member -NotePropertyName review_task -NotePropertyValue $taskName -Force
$result | Add-Member -NotePropertyName effort -NotePropertyValue $effort -Force
$result | Add-Member -NotePropertyName requested_model -NotePropertyValue $model -Force
$result | Add-Member -NotePropertyName authentication -NotePropertyValue 'ChatGPT' -Force
$result | Add-Member -NotePropertyName api_key_fallback -NotePropertyValue $false -Force
if (-not $decision) {
  $result.reason = "codex exited 0 without a structured decision; exit is not approval"
}
return $result
