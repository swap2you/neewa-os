# Concurrent stdout/stderr drain. Dot-source safe. No param() block.
# A redirected child that fills either pipe must not deadlock the parent.

function Invoke-NeewaDrainedProcess {
  param(
    [Parameter(Mandatory)]$StartInfo,
    [int]$TimeoutMs = 20000,
    [int]$MaxChars = 200000,
    [switch]$BinaryOutput,
    [string]$InputText
  )
  if ($env:OS -eq 'Windows_NT' -and -not ('NeewaOwnedChildJob' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
public static class NeewaOwnedChildJob {
  [StructLayout(LayoutKind.Sequential)] struct Basic {
    public long ProcessTime, JobTime;
    public uint Flags;
    public UIntPtr MinWorkingSet, MaxWorkingSet;
    public uint ActiveProcesses;
    public UIntPtr Affinity;
    public uint Priority, Scheduling;
  }
  [StructLayout(LayoutKind.Sequential)] struct Io {
    public ulong ReadOps, WriteOps, OtherOps, ReadBytes, WriteBytes, OtherBytes;
  }
  [StructLayout(LayoutKind.Sequential)] struct Extended {
    public Basic BasicLimits;
    public Io IoCounters;
    public UIntPtr ProcessMemory, JobMemory, PeakProcessMemory, PeakJobMemory;
  }
  [StructLayout(LayoutKind.Sequential)] struct Accounting {
    public long TotalUserTime, TotalKernelTime, PeriodUserTime, PeriodKernelTime;
    public uint PageFaults, TotalProcesses, ActiveProcesses, TerminatedProcesses;
  }
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
  static extern IntPtr CreateJobObject(IntPtr attributes, string name);
  [DllImport("kernel32.dll", SetLastError=true)]
  static extern bool SetInformationJobObject(IntPtr job, int kind, ref Extended limits, uint size);
  [DllImport("kernel32.dll", SetLastError=true)]
  static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
  [DllImport("kernel32.dll", SetLastError=true)]
  static extern bool QueryInformationJobObject(IntPtr job, int kind, out Accounting info, uint size, IntPtr length);
  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern bool CloseHandle(IntPtr handle);
  public static IntPtr Create() {
    var job=CreateJobObject(IntPtr.Zero, null);
    if(job==IntPtr.Zero) throw new Win32Exception();
    var limits=new Extended();
    limits.BasicLimits.Flags=0x2000; // JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if(!SetInformationJobObject(job, 9, ref limits, (uint)Marshal.SizeOf(typeof(Extended)))) {
      int error=Marshal.GetLastWin32Error(); CloseHandle(job); throw new Win32Exception(error);
    }
    return job;
  }
  public static void Attach(IntPtr job, IntPtr process) {
    if(!AssignProcessToJobObject(job, process)) throw new Win32Exception();
  }
  public static uint ActiveProcesses(IntPtr job) {
    Accounting info;
    if(!QueryInformationJobObject(job, 1, out info, (uint)Marshal.SizeOf(typeof(Accounting)), IntPtr.Zero)) throw new Win32Exception();
    return info.ActiveProcesses;
  }
}
'@
  }
  $proc = New-Object System.Diagnostics.Process
  $proc.StartInfo = $StartInfo
  $timedOut = $false
  $inputFailed = $false
  $exitCode = $null
  $outText = ''
  $errText = ''
  $outBytes = [byte[]]@()
  $buffer = $null
  $ownedJob = [IntPtr]::Zero
  $elapsed = [System.Diagnostics.Stopwatch]::StartNew()
  try {
    if ($env:OS -eq 'Windows_NT') { $ownedJob = [NeewaOwnedChildJob]::Create() }
    [void]$proc.Start()
    if ($ownedJob -ne [IntPtr]::Zero) { [NeewaOwnedChildJob]::Attach($ownedJob, $proc.Handle) }
    if ($BinaryOutput) {
      $buffer = New-Object System.IO.MemoryStream
      $stdoutTask = $proc.StandardOutput.BaseStream.CopyToAsync($buffer)
    } else {
      $stdoutTask = $proc.StandardOutput.ReadToEndAsync()
    }
    $stderrTask = $proc.StandardError.ReadToEndAsync()
    if ($StartInfo.RedirectStandardInput) {
      # Drain both output streams before writing a large prompt, and bound the
      # write itself so a child that never consumes stdin cannot hang a worker.
      try {
        $inputTask = $proc.StandardInput.WriteAsync($InputText)
        $remainingMs = [Math]::Max(0, $TimeoutMs - [int]$elapsed.ElapsedMilliseconds)
        if (-not $inputTask.Wait($remainingMs)) { $timedOut = $true }
        else { [void]$inputTask.GetAwaiter().GetResult(); $proc.StandardInput.Close() }
      } catch { $inputFailed = $true; try { $proc.StandardInput.Close() } catch { } }
    }
    $remainingMs = [Math]::Max(0, $TimeoutMs - [int]$elapsed.ElapsedMilliseconds)
    if ($timedOut -or -not $proc.WaitForExit($remainingMs)) {
      $timedOut = $true
      try { $proc.Kill($true) } catch { try { $proc.Kill() } catch { } }
    }
    # A parent can exit while a descendant retains inherited pipe handles.
    # Bound the drain tasks by the same deadline as stdin and process exit.
    $remainingMs = [Math]::Max(0, $TimeoutMs - [int]$elapsed.ElapsedMilliseconds)
    $drains = [System.Threading.Tasks.Task]::WhenAll([System.Threading.Tasks.Task[]]@($stdoutTask, $stderrTask))
    if (-not $timedOut -and -not $drains.Wait($remainingMs)) { $timedOut = $true }
    # Completion also requires this invocation's owned descendants to exit.
    # Some native launchers close their pipe copies before children terminate.
    if (-not $timedOut -and $ownedJob -ne [IntPtr]::Zero) {
      while ([NeewaOwnedChildJob]::ActiveProcesses($ownedJob) -gt 0) {
        if ($elapsed.ElapsedMilliseconds -ge $TimeoutMs) { $timedOut = $true; break }
        [System.Threading.Thread]::Sleep(10)
      }
    }
    if ($timedOut) {
      if ($ownedJob -ne [IntPtr]::Zero) {
        [void][NeewaOwnedChildJob]::CloseHandle($ownedJob); $ownedJob = [IntPtr]::Zero
      }
      try { if (-not $proc.HasExited) { try { $proc.Kill($true) } catch { $proc.Kill() } } } catch { }
      [void]$proc.WaitForExit(1000)
    }
    if ($BinaryOutput) {
      if ($stdoutTask.IsCompleted) { [void]$stdoutTask.GetAwaiter().GetResult(); $outBytes = $buffer.ToArray() }
    } else {
      if ($stdoutTask.IsCompleted) { try { $outText = [string]$stdoutTask.GetAwaiter().GetResult() } catch { $outText = '' } }
    }
    if ($stderrTask.IsCompleted) { try { $errText = [string]$stderrTask.GetAwaiter().GetResult() } catch { $errText = '' } }
    try { $exitCode = [int]$proc.ExitCode } catch { $exitCode = $null }
  } catch {
    # A launch/drain exception must not orphan this owned child. Never target a
    # PID other than the process object started by this invocation.
    try { if (-not $proc.HasExited) { try { $proc.Kill($true) } catch { $proc.Kill() } } } catch { }
    throw
  } finally {
    if ($ownedJob -ne [IntPtr]::Zero) { [void][NeewaOwnedChildJob]::CloseHandle($ownedJob) }
    $proc.Dispose()
    if ($buffer) { $buffer.Dispose() }
  }
  if ($outText.Length -gt $MaxChars) { $outText = $outText.Substring($outText.Length - $MaxChars) }
  if ($errText.Length -gt $MaxChars) { $errText = $errText.Substring($errText.Length - $MaxChars) }
  return [pscustomobject]@{
    ExitCode = $exitCode
    Stdout = $outText
    StdoutBytes = $outBytes
    Stderr = $errText
    TimedOut = $timedOut
    InputFailed = $inputFailed
  }
}

