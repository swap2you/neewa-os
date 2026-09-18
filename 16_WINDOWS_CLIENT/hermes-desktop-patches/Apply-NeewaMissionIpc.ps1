# Apply the NEEWA Home mission IPC onto the installed Hermes Desktop source.
# Does not open a public listener. Restart packed Hermes.exe after packing.
param(
  [string]$DesktopRoot = "$env:LOCALAPPDATA\hermes\hermes-agent\apps\desktop",
  [switch]$Build
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$src = Join-Path $here 'electron\neewa-mission-ipc.ts'
$dstDir = Join-Path $DesktopRoot 'electron'
$dst = Join-Path $dstDir 'neewa-mission-ipc.ts'
if (-not (Test-Path $src)) { throw "missing $src" }
if (-not (Test-Path $dstDir)) { throw "missing Hermes electron dir $dstDir" }
Copy-Item -Force $src $dst
Write-Output "copied $dst"

$main = Join-Path $dstDir 'main.ts'
$preload = Join-Path $dstDir 'preload.ts'
$mainText = Get-Content -Raw -LiteralPath $main
if ($mainText -notmatch 'registerNeewaMissionIpc') {
  $mainText = $mainText.Replace(
    "import { registerHudIpc } from './hud-ipc'",
    "import { registerHudIpc } from './hud-ipc'`r`nimport { registerNeewaMissionIpc } from './neewa-mission-ipc'"
  )
  $needle = "const hudIpc = registerHudIpc({"
  $insert = "registerNeewaMissionIpc()`r`n`r`nconst hudIpc = registerHudIpc({"
  if ($mainText -notmatch [regex]::Escape($needle)) { throw 'hudIpc registration site not found in main.ts' }
  $mainText = $mainText.Replace($needle, $insert)
  Set-Content -LiteralPath $main -Value $mainText -Encoding utf8
  Write-Output 'patched electron/main.ts'
} else {
  Write-Output 'main.ts already registers NEEWA mission IPC'
}

$preloadText = Get-Content -Raw -LiteralPath $preload
$neewaBlock = @'
  neewa: {
    submitMission: payload => ipcRenderer.invoke('hermes:neewa:mission', { command: 'submit', origin: 'home', ...(payload || {}) }),
    missionStatus: payload => ipcRenderer.invoke('hermes:neewa:mission', { command: 'status', ...(payload || {}) })
  },
'@
if ($preloadText -notmatch 'hermes:neewa:mission') {
  $mark = '  hud: {'
  if ($preloadText -notmatch [regex]::Escape($mark)) { throw 'hud block not found in preload.ts' }
  $preloadText = $preloadText.Replace($mark, $neewaBlock + "`r`n" + $mark)
  Set-Content -LiteralPath $preload -Value $preloadText -Encoding utf8
  Write-Output 'patched electron/preload.ts'
} else {
  Write-Output 'preload.ts already exposes hermesDesktop.neewa'
}

if ($Build) {
  Push-Location $DesktopRoot
  try { npm run build } finally { Pop-Location }
}
Write-Output 'NEEWA mission IPC source is installed. Rebuild/pack Hermes Desktop, then relaunch Hermes.exe.'
