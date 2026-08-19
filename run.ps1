$ErrorActionPreference = "Stop"
$ProjectDir = $PSScriptRoot
Set-Location $ProjectDir
$Python = Join-Path $ProjectDir ".venv\Scripts\python.exe"
if (-not (Test-Path $Python) -or -not (Test-Path "frontend\dist\index.html")) {
    throw "Setup is incomplete. Run scripts\setup.ps1 first."
}
$env:PYTHONPATH = $ProjectDir
& $Python -m backend.app.run
