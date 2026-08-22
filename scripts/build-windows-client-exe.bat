@echo off
setlocal enabledelayedexpansion

REM ==============================================================================
REM AutoUSBIP-QT Standalone Single-File Windows Release Builder
REM Builds a single self-contained autousbip-qt-client.exe into dist\
REM ==============================================================================

cd /d "%~dp0\.."
set "PROJECT_ROOT=%CD%"

echo =========================================================
echo   Building Single-File AutoUSBIP-Client.exe for Windows
echo =========================================================

REM 1. Kill any running client instances
taskkill /F /IM autousbip-qt-client.exe >nul 2>&1
taskkill /F /IM python.exe /FI "WINDOWTITLE eq autousbip*" >nul 2>&1

REM 2. Locate Python
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
    if "%~1" NEQ "--no-pause" pause
    exit /b 1
)

echo [*] Using Python: %PYTHON_EXE%

REM 3. Setup build environment on fast local C:\ drive
set "BUILD_VENV=%LOCALAPPDATA%\autousbip_win_venv"
set "VENV_PYTHON=%BUILD_VENV%\Scripts\python.exe"
set "VENV_PIP=%BUILD_VENV%\Scripts\pip.exe"
set "VENV_PYINSTALLER=%BUILD_VENV%\Scripts\pyinstaller.exe"

if not exist "%VENV_PIP%" (
    echo [1/3] Creating Python virtual environment in %BUILD_VENV%...
    "%PYTHON_EXE%" -m venv "%BUILD_VENV%"
    echo [1/3] Installing dependencies...
    "%VENV_PYTHON%" -m pip install --upgrade pip
    "%VENV_PIP%" install PyQt6 PyQt6-WebEngine pyserial zeroconf pyinstaller
)

REM 4. Build single-file EXE in local TEMP directory
set "LOCAL_WORK=%TEMP%\autousbip_build"
set "LOCAL_DIST=%TEMP%\autousbip_dist"
if exist "%LOCAL_WORK%" rmdir /s /q "%LOCAL_WORK%" >nul 2>&1
if exist "%LOCAL_DIST%" rmdir /s /q "%LOCAL_DIST%" >nul 2>&1

echo [2/3] Compiling single standalone executable with PyInstaller...
"%VENV_PYINSTALLER%" --clean --noconfirm --workpath "%LOCAL_WORK%" --distpath "%LOCAL_DIST%" "%PROJECT_ROOT%\packaging\autousbip-client-onefile.spec"

if not exist "%LOCAL_DIST%\autousbip-qt-client.exe" (
    echo [!] PyInstaller build failed.
    if "%~1" NEQ "--no-pause" pause
    exit /b 1
)

REM 5. Copy single standalone .exe to dist\
set "OUT_DIR=%PROJECT_ROOT%\dist"
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%" >nul 2>&1

echo [3/3] Deploying standalone binary to %OUT_DIR%\AutoUSBIP-QT-Client-Windows-x64.exe...
copy /Y "%LOCAL_DIST%\autousbip-qt-client.exe" "%OUT_DIR%\AutoUSBIP-QT-Client-Windows-x64.exe" >nul

REM Clean temp work files
if exist "%LOCAL_WORK%" rmdir /s /q "%LOCAL_WORK%" >nul 2>&1
if exist "%LOCAL_DIST%" rmdir /s /q "%LOCAL_DIST%" >nul 2>&1

if exist "%OUT_DIR%\AutoUSBIP-QT-Client-Windows-x64.exe" (
    echo.
    echo =========================================================
    echo   SUCCESS! Single-File Windows Standalone Binary is ready:
    echo   %OUT_DIR%\AutoUSBIP-QT-Client-Windows-x64.exe
    echo =========================================================
) else (
    echo.
    echo [!] Build finished, but binary was not found.
)

if "%~1" NEQ "--no-pause" pause
endlocal
