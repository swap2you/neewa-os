# NEEWA Windows companion capability discovery.
# Reports AVAILABLE / NOT INSTALLED / AUTH REQUIRED / PERMISSION REQUIRED / UNSUPPORTED.
# Does not execute employer tools, does not print secrets, does not open a listener.

$ErrorActionPreference = 'Continue'
$script:out = [System.Collections.Generic.List[object]]::new()

function Add-Cap {
  param($Name, $Status, $Detail)
  $script:out.Add([pscustomobject]@{ name = $Name; status = $Status; detail = $Detail }) | Out-Null
}

function Find-Cmd($names) {
  foreach ($n in $names) {
    $c = Get-Command $n -ErrorAction SilentlyContinue
    if ($c) { return $c }
  }
  return $null
}

function Find-PathCmd($paths) {
  foreach ($p in $paths) {
    if ($p -and (Test-Path -LiteralPath $p)) {
      return $p
    }
  }
  return $null
}

function Invoke-CapCmd {
  param($File, $ArgumentList, $TimeoutMs = 12000)
  $out = Join-Path $env:TEMP ("neewa-cap-{0}.out" -f [guid]::NewGuid().ToString('N'))
  $err = Join-Path $env:TEMP ("neewa-cap-{0}.err" -f [guid]::NewGuid().ToString('N'))
  try {
    $p = Start-Process -FilePath $File -ArgumentList $ArgumentList -PassThru -NoNewWindow -RedirectStandardOutput $out -RedirectStandardError $err
    if (-not $p.WaitForExit($TimeoutMs)) {
      Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
      return @{ text = 'timeout'; code = -1 }
    }
    $text = ''
    if (Test-Path $out) { $text += [string](Get-Content -Raw $out) }
    if (Test-Path $err) { $text += [string](Get-Content -Raw $err) }
    return @{ text = $text.Trim(); code = $p.ExitCode }
  } finally {
    Remove-Item $out, $err -ErrorAction SilentlyContinue
  }
}

$git = Find-Cmd @('git')
if ($git) {
  $ver = (& git --version) 2>$null
  Add-Cap 'Git' 'AVAILABLE' $ver
} else { Add-Cap 'Git' 'NOT INSTALLED' '' }

$cursor = Find-Cmd @('cursor', 'cursor.cmd')
if ($cursor) {
  $ver = (& $cursor.Source --version) 2>$null | Select-Object -First 1
  Add-Cap 'Cursor IDE CLI' 'AVAILABLE' "$($cursor.Source) $ver"
} else { Add-Cap 'Cursor IDE CLI' 'NOT INSTALLED' 'Desktop app may exist without CLI on PATH' }

$agentCmd = Join-Path $env:LOCALAPPDATA 'cursor-agent\agent.cmd'
if (Test-Path -LiteralPath $agentCmd) {
  $verOut = Join-Path $env:TEMP 'neewa-agent-ver.out'
  $verErr = Join-Path $env:TEMP 'neewa-agent-ver.err'
  $p = Start-Process -FilePath $agentCmd -ArgumentList @('--version') -PassThru -NoNewWindow -RedirectStandardOutput $verOut -RedirectStandardError $verErr
  if (-not $p.WaitForExit(8000)) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
  $ver = if (Test-Path $verOut) { (Get-Content -Raw $verOut).Trim() } else { 'unknown' }
  $stOut = Join-Path $env:TEMP 'neewa-agent-st.out'
  $stErr = Join-Path $env:TEMP 'neewa-agent-st.err'
  $p2 = Start-Process -FilePath $agentCmd -ArgumentList @('status') -PassThru -NoNewWindow -RedirectStandardOutput $stOut -RedirectStandardError $stErr
  if (-not $p2.WaitForExit(8000)) { Stop-Process -Id $p2.Id -Force -ErrorAction SilentlyContinue }
  $st = if (Test-Path $stOut) { (Get-Content -Raw $stOut).Trim() } else { '' }
  if ($st -match '(?i)not logged in|authentication required') {
    Add-Cap 'Cursor Agent CLI' 'AUTH REQUIRED' "$agentCmd $ver"
    Add-Cap 'cursor_call' 'AUTH REQUIRED' 'A1 agent --print; worker reports AUTH_REQUIRED/BLOCKED'
  } else {
    Add-Cap 'Cursor Agent CLI' 'AVAILABLE' "$agentCmd $ver"
    Add-Cap 'cursor_call' 'AVAILABLE' 'A1 agent --print on approved personal repos'
  }
} else {
  Add-Cap 'Cursor Agent CLI' 'NOT INSTALLED' 'required for cursor_call (agent --print); cursor.cmd is not this interface'
}

