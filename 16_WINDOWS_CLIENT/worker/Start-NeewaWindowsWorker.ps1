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
  $localInbox = Join-Path $env:USERPROFILE 'NEEWA-Personal\inbox'
  New-Item -ItemType Directory -Force -Path $localInbox | Out-Null

  function Receive-RemoteJobs {
    $tmp = Join-Path $env:TEMP 'neewa-windows-jobs'
    New-Item -ItemType Directory -Force -Path $tmp | Out-Null
    ssh -o BatchMode=yes -o ConnectTimeout=8 $RemoteHost "mkdir -p $RemoteInbox/inbox $RemoteInbox/processing $RemoteInbox/done $RemoteInbox/failed; ls -1 $RemoteInbox/inbox/*.json 2>/dev/null" | ForEach-Object {
      $name = Split-Path -Leaf $_.Trim()
      if (-not $name) { return }
      $local = Join-Path $localInbox $name
      scp -o BatchMode=yes -o ConnectTimeout=8 "${RemoteHost}:$RemoteInbox/inbox/$name" $local | Out-Null
      ssh -o BatchMode=yes $RemoteHost "mv $RemoteInbox/inbox/$name $RemoteInbox/processing/$name"
    }
  }

  function Submit-RemoteResult($jobFile, $result) {
    $name = Split-Path -Leaf $jobFile
    $payload = $result | ConvertTo-Json -Depth 6 -Compress
    $destDir = if ($result.status -eq 'complete') { 'done' } else { 'failed' }
    $remoteJson = "$RemoteInbox/$destDir/$name"
    $payload | ssh -o BatchMode=yes $RemoteHost "cat > $remoteJson"
    if ($result.artifact -and (Test-Path -LiteralPath $result.artifact)) {
      $leaf = Split-Path -Leaf $result.artifact
      scp -o BatchMode=yes $result.artifact "${RemoteHost}:$RemoteInbox/$destDir/$leaf" | Out-Null
    }
    ssh -o BatchMode=yes $RemoteHost "rm -f $RemoteInbox/processing/$name"
  }

  function Invoke-Pending {
    Get-ChildItem -LiteralPath $localInbox -Filter '*.json' -ErrorAction SilentlyContinue | ForEach-Object {
      $result = & $invoke -JobPath $_.FullName
      Write-Output ($result | ConvertTo-Json -Compress)
      try { Submit-RemoteResult $_.FullName $result } catch { Write-Output "remote result push failed: $($_.Exception.Message)" }
      Remove-Item -LiteralPath $_.FullName -Force
    }
  }

  do {
    try { Receive-RemoteJobs } catch { Write-Output "poll skipped: $($_.Exception.Message)" }
    Invoke-Pending
    if (-not $Once) { Start-Sleep -Seconds 15 }
  } while (-not $Once)
}
finally {
  $mutex.ReleaseMutex() | Out-Null
  $mutex.Dispose()
}
