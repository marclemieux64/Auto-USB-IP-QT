# AutoUSBIP-QT Windows PowerShell Launcher
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "  AutoUSBIP-QT Client - Windows Launcher                " -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check Python
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "[!] Python is not installed or not in PATH." -ForegroundColor Red
    Write-Host "Installing Python via winget..." -ForegroundColor Yellow
    winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}

# 2. Virtual Environment
$venvDir = Join-Path $ScriptDir "client\venv_win"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$venvPip = Join-Path $venvDir "Scripts\pip.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "[*] Creating virtual environment ($venvDir)..." -ForegroundColor Green
    python -m venv $venvDir
    Write-Host "[*] Installing dependencies (PyQt6, QtWebEngine, zeroconf)..." -ForegroundColor Green
    & $venvPip install -r (Join-Path $ScriptDir "client\requirements.txt")
}

# 3. Check Driver
$usbipBin = Join-Path $ScriptDir "client\bin\usbip.exe"
if (-not (Test-Path $usbipBin)) {
    Write-Host "[*] Setting up USB/IP Windows driver..." -ForegroundColor Green
    & powershell.exe -ExecutionPolicy Bypass -File (Join-Path $ScriptDir "scripts\setup-windows-driver.ps1")
}

# 4. Launch Client
Write-Host "[*] Starting AutoUSBIP-QT Client..." -ForegroundColor Cyan
& $venvPython (Join-Path $ScriptDir "client\client.py")