$codex = Find-Cmd @('codex', 'codex.cmd')
if ($codex) {
  $codexAuth = (& codex login status 2>&1 | Out-String)
  if ($codexAuth -match '(?i)logged in') {
    Add-Cap 'Codex CLI' 'AVAILABLE' "$($codex.Source); authenticated"
  } elseif ($codexAuth -match '(?i)not logged|unauthenticated|login required') {
    Add-Cap 'Codex CLI' 'AUTH REQUIRED' "$($codex.Source); run codex login"
  } else {
    Add-Cap 'Codex CLI' 'AVAILABLE' $codex.Source
  }
} else { Add-Cap 'Codex CLI' 'NOT INSTALLED' '' }

$gh = Find-Cmd @('gh')
if ($gh) {
  $auth = (& gh auth status 2>&1 | Out-String)
  if ($auth -match 'Logged in') { Add-Cap 'GitHub CLI' 'AVAILABLE' 'authenticated' }
  else { Add-Cap 'GitHub CLI' 'AUTH REQUIRED' 'gh present, not logged in' }
} else { Add-Cap 'GitHub CLI' 'NOT INSTALLED' '' }

$claudeExe = Find-PathCmd @(
  (Join-Path $env:USERPROFILE '.local\bin\claude.exe'),
  ((Find-Cmd @('claude')) | ForEach-Object { $_.Source })
)
if ($claudeExe) {
  $st = Invoke-CapCmd $claudeExe @('auth','status')
  $ver = Invoke-CapCmd $claudeExe @('--version')
  $verText = if ($ver.text) { $ver.text.Split("`n")[0] } else { 'installed' }
  if ($st.text -match '(?i)"loggedIn"\s*:\s*true|Login method:') {
    Add-Cap 'Claude Code CLI' 'AVAILABLE' "$claudeExe $verText; authenticated"
  } else {
    Add-Cap 'Claude Code CLI' 'AUTH REQUIRED' "$claudeExe $verText; run claude auth login"
  }
} else { Add-Cap 'Claude Code CLI' 'NOT INSTALLED' 'native installer: irm https://claude.ai/install.ps1 | iex' }

$coworkSvc = Get-Service -Name 'CoworkVMService','CoworkVMServiceStore' -ErrorAction SilentlyContinue | Select-Object -First 1
$claudeApp = Get-AppxPackage -Name 'Claude' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($coworkSvc -or $claudeApp) {
  $svcText = if ($coworkSvc) { "$($coworkSvc.Name)=$($coworkSvc.Status)" } else { 'no Cowork service' }
  $appText = if ($claudeApp) { "Claude Desktop $($claudeApp.Version)" } else { 'no Store package' }
  Add-Cap 'Claude Cowork' 'UNSUPPORTED' "$appText; $svcText; desktop GUI only, no NEEWA CLI"
} else {
  Add-Cap 'Claude Cowork' 'UNSUPPORTED' 'desktop GUI feature; no programmable CLI for NEEWA'
}

$geminiCmd = Find-Cmd @('gemini', 'gemini.cmd')
if ($geminiCmd) {
  $oauth = Join-Path $env:USERPROFILE '.gemini\oauth_creds.json'
  $accounts = Join-Path $env:USERPROFILE '.gemini\google_accounts.json'
  if ((Test-Path $oauth) -or (Test-Path $accounts)) {
    Add-Cap 'Gemini CLI' 'PERMISSION REQUIRED' "$($geminiCmd.Source); Google login present, but Gemini CLI is no longer supported for individuals; use Antigravity CLI (agy)"
  } else {
    Add-Cap 'Gemini CLI' 'AUTH REQUIRED' "$($geminiCmd.Source); run gemini and Sign in with Google"
  }
} else { Add-Cap 'Gemini CLI' 'NOT INSTALLED' 'npm install -g @google/gemini-cli' }

