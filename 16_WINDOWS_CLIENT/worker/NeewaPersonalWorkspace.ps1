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

function Get-ApprovedRoots {
  $roots = New-Object System.Collections.Generic.List[string]
  function Add-Root([string]$value) {
    if (-not $value) { return }
    $full = [System.IO.Path]::GetFullPath((Expand-UserPath $value))
    if (-not ($roots -contains $full)) { [void]$roots.Add($full) }
  }
  Add-Root ([string]$policy.sandbox_repo)
  foreach ($item in @($policy.personal_roots)) { Add-Root ([string]$item) }
  Add-Root ([string]$policy.workspace_root)
  return @($roots)
}

function Get-ImplementationArtifacts([string]$dir) {
  if (-not (Test-Path -LiteralPath $dir)) { return @() }
  $ignore = @('.gitkeep', '.gitignore', 'Thumbs.db', '.DS_Store')
  $found = @()
  Get-ChildItem -LiteralPath $dir -Force -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
    $_.FullName -notmatch '\\.git\\' -and ($ignore -notcontains $_.Name)
  } | ForEach-Object { $found += $_.FullName }
  return $found
}

function Invoke-ProductUnittest {
  param(
    [string]$Repo,
    [string]$TestCommand = 'python -m unittest'
  )
  $result = [ordered]@{
    command = $TestCommand
    cwd = $Repo
    exit_code = $null
    passed = $false
    stdout = ''
    stderr = ''
    failure_class = $null
  }
  if ($TestCommand -notmatch '^python(?:3)?\s+-m\s+unittest\b') {
    $result.stderr = "test command is not allowlisted: $TestCommand"
    $result.failure_class = 'UNAPPROVED_TEST_COMMAND'
    return [pscustomobject]$result
  }
  $py = Get-Command python -ErrorAction SilentlyContinue
  if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
  if (-not $py) {
    $result.stderr = 'python interpreter is not installed'
    $result.failure_class = 'PYTHON_MISSING'
    return [pscustomobject]$result
  }
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $py.Source
  $psi.WorkingDirectory = $Repo
  $psi.UseShellExecute = $false
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.CreateNoWindow = $true
  $argListProp = $psi.GetType().GetProperty('ArgumentList')
  if ($argListProp) {
    [void]$psi.ArgumentList.Add('-m')
    [void]$psi.ArgumentList.Add('unittest')
  } else {
    $psi.Arguments = '-m unittest'
  }
  $proc = New-Object System.Diagnostics.Process
  $proc.StartInfo = $psi
  [void]$proc.Start()
  $stdout = $proc.StandardOutput.ReadToEnd()
  $stderr = $proc.StandardError.ReadToEnd()
  [void]$proc.WaitForExit()
  $result.exit_code = [int]$proc.ExitCode
  $result.stdout = [string]$stdout
  $result.stderr = [string]$stderr
  $result.passed = ($proc.ExitCode -eq 0)
  return [pscustomobject]$result
}

