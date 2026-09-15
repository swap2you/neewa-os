Write-Host "=== NEEWA-EDGE-01 Readiness ==="
Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, OsArchitecture
Get-CimInstance Win32_ComputerSystem | Select-Object TotalPhysicalMemory
Get-Volume | Sort-Object DriveLetter | Select-Object DriveLetter, FileSystemLabel, Size, SizeRemaining

$tools = @("git","docker","node","npm","python","java","codex","claude","gemini")
foreach ($tool in $tools) {
    $cmd = Get-Command $tool -ErrorAction SilentlyContinue
    if ($cmd) { Write-Host "$tool -> $($cmd.Source)" }
    else { Write-Host "$tool -> NOT FOUND" }
}

Write-Host "Read-only readiness check complete. No cleanup was performed."
