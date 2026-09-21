# Publish Windows-worker execution evidence to the Ubuntu inbox tree.
# Updates existing processing/records files only. Does not enqueue a new job.
[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$JobId,
  [Parameter(Mandatory)][string]$State,
  [int]$WorkerPid = $PID,
  [int]$ChildPid = 0,
  [string]$CommandLine = '',
  [string]$RemoteHost = 'ubuntu@neewa-core-01',
  [string]$RemoteInbox = '/home/ubuntu/.hermes/sandboxes/docker/default/workspace/windows-jobs'
)
$ErrorActionPreference = 'Stop'
$now = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
$expires = (Get-Date).ToUniversalTime().AddSeconds(90).ToString('yyyy-MM-ddTHH:mm:ssZ')
$payloadObj = [ordered]@{
  job_id = $JobId
  state = $State
  worker_pid = $WorkerPid
  child_pid = $ChildPid
  command_line = $CommandLine
  progress_at = $now
  host = $env:COMPUTERNAME
  lease = [ordered]@{
    owner = $WorkerPid
    child_pid = $ChildPid
    fencing = "win-$WorkerPid-$JobId"
    expires_at = $expires
    host = $env:COMPUTERNAME
  }
}
$payload = $payloadObj | ConvertTo-Json -Compress -Depth 8
$python = @'
import json, sys
from pathlib import Path
u = json.load(sys.stdin)
root = Path("/home/ubuntu/.hermes/sandboxes/docker/default/workspace/windows-jobs")
job = u["job_id"]
now = u["progress_at"]
updated = []
for folder in ("processing", "records"):
    p = root / folder / ("%s.json" % job)
    if not p.is_file():
        continue
    bak = p.with_name(p.name + ".pre-running.bak")
    if folder == "processing" and not bak.exists():
        bak.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("job_id") not in (None, job):
        continue
    data["state"] = u["state"]
    data["lease"] = u["lease"]
    data["child_pid"] = u["child_pid"]
    data["worker_pid"] = u["worker_pid"]
    data["command_line"] = u.get("command_line")
    data["progress_at"] = now
    data["updated_at"] = now
    hist = list(data.get("history") or [])
    last = hist[-1] if hist else {}
    if last.get("state") != u["state"] or last.get("child_pid") != u["child_pid"]:
        hist.append({"state": u["state"], "at": now, "child_pid": u["child_pid"], "worker_pid": u["worker_pid"]})
    data["history"] = hist
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(p)
    updated.append(str(p))
active = {
    "at": now,
    "active_jobs": [{
        "job_id": job,
        "state": u["state"],
        "child_pid": u["child_pid"],
        "worker_pid": u["worker_pid"],
        "mission_id": None
    }]
}
(root / "records" / "active_jobs.json").write_text(json.dumps(active, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"updated": updated, "progress_at": now, "state": u["state"], "child_pid": u["child_pid"]}))
'@
$sshOpts = @('-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', '-o', 'LogLevel=ERROR')
$tmpPy = Join-Path $env:TEMP 'neewa-publish-progress.py'
[System.IO.File]::WriteAllText($tmpPy, $python.Replace("`r`n", "`n"), [System.Text.UTF8Encoding]::new($false))
& scp @sshOpts $tmpPy "${RemoteHost}:/tmp/neewa-publish-progress.py" | Out-Null
$out = $payload | & ssh @sshOpts $RemoteHost 'python3 /tmp/neewa-publish-progress.py'
if ($LASTEXITCODE -ne 0) { throw "progress publish failed: $out" }
$out
