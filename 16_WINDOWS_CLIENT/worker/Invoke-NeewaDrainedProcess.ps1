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
  $proc.EnableRaisingEvents = $true
  $stdout = New-Object System.Collections.Concurrent.ConcurrentQueue[string]
  $stderr = New-Object System.Collections.Concurrent.ConcurrentQueue[string]
  $outSub = Register-ObjectEvent -InputObject $proc -EventName OutputDataReceived -MessageData $stdout -Action {
    $line = $EventArgs.Data
    if ($null -ne $line) { [void]$Event.MessageData.Enqueue([string]$line) }
  }
  $errSub = Register-ObjectEvent -InputObject $proc -EventName ErrorDataReceived -MessageData $stderr -Action {
    $line = $EventArgs.Data
    if ($null -ne $line) { [void]$Event.MessageData.Enqueue([string]$line) }
  }
  $timedOut = $false
  $exitCode = $null
  try {
    [void]$proc.Start()
    $proc.BeginOutputReadLine()
    $proc.BeginErrorReadLine()
    if (-not $proc.WaitForExit($TimeoutMs)) {
      $timedOut = $true
      try { $proc.Kill() } catch { }
    }
    $proc.WaitForExit()
    Start-Sleep -Milliseconds 200
    try { $exitCode = [int]$proc.ExitCode } catch { $exitCode = $null }
  } finally {
    try { $proc.CancelOutputRead() } catch { }
    try { $proc.CancelErrorRead() } catch { }
    Unregister-Event -SourceIdentifier $outSub.Name -ErrorAction SilentlyContinue
    Unregister-Event -SourceIdentifier $errSub.Name -ErrorAction SilentlyContinue
    Remove-Job -Id $outSub.Id, $errSub.Id -Force -ErrorAction SilentlyContinue
    $proc.Dispose()
  }
  $outText = (@($stdout.ToArray()) -join "`n")
  $errText = (@($stderr.ToArray()) -join "`n")
  if ($outText.Length -gt $MaxChars) { $outText = $outText.Substring($outText.Length - $MaxChars) }
  if ($errText.Length -gt $MaxChars) { $errText = $errText.Substring($errText.Length - $MaxChars) }
  return [pscustomobject]@{
    ExitCode = $exitCode
    Stdout = $outText
    Stderr = $errText
    TimedOut = $timedOut
  }
}
