# Live Ear: make the laptop microphone capture as strongly as Windows allows.
#   1. Lists every active recording device.
#   2. Picks the real built-in or USB microphone (never the Krisp or other virtual ones)
#      and makes it the default recording device for all apps, Edge included.
#   3. Unmutes it and sets its input level to 100 percent.
#   4. Saves the previous settings so you can undo with: mic_boost.bat restore
#   5. Opens the microphone Levels window so you can raise Microphone Boost if your driver has it.
param([string]$Mode = "boost")

$code = @"
using System;
using System.Runtime.InteropServices;

[StructLayout(LayoutKind.Sequential)] public struct PROPERTYKEY { public Guid fmtid; public int pid; }
[StructLayout(LayoutKind.Explicit)] public struct PROPVARIANT {
  [FieldOffset(0)] public short vt; [FieldOffset(8)] public IntPtr p; [FieldOffset(16)] public long pad; }

[Guid("886d8eeb-8cf2-4446-8d02-cdba1dbdcf99"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IPropertyStore {
  int GetCount(out int c); int GetAt(int i, out PROPERTYKEY k);
  int GetValue(ref PROPERTYKEY key, out PROPVARIANT v); int SetValue(ref PROPERTYKEY key, ref PROPVARIANT v); int Commit(); }

[Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IMMDevice {
  int Activate(ref Guid iid, int clsCtx, IntPtr p, [MarshalAs(UnmanagedType.IUnknown)] out object o);
  int OpenPropertyStore(int access, out IPropertyStore store);
  int GetId([MarshalAs(UnmanagedType.LPWStr)] out string id);
  int GetState(out int state); }

[Guid("0BD7A1BE-7A1A-44DB-8397-CC5392387B5E"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IMMDeviceCollection { int GetCount(out int n); int Item(int i, out IMMDevice d); }

[Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IMMDeviceEnumerator {
  int EnumAudioEndpoints(int flow, int mask, out IMMDeviceCollection c);
  int GetDefaultAudioEndpoint(int flow, int role, out IMMDevice d);
  int GetDevice([MarshalAs(UnmanagedType.LPWStr)] string id, out IMMDevice d);
  int Reg(IntPtr p); int Unreg(IntPtr p); }

[ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")] public class MMDeviceEnumeratorCom {}

[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IAudioEndpointVolume {
  int RegisterControlChangeNotify(IntPtr p); int UnregisterControlChangeNotify(IntPtr p);
  int GetChannelCount(out int n);
  int SetMasterVolumeLevel(float db, ref Guid ctx); int SetMasterVolumeLevelScalar(float v, ref Guid ctx);
  int GetMasterVolumeLevel(out float db); int GetMasterVolumeLevelScalar(out float v);
  int SetChannelVolumeLevel(int ch, float db, ref Guid ctx); int SetChannelVolumeLevelScalar(int ch, float v, ref Guid ctx);
  int GetChannelVolumeLevel(int ch, out float db); int GetChannelVolumeLevelScalar(int ch, out float v);
  int SetMute([MarshalAs(UnmanagedType.Bool)] bool mute, ref Guid ctx); int GetMute([MarshalAs(UnmanagedType.Bool)] out bool mute);
  int GetVolumeStepInfo(out int step, out int count); int VolumeStepUp(ref Guid ctx); int VolumeStepDown(ref Guid ctx);
  int QueryHardwareSupport(out int mask); int GetVolumeRange(out float min, out float max, out float inc); }

[Guid("f8679f50-850a-41cf-9c72-430f290290c8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IPolicyConfig {
  int GetMixFormat(); int GetDeviceFormat(); int ResetDeviceFormat(); int SetDeviceFormat();
  int GetProcessingPeriod(); int SetProcessingPeriod(); int GetShareMode(); int SetShareMode();
  int GetPropertyValue(); int SetPropertyValue();
  int SetDefaultEndpoint([MarshalAs(UnmanagedType.LPWStr)] string id, int role);
  int SetEndpointVisibility(); }

[ComImport, Guid("870af99c-171d-4f9e-af0d-e63df40c2bc9")] public class PolicyConfigCom {}

public class Mic {
  static IMMDeviceEnumerator En() { return (IMMDeviceEnumerator)(new MMDeviceEnumeratorCom()); }
  public static string[] List() {
    IMMDeviceCollection c; En().EnumAudioEndpoints(1, 1, out c);
    int n; c.GetCount(out n); string[] r = new string[n];
    for (int i = 0; i < n; i++) { IMMDevice d; c.Item(i, out d); string id; d.GetId(out id); r[i] = id + "|" + Name(d); }
    return r; }
  static string Name(IMMDevice d) {
    IPropertyStore s; d.OpenPropertyStore(0, out s);
    PROPERTYKEY k = new PROPERTYKEY(); k.fmtid = new Guid("a45c254e-df1c-4efd-8020-67d146a850e0"); k.pid = 14;
    PROPVARIANT v; s.GetValue(ref k, out v);
    return v.vt == 31 ? Marshal.PtrToStringUni(v.p) : "(no name)"; }
  public static string DefaultId() {
    try { IMMDevice d; En().GetDefaultAudioEndpoint(1, 0, out d); string id; d.GetId(out id); return id; } catch { return ""; } }
  static IAudioEndpointVolume Vol(string id) {
    IMMDevice d; En().GetDevice(id, out d);
    Guid iid = typeof(IAudioEndpointVolume).GUID; object o; d.Activate(ref iid, 23, IntPtr.Zero, out o);
    return (IAudioEndpointVolume)o; }
  public static float GetLevel(string id) { float v; Vol(id).GetMasterVolumeLevelScalar(out v); return v; }
  public static void SetLevel(string id, float v) { Guid g = Guid.Empty; var a = Vol(id); a.SetMute(false, ref g); a.SetMasterVolumeLevelScalar(v, ref g); }
  public static void MakeDefault(string id) {
    var p = (IPolicyConfig)(new PolicyConfigCom());
    p.SetDefaultEndpoint(id, 0); p.SetDefaultEndpoint(id, 1); p.SetDefaultEndpoint(id, 2); }
}
"@

try { Add-Type -TypeDefinition $code -Language CSharp -ErrorAction Stop } catch { Write-Host "Could not load the audio tools: $_" -ForegroundColor Red; exit 1 }

$backup = Join-Path $env:USERPROFILE "LiveEar_mic_backup.txt"

if ($Mode -eq "restore") {
  if (-not (Test-Path $backup)) { Write-Host "No saved settings to restore." -ForegroundColor Yellow; exit 0 }
  $b = Get-Content $backup
  if ($b[0]) { [Mic]::MakeDefault($b[0]) }
  [Mic]::SetLevel($b[1], [float][double]::Parse($b[2], [Globalization.CultureInfo]::InvariantCulture))
  Write-Host "Previous microphone settings restored." -ForegroundColor Green
  exit 0
}

$devices = [Mic]::List() | ForEach-Object { $p = $_ -split '\|', 2; [pscustomobject]@{ Id = $p[0]; Name = $p[1] } }
if (-not $devices) { Write-Host "No active microphone found. Check that the microphone is not disabled in Sound settings." -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "Recording devices found:" -ForegroundColor Cyan
$i = 0; foreach ($d in $devices) { $i++; Write-Host ("  {0}. {1}" -f $i, $d.Name) }

$virtual = 'krisp|virtual|cable|voicemeeter|stereo mix|what u hear|wave out|nvidia broadcast|camo|droidcam'
$real = $devices | Where-Object { $_.Name -notmatch $virtual }
$pick = $real | Where-Object { $_.Name -match 'microphone array|array|built-in|internal|usb' } | Select-Object -First 1
if (-not $pick) { $pick = $real | Where-Object { $_.Name -match 'microphone|mic' } | Select-Object -First 1 }
if (-not $pick) { $pick = $real | Select-Object -First 1 }
if (-not $pick) { Write-Host "Only virtual microphones were found (such as Krisp). Connect or enable the real microphone first." -ForegroundColor Red; exit 1 }

$oldDefault = [Mic]::DefaultId()
$oldLevel = [Mic]::GetLevel($pick.Id)
Set-Content -Path $backup -Value @($oldDefault, $pick.Id, $oldLevel.ToString([Globalization.CultureInfo]::InvariantCulture)) -Encoding UTF8

[Mic]::MakeDefault($pick.Id)
[Mic]::SetLevel($pick.Id, 1.0)
$newLevel = [Mic]::GetLevel($pick.Id)

Write-Host ""
Write-Host ("Chosen microphone : {0}" -f $pick.Name) -ForegroundColor Green
Write-Host ("Default for all apps: yes (Krisp and virtual devices skipped)") -ForegroundColor Green
Write-Host ("Input level       : {0}% -> {1}%" -f [math]::Round($oldLevel*100), [math]::Round($newLevel*100)) -ForegroundColor Green
Write-Host ""
Write-Host "Last step by hand: the Sound window opens now." -ForegroundColor Yellow
Write-Host "  Double-click the microphone marked with a green tick, open the Levels tab," -ForegroundColor Yellow
Write-Host "  and if you see Microphone Boost, set it to +20 dB (or +30 dB if voices stay faint). Then OK." -ForegroundColor Yellow
Write-Host "  If the Advanced tab shows 'Allow applications to take exclusive control', leave it ticked." -ForegroundColor Yellow
Write-Host ""
Write-Host "To undo everything later: run mic_boost.bat restore" -ForegroundColor DarkGray
Start-Process "control.exe" "mmsys.cpl,,1"
