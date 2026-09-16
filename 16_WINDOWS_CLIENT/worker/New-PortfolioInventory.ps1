# Read-only generator for approved personal NEEWA project folders.
# Does not open financial accounts, employer trees, or credential stores.
$ErrorActionPreference = 'Stop'
$outDir = Join-Path $env:USERPROFILE 'NEEWA-Personal\inventory'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$repo = 'C:\Development\Workspace\NEEWA-OS'
$projectsRoot = Join-Path $repo '08_PROJECTS'
$registry = Get-Content -Raw (Join-Path $repo '11_CONFIG\projects.json') | ConvertFrom-Json
$rows = @()
foreach ($p in $registry.projects) {
  $folder = Join-Path $repo ($p.path -replace '/', '\')
  $exists = Test-Path $folder
  $docs = @()
  $tests = $false
  $statusFile = $null
  if ($exists) {
    $docs = @(Get-ChildItem $folder -File -ErrorAction SilentlyContinue | ForEach-Object Name)
    $statusFile = if (Test-Path (Join-Path $folder 'STATUS.md')) { 'STATUS.md' } elseif (Test-Path (Join-Path $folder 'PROJECT.md')) { 'PROJECT.md' } else { $null }
  }
  $rows += [pscustomobject]@{
    name = $p.name
    id = $p.id
    registry_status = $p.status
    path = $p.path
    folder_exists = $exists
    documents = $docs
    implementation_status = if ($p.id -eq 'PRJ-NEEWA' -and $exists) { 'active in this repository' } elseif ($exists) { 'defined documentation only; not treated as a complete product' } else { 'missing on disk' }
    tests = 'not claimed from registry'
    build_status = 'not built from this inventory'
    deployment = 'not started by this inventory'
    unfinished_work = if ($p.id -eq 'PRJ-NEEWA') { 'physical voice acceptance; Windows computer-use worker; A2/A3 integrations' } else { 'not implemented as a live codebase in this repo beyond PROJECT.md' }
  }
}
$report = [pscustomobject]@{
  generated_at = [DateTime]::UtcNow.ToString('o')
  scope = @('C:\Development\Workspace\NEEWA-OS\08_PROJECTS', '%USERPROFILE%\NEEWA-Personal')
  excluded = @('employer trees', 'financial accounts', 'credential stores', 'unrelated private files')
  projects = $rows
}
$path = Join-Path $outDir 'portfolio-inventory.json'
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $path -Encoding utf8
Write-Output $path
