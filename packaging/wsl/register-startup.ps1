[CmdletBinding()]
param(
    [ValidateSet("Install", "Uninstall")][string]$Action = "Install",
    [string]$Distro = ""
)

$ErrorActionPreference = "Stop"
$TaskPath = "\Local AI\"
$TaskName = "Start Local AI WSL"
if ($Action -eq "Uninstall") {
    Unregister-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    exit 0
}
if (-not $Distro) {
    $Distro = (& wsl.exe --list --quiet | ForEach-Object { ($_ -replace "`0", "").Trim() } | Where-Object { $_ } | Select-Object -First 1)
}
if (-not $Distro) { throw "No WSL distribution was detected." }
$Wsl = Join-Path $env:WINDIR "System32\wsl.exe"
$Arguments = "-d `"$Distro`" --exec /bin/true"
$TaskAction = New-ScheduledTaskAction -Execute $Wsl -Argument $Arguments
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$Trigger.Delay = "PT10S"
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -StartWhenAvailable
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName -Action $TaskAction -Trigger $Trigger -Settings $Settings -Principal $Principal -Description "Starts WSL at Windows sign-in so the Local AI system service starts automatically." -Force | Out-Null
$Shortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "Local AI.url"
@("[InternetShortcut]", "URL=http://127.0.0.1:8181", "IconIndex=0") | Set-Content -Path $Shortcut -Encoding ASCII
