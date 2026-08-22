@echo off
REM ==============================================================================
REM AutoUSBIP-QT Client - Windows Standalone Release Builder
REM ==============================================================================

echo =============================================================
echo    AutoUSBIP-QT Client - Windows EXE Release Builder
echo =============================================================

cd /d "%~dp0\.."

if not exist client\venv (
    echo [1/4] Creating virtual environment...
    python -m venv client\venv
)

echo [2/4] Installing dependencies and PyInstaller...
call client\venv\Scripts\activate.bat
pip install -r client\requirements.txt
pip install pyinstaller

echo [3/4] Building standalone Windows executable...
pyinstaller --clean --noconfirm packaging\autousbip-client.spec

echo [4/4] Bundling release files into dist\AutoUSBIP-QT-Windows...
if not exist dist\AutoUSBIP-QT-Windows mkdir dist\AutoUSBIP-QT-Windows
xcopy /E /I /Y dist\autousbip-qt-client\* dist\AutoUSBIP-QT-Windows\
copy /Y scripts\setup-windows-driver.ps1 dist\AutoUSBIP-QT-Windows\

echo.
echo =============================================================
echo  SUCCESS: Windows build ready in dist\AutoUSBIP-QT-Windows\
echo  Launch with: dist\AutoUSBIP-QT-Windows\autousbip-qt-client.exe
echo =============================================================