$agyExe = Find-PathCmd @(
  (Join-Path $env:LOCALAPPDATA 'agy\bin\agy.exe'),
  ((Find-Cmd @('agy')) | ForEach-Object { $_.Source })
)
if ($agyExe) {
  $ver = Invoke-CapCmd $agyExe @('--version')
  $agyOauth = Join-Path $env:USERPROFILE '.gemini\oauth_creds.json'
  $agyAccounts = Join-Path $env:USERPROFILE '.gemini\google_accounts.json'
  if ((Test-Path $agyOauth) -or (Test-Path $agyAccounts)) {
    Add-Cap 'Antigravity CLI' 'AVAILABLE' "$agyExe $($ver.text); Google credentials present"
  } else {
    Add-Cap 'Antigravity CLI' 'AUTH REQUIRED' "$agyExe $($ver.text); run agy and sign in with Google"
  }
} else { Add-Cap 'Antigravity CLI' 'NOT INSTALLED' 'irm https://antigravity.google/cli/install.ps1 | iex' }

$agIde = Find-Cmd @('antigravity', 'antigravity.cmd')
if ($agIde) {
  Add-Cap 'Antigravity IDE' 'UNSUPPORTED' "$($agIde.Source); IDE launcher, NEEWA uses agy CLI only"
} else {
  Add-Cap 'Antigravity IDE' 'UNSUPPORTED' 'IDE not required for NEEWA CLI workers'
}

$grokCmd = Find-Cmd @('grok', 'grok.cmd')
if ($grokCmd) {
  $grokAuth = Join-Path $env:USERPROFILE '.grok\auth.json'
  if (Test-Path $grokAuth) {
    Add-Cap 'Grok CLI' 'AVAILABLE' "$($grokCmd.Source); auth.json present"
  } else {
    Add-Cap 'Grok CLI' 'AUTH REQUIRED' "$($grokCmd.Source); grok login --oauth (SuperGrok/X Premium+ or XAI_API_KEY may be required)"
  }
} else { Add-Cap 'Grok CLI' 'NOT INSTALLED' 'npm i -g @xai-official/grok' }

$copilotExe = Find-PathCmd @(
  (Join-Path $env:LOCALAPPDATA 'GitHubCopilotCLI\copilot.exe'),
  ((Find-Cmd @('copilot')) | ForEach-Object { $_.Source })
)
if ($copilotExe) {
  $ver = Invoke-CapCmd $copilotExe @('--version')
  $verText = if ($ver.text) { ($ver.text -split "`n")[0] } else { 'installed' }
  Add-Cap 'GitHub Copilot CLI' 'AUTH REQUIRED' "$copilotExe $verText; run copilot login (subscription required)"
} else { Add-Cap 'GitHub Copilot CLI' 'NOT INSTALLED' '' }

$tailscale = Find-Cmd @('tailscale')
if ($tailscale) {
  $st = (& tailscale status --json 2>$null)
  if ($st) { Add-Cap 'Tailscale' 'AVAILABLE' 'status json readable' }
  else { Add-Cap 'Tailscale' 'PERMISSION REQUIRED' 'binary present, status failed' }
} else { Add-Cap 'Tailscale' 'NOT INSTALLED' '' }

$ssh = Find-Cmd @('ssh')
if ($ssh) { Add-Cap 'OpenSSH client' 'AVAILABLE' $ssh.Source } else { Add-Cap 'OpenSSH client' 'NOT INSTALLED' '' }

$personal = Join-Path $env:USERPROFILE 'NEEWA-Personal'
if (Test-Path $personal) { Add-Cap 'Personal workspace' 'AVAILABLE' $personal }
else { Add-Cap 'Personal workspace' 'PERMISSION REQUIRED' "create $personal for scoped worker tasks" }

$workspace = 'C:\Development\Workspace'
if (Test-Path -LiteralPath $workspace) {
  Add-Cap 'Workspace inventory' 'AVAILABLE' 'read-only personal allowlist via workspace_inventory'
} else {
  Add-Cap 'Workspace inventory' 'PERMISSION REQUIRED' $workspace
}

Add-Cap 'Employer files' 'UNSUPPORTED' 'explicitly excluded from the worker allowlist'
Add-Cap 'Unrestricted Windows shell' 'UNSUPPORTED' 'remote model must not receive a raw shell'
Add-Cap 'Public listener' 'UNSUPPORTED' 'outbound/poll only'

$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$report = Join-Path $dir 'capability_inventory.json'
$script:out | ConvertTo-Json -Depth 4 | Set-Content -Path $report -Encoding utf8
$script:out | Format-Table -AutoSize
Write-Output "wrote $report"
