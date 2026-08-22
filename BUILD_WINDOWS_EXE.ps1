# AutoUSBIP-QT Standalone Windows EXE Builder
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "  Building Standalone AutoUSBIP-Client.exe for Windows   " -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan

# 1. Ensure Python
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "[*] Installing Python 3.11..." -ForegroundColor Yellow
    winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}

# 2. Setup build environment
$buildVenv = Join-Path $ScriptDir "client\venv_build"
$venvPip = Join-Path $buildVenv "Scripts\pip.exe"
$venvPyinstaller = Join-Path $buildVenv "Scripts\pyinstaller.exe"

if (-not (Test-Path $venvPip)) {
    Write-Host "[1/3] Setting up Python virtual environment for building..." -ForegroundColor Green
    python -m venv $buildVenv
    & $venvPip install --upgrade pip
    & $venvPip install -r (Join-Path $ScriptDir "client\requirements.txt")
    & $venvPip install pyinstaller
}

# 3. Build standalone single-file EXE
Write-Host "[2/3] Compiling standalone single EXE with PyInstaller..." -ForegroundColor Green
& $venvPyinstaller --clean --noconfirm (Join-Path $ScriptDir "packaging\autousbip-client-onefile.spec")

# 4. Copy to dist
$outDir = Join-Path $ScriptDir "dist"
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }

Write-Host "`n=========================================================" -ForegroundColor Green
Write-Host "  SUCCESS! Your standalone executable is ready:        " -ForegroundColor Green
Write-Host "  $outDir\AutoUSBIP-Client.exe" -ForegroundColor Yellow
Write-Host "=========================================================" -ForegroundColor Green
