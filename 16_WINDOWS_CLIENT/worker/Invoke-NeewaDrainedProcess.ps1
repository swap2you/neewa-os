# Concurrent stdout/stderr drain. Dot-source safe. No param() block.
# A redirected child that fills either pipe must not deadlock the parent.

function Invoke-NeewaDrainedProcess {
  param(
    [Parameter(Mandatory)]$StartInfo,
    [int]$TimeoutMs = 20000,
    [int]$MaxChars = 200000
  )
  $proc = New-Object System.Diagnostics.Process
  $proc.StartInfo = $StartInfo
  $timedOut = $false
  $exitCode = $null
  $outText = ''
  $errText = ''
  try {
    [void]$proc.Start()
    $stdoutTask = $proc.StandardOutput.ReadToEndAsync()
    $stderrTask = $proc.StandardError.ReadToEndAsync()
    if (-not $proc.WaitForExit($TimeoutMs)) {
      $timedOut = $true
      try { $proc.Kill() } catch { }
    }
    $proc.WaitForExit()
    try { $outText = [string]$stdoutTask.GetAwaiter().GetResult() } catch { $outText = '' }
    try { $errText = [string]$stderrTask.GetAwaiter().GetResult() } catch { $errText = '' }
    try { $exitCode = [int]$proc.ExitCode } catch { $exitCode = $null }
  } finally {
    $proc.Dispose()
  }
  if ($outText.Length -gt $MaxChars) { $outText = $outText.Substring($outText.Length - $MaxChars) }
  if ($errText.Length -gt $MaxChars) { $errText = $errText.Substring($errText.Length - $MaxChars) }
  return [pscustomobject]@{
    ExitCode = $exitCode
    Stdout = $outText
    Stderr = $errText
    TimedOut = $timedOut
  }
}
