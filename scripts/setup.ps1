$ErrorActionPreference = "Stop"
$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectDir

function Refresh-Path {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

function Ensure-Command([string]$Name, [string]$WingetId) {
    if (Get-Command $Name -ErrorAction SilentlyContinue) { return }
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        throw "$Name is required and winget is unavailable. Install $Name, then rerun setup.ps1."
    }
    winget install --id $WingetId --exact --accept-package-agreements --accept-source-agreements
    Refresh-Path
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name was installed but is not available in this terminal. Open a new PowerShell window and rerun setup.ps1."
    }
}

function Find-Python {
    $Candidates = @()
    $Command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($Command -and $Command.Source -notlike "*\WindowsApps\*") { $Candidates += $Command.Source }
    $Candidates += @(Get-ChildItem (Join-Path $env:LOCALAPPDATA "Programs\Python\Python*\python.exe") -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
    foreach ($Candidate in $Candidates) {
        & $Candidate -c "import sys; assert sys.version_info >= (3, 11)" 2>$null
        if ($LASTEXITCODE -eq 0) { return $Candidate }
    }
    return $null
}

$SystemPython = Find-Python
if (-not $SystemPython) {
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        throw "Python 3.11+ is required and winget is unavailable. Install Python, then rerun setup.ps1."
    }
    winget install --id "Python.Python.3.12" --exact --accept-package-agreements --accept-source-agreements
    Refresh-Path
    $SystemPython = Find-Python
    if (-not $SystemPython) { throw "Python was installed but could not be located. Open a new PowerShell window and rerun setup.ps1." }
}
Ensure-Command "node.exe" "OpenJS.NodeJS.LTS"
Ensure-Command "npm.cmd" "OpenJS.NodeJS.LTS"
node.exe -e "const [a,b]=process.versions.node.split('.').map(Number);const ok=(a===20&&b>=19)||(a===22&&b>=12)||a>=24;if(!ok)throw new Error('Node.js 20.19+, 22.12+, or 24+ is required')"

$Pnpm = Get-Command pnpm.cmd -ErrorAction SilentlyContinue
if (-not $Pnpm) {
    Write-Host "Installing pnpm 11.21.0..."
    npm.cmd install --global pnpm@11.21.0
    Refresh-Path
    $Pnpm = Get-Command pnpm.cmd -ErrorAction SilentlyContinue
    if (-not $Pnpm) { throw "pnpm was installed but is not available. Open a new PowerShell window and rerun setup.ps1." }
}

$LlamaCandidates = @(
    (Get-Command llama-server.exe -ErrorAction SilentlyContinue),
    (Get-Command llama.exe -ErrorAction SilentlyContinue)
) | Where-Object { $_ }
$InstalledLlama = Join-Path $HOME ".llama-app\llama.exe"
if ($LlamaCandidates.Count -eq 0 -and -not (Test-Path $InstalledLlama)) {
    Write-Host "Installing the official llama.cpp runtime with hardware detection..."
    $Installer = Join-Path ([IO.Path]::GetTempPath()) "local-ai-llama-install.ps1"
    Invoke-WebRequest -UseBasicParsing "https://llama.app/install.ps1" -OutFile $Installer
    & $Installer
    Remove-Item $Installer -Force -ErrorAction SilentlyContinue
}

& $SystemPython -c "import sys; assert sys.version_info >= (3, 11), 'Python 3.11 or newer is required'"
& $SystemPython -m venv .venv
$Python = Join-Path $ProjectDir ".venv\Scripts\python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install -r backend\requirements.txt

& $Pnpm.Source install --frozen-lockfile
& $Pnpm.Source build

$env:PYTHONPATH = $ProjectDir
& $Python -c 'from backend.app.database import initialize_database; from backend.app.services.model_scanner import scan_models; from backend.app.services.host_profile import apply_recommendations; initialize_database(); models=scan_models(); profile,settings,_=apply_recommendations(); gpu=profile["gpus"][0]["name"] if profile["gpus"] else "CPU inference"; print("Database initialized. {} GGUF model(s) found.".format(len(models))); print("Detected: {} - {:.1f} GB RAM - {}".format(profile["cpu"]["name"], profile["memory"]["total_bytes"] / 2**30, gpu)); print("Recommended: {} context - {} threads - {} GPU layers".format(settings["context_size"], settings["threads"], settings["gpu_layers"]))'

Write-Host ""
Write-Host "Setup complete."
Write-Host "1. Put a .gguf model in: $ProjectDir\models"
Write-Host "2. Run: $ProjectDir\run.ps1"
Write-Host "3. Open: http://127.0.0.1:8181"
Write-Host "4. For automatic Windows startup: .\scripts\windows-startup.ps1 -Mode Native"
