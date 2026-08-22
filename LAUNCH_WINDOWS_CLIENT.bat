@echo off
pushd "%~dp0"
title AutoUSBIP-QT Windows Launcher

echo =========================================================
echo   AutoUSBIP-QT Client - Windows Auto-Launcher
echo =========================================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [!] Python is not installed or not in PATH.
    echo Please install Python 3.10+ from python.org or via winget:
    echo winget install Python.Python.3.11
    echo.
    pause
    popd
    exit /b 1
)

if not exist client\venv_win (
    echo [*] Creating virtual environment (client\venv_win)...
    python -m venv client\venv_win
    echo [*] Installing requirements (PyQt6, QtWebEngine, zeroconf)...
    call client\venv_win\Scripts\pip.exe install -r client\requirements.txt
)

if not exist client\bin\usbip.exe (
    echo [*] Setting up USB/IP Windows driver...
    powershell.exe -ExecutionPolicy Bypass -File scripts\setup-windows-driver.ps1
)

echo [*] Starting AutoUSBIP-QT Client...
call client\venv_win\Scripts\python.exe client\client.py

if errorlevel 1 (
    echo.
    echo Application exited with an error.
    pause
)

popd
