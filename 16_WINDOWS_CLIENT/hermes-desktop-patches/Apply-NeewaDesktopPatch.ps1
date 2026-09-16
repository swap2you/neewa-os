param(
  [string]$DesktopRoot = "$env:LOCALAPPDATA\hermes\hermes-agent\apps\desktop",
  [string]$PackedResources = "$env:LOCALAPPDATA\hermes\hermes-agent\apps\desktop\release\win-unpacked\resources"
)

$ErrorActionPreference = 'Stop'
$asar = Join-Path $PackedResources 'app.asar'
$backup = Join-Path $PackedResources ("app.asar.bak-neewa-" + (Get-Date -Format 'yyyyMMddTHHmmss'))
if (-not (Test-Path $asar)) { throw "missing $asar" }
Copy-Item $asar $backup
Write-Output "backup $backup"

Push-Location $DesktopRoot
try {
  npm run build
} finally {
  Pop-Location
}

$npx = Get-Command npx -ErrorAction SilentlyContinue
if (-not $npx) { throw 'npx not found; cannot pack app.asar' }
Push-Location $DesktopRoot
try {
  npx --yes asar pack dist (Join-Path $PackedResources 'app.asar.new')
} finally {
  Pop-Location
}

# asar pack of dist-only is wrong if original asar includes electron-main.
# Prefer replacing renderer files inside the existing asar.
$extract = Join-Path $env:TEMP 'neewa-app-asar'
if (Test-Path $extract) { Remove-Item $extract -Recurse -Force }
# Extract the LIVE app.asar (do not rename first — asar looks for app.asar.unpacked).
$extract = Join-Path $env:TEMP 'neewa-app-asar-clean'
if (Test-Path $extract) { Remove-Item $extract -Recurse -Force }
npx --yes asar extract $asar $extract
$distSrc = Join-Path $DesktopRoot 'dist'
if (-not (Test-Path $distSrc)) { throw 'vite dist missing after build' }
$distDst = Join-Path $extract 'dist'
robocopy $distSrc $distDst /E /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
$newAsar = Join-Path $PackedResources 'app.asar.neewa'
npx --yes asar pack $extract $newAsar --unpack-dir "{**/node_modules/node-pty/**,**/node_modules/get-windows/**}"
Copy-Item -Force $newAsar $asar
Write-Output "packed $asar"
$newAsar = Join-Path $PackedResources 'app.asar'
npx --yes asar pack $extract $newAsar
Write-Output "packed $newAsar"
Write-Output 'Quit Hermes Desktop completely, then relaunch packed Hermes.exe'
