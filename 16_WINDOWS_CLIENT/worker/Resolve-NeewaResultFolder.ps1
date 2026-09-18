# Map a Windows-worker result object to the remote inbox folder.
# COMPLETED belongs in done/ (harvested as success). BLOCKED/FAILED stay in failed/.
# Historical receipts are not rewritten.
function Resolve-NeewaResultFolder {
  param($Result)
  if ($null -eq $Result) { return 'failed' }
  if ($Result -is [System.Array]) {
    $Result = @($Result | Where-Object { $_ -ne $null } | Select-Object -Last 1)
    if ($Result.Count -eq 1) { $Result = $Result[0] }
  }
  if ($Result -is [string]) {
    $text = $Result.Trim()
    if (-not $text) { return 'failed' }
    try { $Result = $text | ConvertFrom-Json } catch { return 'failed' }
  }
  $status = ''
  try { $status = [string]$Result.status } catch { $status = '' }
  if ($status -in @('complete', 'COMPLETED')) { return 'done' }
  return 'failed'
}

if ($MyInvocation.InvocationName -eq '.') { return }
if ($args.Count -ge 1) {
  Write-Output (Resolve-NeewaResultFolder ($args[0] | ConvertFrom-Json))
}
