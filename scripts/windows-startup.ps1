[CmdletBinding()]
param(
    [ValidateSet("Install", "Start", "Restart", "Status", "Uninstall")]
    [string]$Action = "Install",
    [ValidateSet("WSL", "Native")]
    [string]$Mode = "WSL",
    [string]$Distro = "",
    [int]$AppPort = 0,
    [switch]$SkipWslValidation
)

$ErrorActionPreference = "Stop"
$TaskPath = "\Local AI\"
$TaskName = if ($Mode -eq "WSL") { "Start Local AI WSL" } else { "Start Local AI Windows" }
$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ($AppPort -eq 0) { $AppPort = if ($env:LOCAL_AI_PORT) { [int]$env:LOCAL_AI_PORT } else { 8181 } }
$HealthUrl = "http://127.0.0.1:$AppPort/api/health"

function Resolve-WslDistro {
    if ($Distro) { return $Distro }
    try {
        $Lxss = Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss" -ErrorAction Stop
        $Default = Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss\$($Lxss.DefaultDistribution)" -ErrorAction Stop
        if ($Default.DistributionName) { return $Default.DistributionName }
    } catch {}
    $First = (& wsl.exe --list --quiet | ForEach-Object { ($_ -replace "`0", "").Trim() } | Where-Object { $_ } | Select-Object -First 1)
    if (-not $First) { throw "No WSL distribution is installed." }
    return $First
}

$ResolvedDistro = if ($Mode -eq "WSL") { Resolve-WslDistro } else { $null }

function Get-StartupAction {
    if ($Mode -eq "WSL") {
        $Wsl = Join-Path $env:WINDIR "System32\wsl.exe"
        $Arguments = "-d `"$ResolvedDistro`" --exec systemctl --user start local-ai-stack.target"
        return (New-ScheduledTaskAction -Execute $Wsl -Argument $Arguments)
    }
    $PowerShell = Join-Path $PSHOME "powershell.exe"
    $RunScript = Join-Path $ProjectDir "run.ps1"
    return (New-ScheduledTaskAction -Execute $PowerShell -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$RunScript`"" -WorkingDirectory $ProjectDir)
}

function Install-StartupTask {
    if ($Mode -eq "WSL") {
        if (-not $SkipWslValidation) {
            $null = & wsl.exe -d $ResolvedDistro --exec /bin/true
            if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "WSL distribution '$ResolvedDistro' could not be started." }
            $null = & wsl.exe -d $ResolvedDistro --exec systemctl --user is-enabled local-ai-stack.target
            if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "Install the WSL services first with scripts/service.sh install." }
        }
    } elseif (-not (Test-Path (Join-Path $ProjectDir ".venv\Scripts\python.exe"))) {
        throw "Native Windows setup is incomplete. Run scripts/setup.ps1 first."
    }

    $Trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
    $Trigger.Delay = "PT10S"
    $Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -MultipleInstances IgnoreNew -StartWhenAvailable
    $Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName -Action (Get-StartupAction) `
        -Trigger $Trigger -Settings $Settings -Principal $Principal -Description "Starts the private Local AI stack at Windows sign-in." -Force | Out-Null

    $Shortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "Local AI.url"
    @("[InternetShortcut]", "URL=http://localhost:$AppPort", "IconIndex=0") | Set-Content -Path $Shortcut -Encoding ASCII
    Write-Host "Installed scheduled task $TaskPath$TaskName and updated $Shortcut"
}

function Show-Status {
    $Task = Get-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($Task) {
        $Info = Get-ScheduledTaskInfo -TaskPath $TaskPath -TaskName $TaskName
        [pscustomobject]@{ Task = "$TaskPath$TaskName"; State = $Task.State; LastRun = $Info.LastRunTime; LastResult = $Info.LastTaskResult } | Format-List
    } else {
        Write-Host "Scheduled task is not installed."
    }
    try {
        $Health = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 3
        Write-Host "Application: healthy ($($Health.runtime.model.display_name))"
    } catch {
        Write-Host "Application: not ready at $HealthUrl"
    }
    if ($Mode -eq "WSL") {
        & wsl.exe -d $ResolvedDistro --exec systemctl --user --no-pager --plain is-active local-ai-stack.target local-ai.service
    }
}

try {
    switch ($Action) {
        "Install" { Install-StartupTask; Start-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName }
        "Start" { Start-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName }
        "Restart" {
            if ($Mode -eq "WSL") {
                & wsl.exe -d $ResolvedDistro --exec systemctl --user restart local-ai.service
                & wsl.exe -d $ResolvedDistro --exec systemctl --user start local-ai-stack.target
            } else {
                Stop-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName -ErrorAction SilentlyContinue
                Start-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName
            }
        }
        "Status" { Show-Status }
        "Uninstall" {
            Unregister-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
            Write-Host "Removed scheduled task $TaskPath$TaskName. Application data and WSL services were preserved."
        }
    }
} catch {
    Write-Error $_
    exit 1
}
