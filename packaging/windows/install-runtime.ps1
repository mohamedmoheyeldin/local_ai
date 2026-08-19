[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$AppDirectory,
    [Parameter(Mandatory = $true)][string]$AppExecutable
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$DataDirectory = Join-Path $env:LOCALAPPDATA "PortableLocalAI"
$RuntimeDirectory = Join-Path $DataDirectory "runtime"
$LogPath = Join-Path $DataDirectory "install.log"
New-Item -ItemType Directory -Path $RuntimeDirectory -Force | Out-Null

function Write-InstallLog([string]$Message) {
    "$(Get-Date -Format o) $Message" | Add-Content -Path $LogPath -Encoding UTF8
}

function Save-Asset($Asset, [string]$Destination) {
    if (-not $Asset.digest -or -not ([string]$Asset.digest).StartsWith("sha256:")) {
        throw "GitHub did not provide a SHA-256 digest for $($Asset.name)"
    }
    Invoke-WebRequest -UseBasicParsing -Headers @{ Accept = "application/vnd.github+json"; "User-Agent" = "Portable-Local-AI-Installer" } -Uri $Asset.browser_download_url -OutFile $Destination
    $Actual = (Get-FileHash -Algorithm SHA256 -Path $Destination).Hash.ToLowerInvariant()
    $Expected = ([string]$Asset.digest).Substring(7).ToLowerInvariant()
    if ($Actual -ne $Expected) { throw "Checksum validation failed for $($Asset.name)" }
}

function Configure-Runtime([string]$Executable) {
    & $AppExecutable --configure-runtime $Executable | Add-Content -Path $LogPath -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { throw "Application initialization failed with exit code $LASTEXITCODE" }
}

try {
    Write-InstallLog "Starting native Windows installation finalization."
    $Existing = Get-Command llama-server.exe -ErrorAction SilentlyContinue
    if (-not $Existing) { $Existing = Get-Command llama.exe -ErrorAction SilentlyContinue }
    if ($Existing) {
        Write-InstallLog "Using existing llama.cpp runtime: $($Existing.Source)"
        Configure-Runtime $Existing.Source
    } else {
        $GpuNames = @(Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name)
        $Backend = if ($GpuNames -match "NVIDIA") { "cuda12" } elseif ($GpuNames -match "AMD|Radeon|Intel|Arc") { "vulkan" } else { "cpu" }
        Write-InstallLog "Detected runtime backend: $Backend ($($GpuNames -join ', '))"
        $Release = Invoke-RestMethod -UseBasicParsing -Headers @{ Accept = "application/vnd.github+json"; "User-Agent" = "Portable-Local-AI-Installer" } -Uri "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest"
        $Suffix = switch ($Backend) {
            "cuda12" { "bin-win-cuda-12.4-x64.zip" }
            "vulkan" { "bin-win-vulkan-x64.zip" }
            default { "bin-win-cpu-x64.zip" }
        }
        $Asset = @($Release.assets | Where-Object { $_.name.EndsWith($Suffix) }) | Select-Object -First 1
        if (-not $Asset) { throw "No official llama.cpp asset matched $Suffix" }
        $Temporary = Join-Path ([IO.Path]::GetTempPath()) "portable-local-ai-runtime-$([Guid]::NewGuid().ToString('N'))"
        New-Item -ItemType Directory -Path $Temporary | Out-Null
        try {
            $Archive = Join-Path $Temporary "runtime.zip"
            Save-Asset $Asset $Archive
            Expand-Archive -Path $Archive -DestinationPath $RuntimeDirectory -Force
            if ($Backend -eq "cuda12") {
                $CudaAsset = @($Release.assets | Where-Object { $_.name -eq "cudart-llama-bin-win-cuda-12.4-x64.zip" }) | Select-Object -First 1
                if (-not $CudaAsset) { throw "The official CUDA runtime asset was unavailable" }
                $CudaArchive = Join-Path $Temporary "cudart.zip"
                Save-Asset $CudaAsset $CudaArchive
                Expand-Archive -Path $CudaArchive -DestinationPath $RuntimeDirectory -Force
            }
            $Downloaded = Get-ChildItem $RuntimeDirectory -Filter "llama-server.exe" -Recurse | Select-Object -First 1
            if (-not $Downloaded) { throw "llama-server.exe was missing after extraction" }
            Write-InstallLog "Installed verified llama.cpp $($Release.tag_name): $($Asset.name)"
            Configure-Runtime $Downloaded.FullName
        } finally {
            Remove-Item $Temporary -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
} catch {
    Write-InstallLog "Optimized runtime setup failed: $($_.Exception.Message)"
    $Bundled = Get-ChildItem (Join-Path $AppDirectory "_internal\runtime") -Filter "llama-server.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $Bundled) { throw }
    Write-InstallLog "Using bundled CPU fallback: $($Bundled.FullName)"
    Configure-Runtime $Bundled.FullName
}

try {
    $Action = New-ScheduledTaskAction -Execute $AppExecutable -Argument "--no-browser" -WorkingDirectory $AppDirectory
    $Trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
    $Trigger.Delay = "PT10S"
    $Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -StartWhenAvailable
    $Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskPath "\Portable Local AI\" -TaskName "Start Portable Local AI" -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Description "Starts Portable Local AI privately at sign-in." -Force | Out-Null
    Write-InstallLog "Registered per-user startup task."
} catch {
    Write-InstallLog "Startup task registration failed: $($_.Exception.Message)"
}

Write-InstallLog "Installation finalization completed."
