@echo off
setlocal enabledelayedexpansion

REM ==============================================================================
REM AutoUSBIP-QT Standalone Windows Server Executable Builder
REM Builds standalone autousbip-qt-server.exe into dist\AutoUSBIP-QT-Server-Windows\
REM ==============================================================================

cd /d "%~dp0\.."
set "PROJECT_ROOT=%CD%"

echo =========================================================
echo   Building Standalone AutoUSBIP-Server.exe for Windows
echo =========================================================

REM 1. Locate Python
set "PYTHON_EXE="

if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PYTHON_EXE if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PYTHON_EXE if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
if not defined PYTHON_EXE if exist "C:\Program Files\Python311\python.exe" set "PYTHON_EXE=C:\Program Files\Python311\python.exe"
if not defined PYTHON_EXE if exist "C:\Program Files\Python312\python.exe" set "PYTHON_EXE=C:\Program Files\Python312\python.exe"
if not defined PYTHON_EXE if exist "C:\Python311\python.exe" set "PYTHON_EXE=C:\Python311\python.exe"

if not defined PYTHON_EXE (
    for /f "tokens=*" %%i in ('where python.exe 2^>nul') do (
        echo %%i | findstr /i "WindowsApps" >nul
        if errorlevel 1 (
            if not defined PYTHON_EXE set "PYTHON_EXE=%%i"
        )
    )
)

if not defined PYTHON_EXE (
    echo [!] Python 3 was not found. Please install Python from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [*] Using Python: %PYTHON_EXE%

REM 2. Setup build environment
set "BUILD_VENV=%PROJECT_ROOT%\client\venv_build"
set "VENV_PYTHON=%BUILD_VENV%\Scripts\python.exe"
set "VENV_PIP=%BUILD_VENV%\Scripts\pip.exe"
set "VENV_PYINSTALLER=%BUILD_VENV%\Scripts\pyinstaller.exe"

if not exist "%VENV_PIP%" (
    echo [1/3] Setting up Python virtual environment...
    "%PYTHON_EXE%" -m venv "%BUILD_VENV%"
    "%VENV_PYTHON%" -m pip install --upgrade pip
    "%VENV_PIP%" install pyinstaller
)

REM 3. Build in local temporary directory on C:
set "LOCAL_WORK=%TEMP%\autousbip_server_build"
set "LOCAL_DIST=%TEMP%\autousbip_server_dist"
if exist "%LOCAL_WORK%" rmdir /s /q "%LOCAL_WORK%" >nul 2>&1
if exist "%LOCAL_DIST%" rmdir /s /q "%LOCAL_DIST%" >nul 2>&1

echo [2/3] Compiling standalone server binary with PyInstaller...
"%VENV_PYINSTALLER%" --clean --noconfirm --onefile --name "autousbip-qt-server" --workpath "%LOCAL_WORK%" --distpath "%LOCAL_DIST%" "%PROJECT_ROOT%\server\autousbip.py"

REM 4. Copy to dist\AutoUSBIP-QT-Server-Windows
set "OUT_DIR=%PROJECT_ROOT%\dist\AutoUSBIP-QT-Server-Windows"
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%" >nul 2>&1

if exist "%LOCAL_DIST%\autousbip-qt-server.exe" (
    echo [3/3] Finalizing build artifacts in %OUT_DIR%...
    copy /y "%LOCAL_DIST%\autousbip-qt-server.exe" "%OUT_DIR%\autousbip-qt-server.exe" >nul
)

REM Clean temp directories
if exist "%LOCAL_WORK%" rmdir /s /q "%LOCAL_WORK%" >nul 2>&1
if exist "%LOCAL_DIST%" rmdir /s /q "%LOCAL_DIST%" >nul 2>&1

if exist "%OUT_DIR%\autousbip-qt-server.exe" (
    echo.
    echo =========================================================
    echo   SUCCESS! Windows Server binary is ready:
    echo   %OUT_DIR%\autousbip-qt-server.exe
    echo =========================================================
) else (
    echo.
    echo [!] Build finished, but output file was not found in destination.
)

pause
endlocal
