# Outbound poller. No listener. One instance via a named mutex.
# Completed results stay in a local outbox until the remote file is acknowledged.
[CmdletBinding()]
param(
  [switch]$Once,
  [string]$RemoteHost = 'ubuntu@neewa-core-01',
  [string]$RemoteInbox = '/home/ubuntu/.hermes/sandboxes/docker/default/workspace/windows-jobs'
)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
if (-not (Get-Command Resolve-NeewaResultFolder -ErrorAction SilentlyContinue)) {
  . (Join-Path $PSScriptRoot 'Resolve-NeewaResultFolder.ps1')
}
$sshOpts = @(
  '-o', 'BatchMode=yes',
  '-o', 'ConnectTimeout=8',
  '-o', 'ServerAliveInterval=2',
  '-o', 'ServerAliveCountMax=3',
  '-o', 'LogLevel=ERROR'
)
if (-not $script:NeewaOutbox) {
  $script:NeewaOutbox = Join-Path $env:LOCALAPPDATA 'NEEWA\outbox'
}

function Write-Poll([string]$Message) {
  $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-ddTHH:mm:ssK'), $Message
  if ($script:NeewaPollLog) {
    Add-Content -LiteralPath $script:NeewaPollLog -Value $line -Encoding utf8
  }
  Write-Output $line
}

function Resolve-NeewaExecutable([string]$Name) {
  $cmd = Get-Command $Name -ErrorAction SilentlyContinue
  if ($cmd -and $cmd.Source) { return [string]$cmd.Source }
  return $Name
}

function Invoke-NeewaBoundedProcess {
  param(
    [Parameter(Mandatory)][string]$FileName,
    [Parameter(Mandatory)][string[]]$ArgumentList,
    [int]$TimeoutSec = 20
  )
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $FileName
  $psi.UseShellExecute = $false
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.CreateNoWindow = $true
  $argListProp = $psi.GetType().GetProperty('ArgumentList')
  if ($argListProp) {
    foreach ($a in $ArgumentList) { [void]$psi.ArgumentList.Add([string]$a) }
  } else {
    $psi.Arguments = (($ArgumentList | ForEach-Object {
      $s = [string]$_
      if ($s -match '[\s"]') { '"' + ($s -replace '"', '\"') + '"' } else { $s }
    }) -join ' ')
  }
  $proc = New-Object System.Diagnostics.Process
  $proc.StartInfo = $psi
  [void]$proc.Start()
  if (-not $proc.WaitForExit($TimeoutSec * 1000)) {
    try { $proc.Kill() } catch { }
    throw "$FileName timed out after ${TimeoutSec}s"
  }
  $proc.WaitForExit()
  return [int]$proc.ExitCode
}

$script:NeewaRemoteCommand = {
  param($Request)
  $resolved = Resolve-NeewaExecutable ([string]$Request.Executable)
  return (Invoke-NeewaBoundedProcess -FileName $resolved -ArgumentList @($Request.ArgumentList) -TimeoutSec 20)
}

function Invoke-NeewaRemoteChecked {
  param(
    [Parameter(Mandatory)][string]$Executable,
    [Parameter(Mandatory)][string[]]$ArgumentList
  )
  $code = & $script:NeewaRemoteCommand @{ Executable = $Executable; ArgumentList = $ArgumentList }
  if ($null -eq $code) { $code = -1 }
  if ([int]$code -ne 0) { throw "$Executable exit $code" }
}

