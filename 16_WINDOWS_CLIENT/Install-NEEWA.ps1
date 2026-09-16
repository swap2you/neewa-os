[CmdletBinding()]
param([string]$ServerHost='neewa-core-01',[string]$ServerUser='ubuntu',[switch]$ConfirmPersonalDevice,[switch]$SkipHermesInstall)
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
if(-not $IsWindows){throw 'Run this package on Windows.'}
if(-not $ConfirmPersonalDevice){$answer=Read-Host 'Confirm this is Swapnil personal PC, not an employer device. Type PERSONAL';if($answer-ne'PERSONAL'){throw 'Personal-device confirmation not received.'}}
Write-Host 'NEEWA bootstrap never requests secrets.'
$tailscale=Get-Command tailscale.exe -ErrorAction SilentlyContinue
if(-not $tailscale){if(-not(Get-Command winget.exe -ErrorAction SilentlyContinue)){throw 'winget is required.'};winget install --id Tailscale.Tailscale --exact --source winget --accept-source-agreements --accept-package-agreements;$tailscalePath=Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe'}else{$tailscalePath=$tailscale.Source}
if(-not(Test-Path $tailscalePath)){throw 'Tailscale is not installed.'};& $tailscalePath status|Out-Host
if(-not $SkipHermesInstall -and -not(Get-Command hermes.exe -ErrorAction SilentlyContinue)){$url='https://hermes-assets.nousresearch.com/Hermes-Setup.exe?build=f13a87e61061';$installer=Join-Path $env:TEMP 'Hermes-Setup.exe';Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing;$signature=Get-AuthenticodeSignature $installer;if($signature.Status-ne'Valid'){throw "Hermes signature is $($signature.Status)"};if($signature.SignerCertificate.Subject-notmatch'O=Nous Research Inc\.'){throw "Unexpected signer: $($signature.SignerCertificate.Subject)"};$hash=(Get-FileHash -Algorithm SHA256 $installer).Hash.ToLowerInvariant();Write-Host "Validated Nous Research signer; SHA256 $hash";Start-Process $installer -Wait}
$hermesHome=if($env:HERMES_HOME){$env:HERMES_HOME}else{Join-Path $env:LOCALAPPDATA 'hermes'};$skinDir=Join-Path $hermesHome 'skins';$pluginDir=Join-Path $hermesHome 'desktop-plugins\neewa-command-center';New-Item -ItemType Directory -Force -Path $skinDir,$pluginDir|Out-Null;Copy-Item (Join-Path $PSScriptRoot 'assets\neewa.yaml') (Join-Path $skinDir 'neewa.yaml') -Force;Copy-Item (Join-Path $PSScriptRoot 'assets\neewa-command-center\plugin.js') (Join-Path $pluginDir 'plugin.js') -Force
$env:Path = (Join-Path $hermesHome 'bin') + ';' + $env:Path
$hermesPath = Join-Path $hermesHome 'bin\hermes.exe'
if (-not (Test-Path $hermesPath)) { $hermesCmd = Get-Command hermes.exe -ErrorAction SilentlyContinue; if ($hermesCmd) { $hermesPath = $hermesCmd.Source } else { throw "Hermes launcher not found after installer completed: $hermesPath" } }
& $hermesPath config set display.skin neewa | Out-Host
$desktopRelease = Join-Path $hermesHome 'hermes-agent\apps\desktop\release'
$desktopExe = @((Join-Path $desktopRelease 'win-unpacked\Hermes.exe'),(Join-Path $desktopRelease 'win-arm64-unpacked\Hermes.exe')) | Where-Object { Test-Path $_ } | Select-Object -First 1
$startup=[Environment]::GetFolderPath('Startup');$shortcutPath=Join-Path $startup 'NEEWA Hermes Desktop.lnk'
if ($desktopExe) { $shell=New-Object -ComObject WScript.Shell;$shortcut=$shell.CreateShortcut($shortcutPath);$shortcut.TargetPath=$desktopExe;$shortcut.WorkingDirectory=(Split-Path -Parent $desktopExe);$shortcut.Save() } else { Write-Warning "Packed Hermes.exe not found; use the official installer shortcut instead of creating a rebuild-on-login shortcut." }
$portTest=Test-NetConnection -ComputerName $ServerHost -Port 22 -WarningAction SilentlyContinue;if(-not $portTest.TcpTestSucceeded){Write-Warning "Cannot reach $ServerHost:22. Complete Tailscale sign-in/MagicDNS."}
$steps=@"
NEEWA ONE-TIME CONNECTION
1. Confirm Tailscale shows $ServerHost online.
2. Open Hermes Desktop; choose provider later on first launch.
3. Settings > Gateways > Add connection > SSH.
4. Name: NEEWA; SSH host: $ServerUser@$ServerHost`:22.
5. Save, Test (must be Reachable), then Make Primary.
6. Settings > Voice: select remote NEEWA profile; test microphone and speech.
7. Enable the ear icon and say: Hey Neewa.
8. Optional: Quick Entry Ctrl+Shift+Space; HUD Ctrl+Shift+H.
No public endpoint or Tailscale Funnel is required.
"@;$stepsPath=Join-Path ([Environment]::GetFolderPath('Desktop')) 'NEEWA-NEXT-STEPS.txt';Set-Content $stepsPath $steps -Encoding UTF8;Write-Host "Prepared. Open $stepsPath"
