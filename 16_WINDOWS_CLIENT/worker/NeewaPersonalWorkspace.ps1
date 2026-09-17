# Shared personal-workspace authorization for the Windows worker.
# Deny-list model: any folder under the owner's personal roots is in-scope
# unless it is an explicit employer/client/trading/secrets exclusion.
# Dot-source after $policy is loaded from cursor-call-policy.json.
function Expand-UserPath([string]$value) {
  if (-not $value) { return $value }
  return [Environment]::ExpandEnvironmentVariables($value)
}

function Test-DeniedRepoName([string]$name) {
  if (-not $name) { return $false }
  foreach ($denied in @($policy.denied_name_equals)) {
    if ($name.Equals($denied, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
  }
  foreach ($frag in @($policy.denied_name_contains)) {
    if ($frag -and $name.ToLowerInvariant().Contains($frag.ToLowerInvariant())) { return $true }
  }
  return $false
}

function Test-DeniedRepoPath([string]$fullPath) {
  if (-not $fullPath) { return $true }
  $parts = $fullPath.TrimEnd('\', '/').Split([char[]]@('\', '/'))
  foreach ($part in $parts) {
    if (Test-DeniedRepoName $part) { return $true }
  }
  $lower = $fullPath.ToLowerInvariant()
  foreach ($secret in @('\.ssh', '\.aws', '\.gnupg')) {
    if ($lower.Contains($secret)) { return $true }
  }
  return $false
}

function Test-ReparseEscape([string]$path, [string]$approvedRoot) {
  if (-not (Test-Path -LiteralPath $path)) { return $false }
  $item = Get-Item -LiteralPath $path -Force
  if (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { return $false }
  $targets = @($item.Target)
  foreach ($t in $targets) {
    if (-not $t) { continue }
    $fullTarget = [System.IO.Path]::GetFullPath($t)
    $root = $approvedRoot.TrimEnd('\') + '\'
    if (-not $fullTarget.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase) -and
        -not $fullTarget.Equals($approvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
      return $true
    }
  }
  return $false
}

function Resolve-ApprovedRepo([string]$requested) {
  if (-not $requested) { return $null }
  if ($requested -match '\.\.') { return $null }
  $workspaceRoot = [System.IO.Path]::GetFullPath([string]$policy.workspace_root)
  $sandbox = Expand-UserPath ([string]$policy.sandbox_repo)
  $personalHome = Expand-UserPath('%USERPROFILE%\NEEWA-Personal')
  $fullRequested = [System.IO.Path]::GetFullPath($requested)
  if (Test-DeniedRepoPath $fullRequested) { return $null }

  $roots = @()
  if ($sandbox) { $roots += [System.IO.Path]::GetFullPath($sandbox) }
  if ($personalHome) { $roots += [System.IO.Path]::GetFullPath($personalHome) }
  if ($workspaceRoot) { $roots += $workspaceRoot }

  foreach ($root in $roots) {
    $prefix = $root.TrimEnd('\') + '\'
    $isExact = $fullRequested.Equals($root, [System.StringComparison]::OrdinalIgnoreCase)
    $isChild = $fullRequested.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)
    if (-not ($isExact -or $isChild)) { continue }
    # The Workspace drive root is not itself a project (it also contains exclusions).
    if ($fullRequested.Equals($workspaceRoot, [System.StringComparison]::OrdinalIgnoreCase)) { return $null }
    if (Test-ReparseEscape $fullRequested $root) { return $null }
    return $fullRequested
  }
  return $null
}