function Save-NeewaOutboxResult {
  param($JobFile, $Result)
  if ($Result -is [System.Array]) {
    $Result = @($Result | Where-Object { $_ -ne $null } | Select-Object -Last 1)
    if ($Result.Count -eq 1) { $Result = $Result[0] }
  }
  if ($Result -is [string]) {
    try { $Result = $Result | ConvertFrom-Json } catch { }
  }
  $name = Split-Path -Leaf $JobFile
  New-Item -ItemType Directory -Force -Path $script:NeewaOutbox | Out-Null
  $payloadPath = Join-Path $script:NeewaOutbox ($name + '.payload.json')
  $itemPath = Join-Path $script:NeewaOutbox ($name + '.item.json')
  $payload = $Result | ConvertTo-Json -Depth 8 -Compress
  [System.IO.File]::WriteAllText($payloadPath, $payload, [System.Text.UTF8Encoding]::new($false))
  $artifact = $null
  try {
    if ($Result.artifact -and (Test-Path -LiteralPath ([string]$Result.artifact))) {
      $artifact = [string]$Result.artifact
    }
  } catch { $artifact = $null }
  $item = [ordered]@{
    name = $name
    dest_dir = (Resolve-NeewaResultFolder $Result)
    payload_path = $payloadPath
    artifact = $artifact
  }
  [System.IO.File]::WriteAllText($itemPath, ($item | ConvertTo-Json -Compress), [System.Text.UTF8Encoding]::new($false))
  return $itemPath
}

function Send-NeewaOutboxItem {
  param([Parameter(Mandatory)][string]$ItemPath)
  $ack = "$ItemPath.ack"
  if (Test-Path -LiteralPath $ack) { return 'already-acked' }
  $item = Get-Content -Raw -LiteralPath $ItemPath | ConvertFrom-Json
  $name = [string]$item.name
  $payloadPath = [string]$item.payload_path
  if (-not (Test-Path -LiteralPath $payloadPath)) {
    throw "outbox payload missing: $payloadPath"
  }
  $remoteJson = "$RemoteInbox/$($item.dest_dir)/$name"
  Invoke-NeewaRemoteChecked 'scp' (@($sshOpts) + @($payloadPath, "${RemoteHost}:$remoteJson"))
  Invoke-NeewaRemoteChecked 'ssh' (@($sshOpts) + @($RemoteHost, "test -s '$remoteJson'"))
  if ($item.artifact) {
    $artifact = [string]$item.artifact
    if (Test-Path -LiteralPath $artifact) {
      $leaf = Split-Path -Leaf $artifact
      $remoteArt = "$RemoteInbox/$($item.dest_dir)/$leaf"
      Invoke-NeewaRemoteChecked 'scp' (@($sshOpts) + @($artifact, "${RemoteHost}:$remoteArt"))
      Invoke-NeewaRemoteChecked 'ssh' (@($sshOpts) + @($RemoteHost, "test -s '$remoteArt'"))
    }
  }
  Invoke-NeewaRemoteChecked 'ssh' (@($sshOpts) + @($RemoteHost, "rm -f $RemoteInbox/processing/$name"))
  Set-Content -LiteralPath $ack -Value $remoteJson -Encoding utf8
  return 'acked'
}

function Send-NeewaPendingOutbox {
  if (-not (Test-Path -LiteralPath $script:NeewaOutbox)) { return }
  Get-ChildItem -LiteralPath $script:NeewaOutbox -Filter '*.item.json' -ErrorAction SilentlyContinue |
    ForEach-Object {
      if (Test-Path -LiteralPath ($_.FullName + '.ack')) { return }
      try {
        Send-NeewaOutboxItem $_.FullName | Out-Null
        Write-Poll "outbox delivered $($_.Name)"
      } catch {
        Write-Poll "outbox retry failed $($_.Name): $($_.Exception.Message)"
      }
    }
}