function Invoke-ProjectBootstrap {
  param(
    [string]$Repo,
    [string]$Lifecycle = 'modify_existing',
    [string]$WorkspaceRoot = '',
    [string]$ExecutionPhase = 'implementation',
    [bool]$BootstrapComplete = $false,
    [string[]]$ExpectedPaths = @(),
    [string]$ImplementationRepo = '',
    [bool]$ImplementationCompleted = $false
  )
  if ([System.IO.File]::Exists($Repo)) {
    return [pscustomobject]@{
      lifecycle = $Lifecycle
      execution_phase = $ExecutionPhase
      target_path = $Repo
      workspace_root = $WorkspaceRoot
      target_directory_state = 'nonempty'
      bootstrap_result = 'rejected_nonempty'
      parent_exists = $false
      created = $false
      identity_ok = $false
      git_required = ($Lifecycle -eq 'modify_existing')
      reason = "project path exists as a file: $Repo"
      failure_class = 'PROJECT_ALREADY_EXISTS'
    }
  }
  $exists = [System.IO.Directory]::Exists($Repo)
  $artifacts = @()
  if ($exists) { $artifacts = @(Get-ImplementationArtifacts $Repo) }
  $state = if (-not $exists) { 'missing' } elseif ($artifacts.Count -gt 0) { 'nonempty' } else { 'empty' }
  $result = [ordered]@{
    lifecycle = $Lifecycle
    execution_phase = $ExecutionPhase
    target_path = $Repo
    workspace_root = $WorkspaceRoot
    target_directory_state = $state
    bootstrap_result = 'none'
    parent_exists = $false
    created = $false
    identity_ok = $false
    git_required = ($Lifecycle -eq 'modify_existing' -and $ExecutionPhase -ne 'independent_validation')
    reason = $null
    failure_class = $null
  }
  $parent = [System.IO.Path]::GetDirectoryName($Repo.TrimEnd('\', '/'))
  $result.parent_exists = [bool]($parent -and [System.IO.Directory]::Exists($parent))
  if ($ExecutionPhase -eq 'independent_validation') {
    if (-not $ImplementationCompleted) {
      $result.reason = 'independent validation requires a completed implementation child'
      $result.failure_class = 'INCOMPLETE_IMPLEMENTATION'
      return [pscustomobject]$result
    }
    if ($ImplementationRepo) {
      $want = [System.IO.Path]::GetFullPath($ImplementationRepo)
      $have = [System.IO.Path]::GetFullPath($Repo)
      if (-not $have.Equals($want, [System.StringComparison]::OrdinalIgnoreCase)) {
        $result.reason = "canonical project path does not match implementation path: $Repo"
        $result.failure_class = 'PROJECT_PATH_MISMATCH'
        return [pscustomobject]$result
      }
    }
    if (-not $exists) {
      $result.reason = "approved repo path is missing: $Repo"
      $result.failure_class = 'MISSING_REPO'
      return [pscustomobject]$result
    }
    $missing = @()
    foreach ($rel in @($ExpectedPaths)) {
      $item = [string]$rel
      if (-not $item) { continue }
      if ($item -match '\.\.') {
        $result.reason = 'path traversal is not allowed'
        $result.failure_class = 'PATH_TRAVERSAL'
        return [pscustomobject]$result
      }
      $full = [System.IO.Path]::GetFullPath((Join-Path $Repo $item))
      $rootPrefix = $Repo.TrimEnd('\') + '\'
      if (-not $full.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        $result.reason = "expected path escapes the approved repository: $item"
        $result.failure_class = 'PATH_ESCAPE'
        return [pscustomobject]$result
      }
      if (-not [System.IO.File]::Exists($full) -and -not [System.IO.Directory]::Exists($full)) {
        $missing += $item
      }
    }
    if ((@($ExpectedPaths) | Where-Object { $_ }).Count -gt 0 -and $missing.Count -gt 0) {
      $result.reason = 'missing implementation artifacts: ' + ($missing -join ', ')
      $result.failure_class = 'MISSING_IMPLEMENTATION_ARTIFACTS'
      return [pscustomobject]$result
    }
    if ((@($ExpectedPaths) | Where-Object { $_ }).Count -eq 0 -and $state -ne 'nonempty') {
      $result.reason = "independent validation requires implementation artifacts: $Repo"
      $result.failure_class = 'MISSING_IMPLEMENTATION_ARTIFACTS'
      return [pscustomobject]$result
    }
    $result.bootstrap_result = 'validation_existing'
    $result.identity_ok = $true
    return [pscustomobject]$result
  }
  if ($Lifecycle -ne 'create_new') {
    if (-not $exists) {
      $result.reason = "approved repo path is missing: $Repo"
      $result.failure_class = 'MISSING_REPO'
      return [pscustomobject]$result
    }
    $result.bootstrap_result = 'existing_reused'
    $result.identity_ok = $true
    return [pscustomobject]$result
  }
  if ($Repo -match '\.\.') {
    $result.reason = 'path traversal is not allowed'
    $result.failure_class = 'PATH_TRAVERSAL'
    return [pscustomobject]$result
  }
  if ($BootstrapComplete) {
    if (-not $exists) {
      $result.reason = "approved repo path is missing after bootstrap: $Repo"
      $result.failure_class = 'MISSING_REPO'
      return [pscustomobject]$result
    }
    $result.bootstrap_result = 'existing_reused'
    $result.identity_ok = $true
    return [pscustomobject]$result
  }
  if (-not $result.parent_exists) {
    $result.reason = "parent workspace does not exist: $parent"
    $result.failure_class = 'MISSING_WORKSPACE_ROOT'
    return [pscustomobject]$result
  }
  try {
    $probe = Join-Path $parent ('.neewa-write-probe-' + [guid]::NewGuid().ToString('n'))
    [System.IO.File]::WriteAllText($probe, '')
    [System.IO.File]::Delete($probe)
  } catch {
    $result.reason = "parent workspace is not writable: $parent"
    $result.failure_class = 'WORKSPACE_NOT_WRITABLE'
    return [pscustomobject]$result
  }
  if ($state -eq 'nonempty') {
    $result.reason = "project already contains implementation artifacts: $Repo"
    $result.failure_class = 'PROJECT_ALREADY_EXISTS'
    $result.bootstrap_result = 'rejected_nonempty'
    return [pscustomobject]$result
  }
  if ($state -eq 'missing') {
    $created = [System.IO.Directory]::CreateDirectory($Repo)
    if (-not $created.Exists) {
      $result.reason = "failed to create project directory: $Repo"
      $result.failure_class = 'BOOTSTRAP_CREATE_FAILED'
      return [pscustomobject]$result
    }
    $result.created = $true
    $result.bootstrap_result = 'created'
    $result.target_directory_state = 'empty'
  } else {
    $result.bootstrap_result = 'reused_empty'
  }
  $result.identity_ok = $true
  return [pscustomobject]$result
}

function Resolve-ApprovedRepo([string]$requested) {
  if (-not $requested) { return $null }
  if ($requested -match '\.\.') { return $null }
  $workspaceRoot = $null
  if ($policy.workspace_root) {
    $workspaceRoot = [System.IO.Path]::GetFullPath([string]$policy.workspace_root)
  }
  $fullRequested = [System.IO.Path]::GetFullPath($requested)
  if (Test-DeniedRepoPath $fullRequested) { return $null }

  $roots = @(Get-ApprovedRoots)
  foreach ($root in $roots) {
    $prefix = $root.TrimEnd('\') + '\'
    $isExact = $fullRequested.Equals($root, [System.StringComparison]::OrdinalIgnoreCase)
    $isChild = $fullRequested.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)
    if (-not ($isExact -or $isChild)) { continue }
    if ($workspaceRoot -and $fullRequested.Equals($workspaceRoot, [System.StringComparison]::OrdinalIgnoreCase)) { return $null }
    if (Test-ReparseEscape $fullRequested $root) { return $null }
    return $fullRequested
  }
  return $null
}
