# Governed read-only inventory of personal projects under C:\Development\Workspace.
# Metadata only. No file contents. No employer / financial / credential trees.
# Writes only under %USERPROFILE%\NEEWA-Personal\inventory.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$policyPath = Join-Path $here 'workspace-inventory-policy.json'
$policy = Get-Content -Raw -LiteralPath $policyPath | ConvertFrom-Json
$root = [string]$policy.workspace_root
if (-not $root -or -not (Test-Path -LiteralPath $root)) {
  throw "workspace root is missing or unreadable: $root"
}

$personal = @($policy.personal_projects)
$deniedEquals = @($policy.denied_name_equals)
$deniedContains = @($policy.denied_name_contains)
$skipFiles = @($policy.skip_file_names)
$skipDirs = @($policy.skip_dir_names)

function Get-Classification([string]$name) {
  if ($deniedEquals -contains $name) { return 'denied' }
  foreach ($frag in $deniedContains) {
    if ($frag -and $name.ToLowerInvariant().Contains($frag.ToLowerInvariant())) { return 'denied' }
  }
  return 'personal'
}

$entries = @()
Get-ChildItem -LiteralPath $root -Directory -Force -ErrorAction Stop | ForEach-Object {
  $name = $_.Name
  $cls = Get-Classification $name
  $row = [ordered]@{
    name = $name
    classification = $cls
    inventoried = $false
  }
  if ($cls -eq 'personal') {
    $git = Test-Path -LiteralPath (Join-Path $_.FullName '.git')
    $children = @(
      Get-ChildItem -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue |
        Where-Object {
          $skipFiles -notcontains $_.Name -and
          -not ($_.PSIsContainer -and $skipDirs -contains $_.Name)
        } |
        Select-Object -First 40 |
        ForEach-Object { $_.Name }
    )
    $statusDoc = $null
    foreach ($doc in @('STATUS.md', 'PROJECT.md', 'README.md')) {
      if (Test-Path -LiteralPath (Join-Path $_.FullName $doc)) { $statusDoc = $doc; break }
    }
    $row.path = $_.FullName
    $row.last_write_utc = $_.LastWriteTimeUtc.ToString('o')
    $row.is_git = $git
    $row.status_doc = $statusDoc
    $row.top_level = $children
    $row.inventoried = $true
    $row.catalogued = $personal -contains $name
    if ($children -contains '.git') { throw 'inventory leaked .git internals' }
  }
  elseif ($cls -eq 'denied') {
    $row.reason = 'employer, financial, or trading tree excluded'
  }
  $entries += [pscustomobject]$row
}

foreach ($expected in $personal) {
  if (-not ($entries | Where-Object { $_.name -eq $expected })) {
    $entries += [pscustomobject][ordered]@{
      name = $expected
      classification = 'personal'
      inventoried = $false
      reason = 'allowlisted personal project missing on disk'
    }
  }
}

$outDir = Join-Path $env:USERPROFILE 'NEEWA-Personal\inventory'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$report = [pscustomobject]@{
  generated_at = [DateTime]::UtcNow.ToString('o')
  mode = 'read_only_metadata'
  workspace_root = $root
  personal_allowlist = $personal
  authorization_mode = 'personal_roots_except_denied'
  denied_equals = $deniedEquals
  write_access = $false
  unrestricted_desktop = $false
  file_contents_read = $false
  projects = $entries
}
$path = Join-Path $outDir 'workspace-inventory.json'
[System.IO.File]::WriteAllText($path, ($report | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
Write-Output $path