if ($MyInvocation.InvocationName -eq '.') { return }

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
  New-Item -ItemType Directory -Force -Path $localInbox, $logDir, $script:NeewaOutbox | Out-Null
  $script:NeewaPollLog = Join-Path $logDir 'worker-poll.log'

  function Receive-RemoteJobs {
    $scratch = Join-Path $env:LOCALAPPDATA 'NEEWA\scratch'
    New-Item -ItemType Directory -Force -Path $scratch | Out-Null
    $tmp = Join-Path $scratch 'job-receive'
    New-Item -ItemType Directory -Force -Path $tmp | Out-Null
    & ssh @sshOpts $RemoteHost "mkdir -p $RemoteInbox/inbox $RemoteInbox/processing $RemoteInbox/done $RemoteInbox/failed; ls -1 $RemoteInbox/inbox/*.json 2>/dev/null" |
      ForEach-Object {
        $line = ([string]$_).Trim()
        if ($line -notmatch '\.json$') { return }
        $name = Split-Path -Leaf $line
        if ($name -notmatch '^[A-Za-z0-9._-]+\.json$') { return }
        $local = Join-Path $localInbox $name
        try {
          Invoke-NeewaRemoteChecked 'scp' (@($sshOpts) + @("${RemoteHost}:$RemoteInbox/inbox/$name", $local))
          Invoke-NeewaRemoteChecked 'ssh' (@($sshOpts) + @($RemoteHost, "mv $RemoteInbox/inbox/$name $RemoteInbox/processing/$name"))
        } catch {
          Write-Poll "claim failed ${name}: $($_.Exception.Message)"
          return
        }
        Write-Poll "claimed $name"
      }
  }

  function Invoke-Pending {
    $jobsDir = Join-Path $env:USERPROFILE 'NEEWA-Personal\jobs'
    Get-ChildItem -LiteralPath $localInbox -Filter '*.json' -ErrorAction SilentlyContinue |
      Sort-Object LastWriteTime -Descending |
      ForEach-Object {
        $stamp = Join-Path $jobsDir ($_.BaseName + '.done.json')
        $item = Join-Path $script:NeewaOutbox ($_.Name + '.item.json')
        $ack = "$item.ack"
        if (Test-Path -LiteralPath $stamp) {
          if ((Test-Path -LiteralPath $item) -and -not (Test-Path -LiteralPath $ack)) {
            try {
              Send-NeewaOutboxItem $item | Out-Null
            } catch {
              Write-Poll "remote result push failed: $($_.Exception.Message)"
              return
            }
          }
          if (Test-Path -LiteralPath $ack) {
            Remove-Item -LiteralPath $_.FullName -Force
          } else {
            Write-Poll "local completion kept; delivery not acknowledged $($_.Name)"
          }
          return
        }
        Write-Poll "invoke $($_.Name)"
        Write-WorkerStatus $_.BaseName
        $result = & $invoke -JobPath $_.FullName
        Write-Output ($result | ConvertTo-Json -Compress)
        try {
          $saved = Save-NeewaOutboxResult $_.FullName $result
          Send-NeewaOutboxItem $saved | Out-Null
          Remove-Item -LiteralPath $_.FullName -Force
        } catch {
          Write-Poll "remote result push failed: $($_.Exception.Message)"
        }
      }
  }

  function Write-WorkerStatus([string]$ActiveJob) {
    $allowObj = Get-Content -Raw (Join-Path $here 'allowlist.json') | ConvertFrom-Json
    $caps = @($allowObj.actions.PSObject.Properties.Name)
    $statusPath = Join-Path $env:LOCALAPPDATA 'NEEWA\worker-status.json'
    $doc = [ordered]@{
      at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
      host = $env:COMPUTERNAME
      account = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
      worker_path = $here
      capability_version = [string]$allowObj.capability_version
      capabilities = $caps
      active_job_id = $ActiveJob
      heartbeat = $true
    }
    $doc | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $statusPath -Encoding utf8
    try {
      Invoke-NeewaRemoteChecked 'scp' (@($sshOpts) + @($statusPath, "${RemoteHost}:$RemoteInbox/records/windows-worker-status.json"))
    } catch {
      Write-Poll "worker status upload failed: $($_.Exception.Message)"
    }
  }

  do {
    try { Send-NeewaPendingOutbox } catch { Write-Poll "outbox skipped: $($_.Exception.Message)" }
    try { Receive-RemoteJobs } catch { Write-Poll "poll skipped: $($_.Exception.Message)" }
    Write-WorkerStatus ''
    Invoke-Pending
    if (-not $Once) { Start-Sleep -Seconds 15 }
  } while (-not $Once)
}
finally {
  $mutex.ReleaseMutex() | Out-Null
  $mutex.Dispose()
}
