[CmdletBinding(SupportsShouldProcess)]
param(
  [string]$PreferredNamePattern = 'Realtek',
  [string]$AvoidNamePattern = 'Iriun'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$cs = @'
using System;
using System.Runtime.InteropServices;

public static class NeewaPolicyConfig {
  public const int eConsole = 0;
  public const int eMultimedia = 1;
  public const int eCommunications = 2;

  [ComImport, Guid("F8679F50-850A-41CF-9C72-430F290290C8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  interface IPolicyConfig {
    int GetMixFormat(string pszDeviceName, IntPtr ppFormat);
    int GetDeviceFormat(string pszDeviceName, bool bDefault, IntPtr ppFormat);
    int ResetDeviceFormat(string pszDeviceName);
    int SetDeviceFormat(string pszDeviceName, IntPtr pEndpointFormat, IntPtr MixFormat);
    int GetProcessingPeriod(string pszDeviceName, bool bDefault, IntPtr pmftDefaultPeriod, IntPtr pmftMinimumPeriod);
    int SetProcessingPeriod(string pszDeviceName, IntPtr pmftPeriod);
    int GetShareMode(string pszDeviceName, IntPtr pMode);
    int SetShareMode(string pszDeviceName, IntPtr pMode);
    int GetPropertyValue(string pszDeviceName, IntPtr key, IntPtr pv);
    int SetPropertyValue(string pszDeviceName, IntPtr key, IntPtr pv);
    int SetDefaultEndpoint(string pszDeviceName, int role);
    int SetEndpointVisibility(string pszDeviceName, bool bVisible);
  }

  [ComImport, Guid("870AF99C-171D-4F9E-AF0D-E63DF40C2BC9")]
  class PolicyConfigClient {}

  public static int SetDefault(string deviceId, int role) {
    var cfg = (IPolicyConfig)new PolicyConfigClient();
    return cfg.SetDefaultEndpoint(deviceId, role);
  }
}

public static class NeewaCoreAudio {
  public const int eCapture = 1;
  [ComImport, Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  public interface IMMDeviceEnumerator {
    int NotImpl1();
    [PreserveSig] int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice ppDevice);
    [PreserveSig] int EnumAudioEndpoints(int dataFlow, int dwStateMask, out IMMDeviceCollection ppDevices);
  }
  [ComImport, Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  public interface IMMDevice {
    [PreserveSig] int Activate(ref Guid iid, int dwClsCtx, IntPtr pActivationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface);
    [PreserveSig] int OpenPropertyStore(int stgmAccess, out IPropertyStore ppProperties);
    [PreserveSig] int GetId([MarshalAs(UnmanagedType.LPWStr)] out string ppstrId);
  }
  [ComImport, Guid("0BD7A1BE-7A1A-44DB-8397-CC5392387C5E"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  public interface IMMDeviceCollection {
    [PreserveSig] int GetCount(out uint pcDevices);
    [PreserveSig] int Item(uint nDevice, out IMMDevice ppDevice);
  }
  [StructLayout(LayoutKind.Sequential)]
  public struct PROPERTYKEY { public Guid fmtid; public int pid; }
  [StructLayout(LayoutKind.Sequential)]
  public struct PROPVARIANT {
    public short vt, wReserved1, wReserved2, wReserved3;
    public IntPtr p;
  }
  [ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  public interface IPropertyStore {
    [PreserveSig] int GetCount(out uint cProps);
    [PreserveSig] int GetAt(uint iProp, out PROPERTYKEY pkey);
    [PreserveSig] int GetValue(ref PROPERTYKEY key, out PROPVARIANT pv);
  }
  [ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
  public class MMDeviceEnumeratorComObject {}

  public static string DeviceName(IMMDevice dev) {
    IPropertyStore store;
    dev.OpenPropertyStore(0, out store);
    var key = new PROPERTYKEY { fmtid = new Guid("a45c254e-df1c-4efd-8020-67d146a850e0"), pid = 14 };
    PROPVARIANT pv;
    store.GetValue(ref key, out pv);
    return Marshal.PtrToStringUni(pv.p);
  }

  public static string DefaultId(int role, out string name) {
    var en = (IMMDeviceEnumerator)new MMDeviceEnumeratorComObject();
    IMMDevice dev;
    int hr = en.GetDefaultAudioEndpoint(eCapture, role, out dev);
    if (hr != 0) { name = "hr=" + hr; return null; }
    string id;
    dev.GetId(out id);
    name = DeviceName(dev);
    return id;
  }

  public static string FindCaptureId(string prefer, string avoid, out string name) {
    string multimediaName;
    string multimediaId = DefaultId(1, out multimediaName);
    if (multimediaId != null && (string.IsNullOrEmpty(prefer) || (multimediaName ?? "").IndexOf(prefer, StringComparison.OrdinalIgnoreCase) >= 0)
        && (string.IsNullOrEmpty(avoid) || (multimediaName ?? "").IndexOf(avoid, StringComparison.OrdinalIgnoreCase) < 0)) {
      name = multimediaName;
      return multimediaId;
    }
    string consoleName;
    string consoleId = DefaultId(0, out consoleName);
    name = consoleName;
    return consoleId;
  }
}
'@

if (-not ([System.Management.Automation.PSTypeName]'NeewaPolicyConfig').Type) {
  Add-Type -TypeDefinition $cs
}

function Show-Role([int]$role, [string]$label) {
  $name = $null
  $id = [NeewaCoreAudio]::DefaultId($role, [ref]$name)
  Write-Host ("{0}: {1}" -f $label, $(if ($name) { $name } else { $id }))
}

Write-Host 'Before:'
Show-Role 0 'CONSOLE'
Show-Role 1 'MULTIMEDIA'
Show-Role 2 'COMMUNICATIONS'

$chosenName = $null
$chosenId = [NeewaCoreAudio]::FindCaptureId($PreferredNamePattern, $AvoidNamePattern, [ref]$chosenName)
if (-not $chosenId) { throw 'No active capture endpoint matched the preferred Realtek array.' }
Write-Host ("Preferred capture: {0}" -f $chosenName)

if ($PSCmdlet.ShouldProcess($chosenName, 'Set default capture endpoint for Console/Multimedia/Communications')) {
  foreach ($role in 0, 1, 2) {
    $hr = [NeewaPolicyConfig]::SetDefault($chosenId, $role)
    if ($hr -ne 0) { throw ("SetDefaultEndpoint role {0} failed HRESULT=0x{1:X8}" -f $role, $hr) }
  }
}

Write-Host 'After:'
Show-Role 0 'CONSOLE'
Show-Role 1 'MULTIMEDIA'
Show-Role 2 'COMMUNICATIONS'
