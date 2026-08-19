[CmdletBinding()]
param(
    [ValidateSet("Install", "Uninstall")][string]$Action = "Install",
    [string]$Distro = "",
    [ValidateSet("Systemd", "Direct")][string]$Mode = "Systemd",
    [string]$LinuxCommand = ""
)

$ErrorActionPreference = "Stop"
$TaskPath = "\Portable Local AI\"
$TaskName = "Start Portable Local AI WSL"
if ($Action -eq "Uninstall") {
    Unregister-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    exit 0
}
if (-not $Distro) {
    $Distro = (& wsl.exe --list --quiet | ForEach-Object { ($_ -replace "`0", "").Trim() } | Where-Object { $_ } | Select-Object -First 1)
}
if (-not $Distro) { throw "No WSL distribution was detected." }
$Wsl = Join-Path $env:WINDIR "System32\wsl.exe"
$Arguments = if ($Mode -eq "Systemd") {
    "-d `"$Distro`" --exec systemctl --user start portable-local-ai.service"
} else {
    "-d `"$Distro`" --exec `"$LinuxCommand`""
}
$TaskAction = New-ScheduledTaskAction -Execute $Wsl -Argument $Arguments
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$Trigger.Delay = "PT10S"
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -StartWhenAvailable
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName -Action $TaskAction -Trigger $Trigger -Settings $Settings -Principal $Principal -Description "Starts Portable Local AI in WSL at Windows sign-in." -Force | Out-Null
$Shortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "Portable Local AI.url"
@("[InternetShortcut]", "URL=http://127.0.0.1:8181", "IconIndex=0") | Set-Content -Path $Shortcut -Encoding ASCII
