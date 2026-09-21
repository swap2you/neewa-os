# Outbound poller. No listener. One instance via a named mutex.
[CmdletBinding()]
param(
  [switch]$Once,
  [string]$RemoteHost = 'ubuntu@neewa-core-01',
  [string]$RemoteInbox = '/home/ubuntu/.hermes/sandboxes/docker/default/workspace/windows-jobs'
)
$ErrorActionPreference = 'Stop'
$created = $false
$mutex = New-Object System.Threading.Mutex($true, 'Local\NEEWA-WindowsWorker', [ref]$created)
if (-not $created) {
  Write-Output 'another NEEWA Windows worker is already running'
  exit 0
}
try {
  $here = Split-Path -Parent $MyInvocation.MyCommand.Path
  $invoke = Join-Path $here 'Invoke-NeewaWindowsJob.ps1'
  . (Join-Path $here 'Resolve-NeewaResultFolder.ps1')
  $localInbox = Join-Path $env:USERPROFILE 'NEEWA-Personal\inbox'
  $logDir = Join-Path $env:LOCALAPPDATA 'NEEWA\logs'
  New-Item -ItemType Directory -Force -Path $localInbox, $logDir | Out-Null
  $pollLog = Join-Path $logDir 'worker-poll.log'
  function Write-Poll([string]$Message) {
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-ddTHH:mm:ssK'), $Message
    Add-Content -LiteralPath $pollLog -Value $line -Encoding utf8
    Write-Output $line
  }
  $sshOpts = @('-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', '-o', 'LogLevel=ERROR')

  function Receive-RemoteJobs {
    $tmp = Join-Path $env:TEMP 'neewa-windows-jobs'
    New-Item -ItemType Directory -Force -Path $tmp | Out-Null
    & ssh @sshOpts $RemoteHost "mkdir -p $RemoteInbox/inbox $RemoteInbox/processing $RemoteInbox/done $RemoteInbox/failed; ls -1 $RemoteInbox/inbox/*.json 2>/dev/null" |
      ForEach-Object {
        $line = ([string]$_).Trim()
        if ($line -notmatch '\.json$') { return }
        $name = Split-Path -Leaf $line
        if ($name -notmatch '^[A-Za-z0-9._-]+\.json$') { return }
        $local = Join-Path $localInbox $name
        & scp @sshOpts "${RemoteHost}:$RemoteInbox/inbox/$name" $local | Out-Null
        & ssh @sshOpts $RemoteHost "mv $RemoteInbox/inbox/$name $RemoteInbox/processing/$name"
        Write-Poll "claimed $name"
      }
  }

  function Submit-RemoteResult($jobFile, $result) {
    $name = Split-Path -Leaf $jobFile
    if ($result -is [System.Array]) {
      $result = @($result | Where-Object { $_ -ne $null } | Select-Object -Last 1)
      if ($result.Count -eq 1) { $result = $result[0] }
    }
    if ($result -is [string]) {
      try { $result = $result | ConvertFrom-Json } catch { }
    }
    $payload = $result | ConvertTo-Json -Depth 8 -Compress
    $destDir = Resolve-NeewaResultFolder $result
    $remoteJson = "$RemoteInbox/$destDir/$name"
    $payload | & ssh @sshOpts $RemoteHost "cat > $remoteJson"
    if ($result.artifact -and (Test-Path -LiteralPath $result.artifact)) {
      $leaf = Split-Path -Leaf $result.artifact
      & scp @sshOpts $result.artifact "${RemoteHost}:$RemoteInbox/$destDir/$leaf" | Out-Null
    }
    & ssh @sshOpts $RemoteHost "rm -f $RemoteInbox/processing/$name"
  }

  function Invoke-Pending {
    $jobsDir = Join-Path $env:USERPROFILE 'NEEWA-Personal\jobs'
    Get-ChildItem -LiteralPath $localInbox -Filter '*.json' -ErrorAction SilentlyContinue |
      Sort-Object LastWriteTime -Descending |
      ForEach-Object {
        $stamp = Join-Path $jobsDir ($_.BaseName + '.done.json')
        if (Test-Path -LiteralPath $stamp) {
          Write-Poll "skip already-done $($_.Name)"
          Remove-Item -LiteralPath $_.FullName -Force
          return
        }
        Write-Poll "invoke $($_.Name)"
        $result = & $invoke -JobPath $_.FullName
        Write-Output ($result | ConvertTo-Json -Compress)
        try { Submit-RemoteResult $_.FullName $result } catch { Write-Poll "remote result push failed: $($_.Exception.Message)" }
        Remove-Item -LiteralPath $_.FullName -Force
      }
  }

  do {
    try { Receive-RemoteJobs } catch { Write-Poll "poll skipped: $($_.Exception.Message)" }
    Invoke-Pending
    if (-not $Once) { Start-Sleep -Seconds 15 }
  } while (-not $Once)
}
finally {
  $mutex.ReleaseMutex() | Out-Null
  $mutex.Dispose()
}
