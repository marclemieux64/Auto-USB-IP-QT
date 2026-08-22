@echo off
title AutoUSBIP-QT Windows Launcher
cd /d "%~dp0"

echo =========================================================
echo   AutoUSBIP-QT Client - Windows Auto-Launcher
echo =========================================================
echo.

REM 1. Check Python
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] Python is not installed or not in PATH.
    echo Please install Python 3.10+ from python.org (check "Add Python to PATH").
    echo.
    pause
    exit /b 1
)

REM 2. Create and Activate Virtual Environment
if not exist client\venv_win (
    echo [*] Creating virtual environment (client\venv_win)...
    python -m venv client\venv_win
    echo [*] Installing requirements (PyQt6, QtWebEngine, zeroconf)...
    call client\venv_win\Scripts\pip install -r client\requirements.txt
)

REM 3. Ensure Windows Driver is downloaded & installed
if not exist client\bin\usbip.exe (
    echo [*] Setting up USB/IP Windows driver...
    powershell -ExecutionPolicy Bypass -File scripts\setup-windows-driver.ps1
)

REM 4. Launch the application
echo [*] Starting AutoUSBIP-QT Client...
call client\venv_win\Scripts\python.exe client\client.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application exited with an error.
    pause
)
