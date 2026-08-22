@echo off
setlocal EnableExtensions

REM ==============================================================================
REM AutoUSBIP-QT MSI Installer Builder for Windows
REM ==============================================================================

pushd "%~dp0\.."
set "PROJECT_ROOT=%CD%"

echo =========================================================
echo   Building AutoUSBIP-QT-Client Windows MSI Installer
echo =========================================================

set "DIST_DIR=%PROJECT_ROOT%\dist"
set "CLIENT_EXE=%DIST_DIR%\autousbip-qt-client.exe"

if not exist "%CLIENT_EXE%" (
    echo [*] Compiling client executable first...
    call "%PROJECT_ROOT%\scripts\build-windows-client-exe.bat" --no-pause
)

if not exist "%CLIENT_EXE%" (
    echo [ERROR] Client executable not found at %CLIENT_EXE%
    if "%~1" NEQ "--no-pause" pause
    popd
    exit /b 1
)

set "WIX_DIR=%PROJECT_ROOT%\tools\wix"
set "CANDLE_EXE=%WIX_DIR%\candle.exe"
set "LIGHT_EXE=%WIX_DIR%\light.exe"

if not exist "%CANDLE_EXE%" (
    if defined WIX (
        set "WIX_DIR=%WIX%bin"
        set "CANDLE_EXE=%WIX%bin\candle.exe"
        set "LIGHT_EXE=%WIX%bin\light.exe"
    ) else if exist "C:\Program Files (x86)\WiX Toolset v3.11\bin\candle.exe" (
        set "WIX_DIR=C:\Program Files (x86)\WiX Toolset v3.11\bin"
        set "CANDLE_EXE=C:\Program Files (x86)\WiX Toolset v3.11\bin\candle.exe"
        set "LIGHT_EXE=C:\Program Files (x86)\WiX Toolset v3.11\bin\light.exe"
    ) else if exist "C:\Program Files (x86)\WiX Toolset v3.14\bin\candle.exe" (
        set "WIX_DIR=C:\Program Files (x86)\WiX Toolset v3.14\bin"
        set "CANDLE_EXE=C:\Program Files (x86)\WiX Toolset v3.14\bin\candle.exe"
        set "LIGHT_EXE=C:\Program Files (x86)\WiX Toolset v3.14\bin\light.exe"
    )
)

if not exist "%CANDLE_EXE%" (
    echo [*] Downloading portable WiX Toolset v3.11 binaries...
    mkdir "%PROJECT_ROOT%\tools\wix" >nul 2>&1
    curl -sL -o "%TEMP%\wix311-binaries.zip" "https://github.com/wixtoolset/wix3/releases/download/wix3112rtm/wix311-binaries.zip"
    powershell -NoProfile -Command "Expand-Archive -Path "$env:TEMP\wix311-binaries.zip" -DestinationPath "%PROJECT_ROOT%\tools\wix" -Force" >nul 2>&1
    del /f /q "%TEMP%\wix311-binaries.zip" >nul 2>&1
    set "WIX_DIR=%PROJECT_ROOT%\tools\wix"
    set "CANDLE_EXE=%WIX_DIR%\candle.exe"
    set "LIGHT_EXE=%WIX_DIR%\light.exe"
)

if not exist "%CANDLE_EXE%" (
    echo [ERROR] WiX candle.exe could not be found or downloaded.
    if "%~1" NEQ "--no-pause" pause
    popd
    exit /b 1
)

REM Ensure USB/IP Windows drivers are present before building MSI
if not exist "%PROJECT_ROOT%\client\drivers\usbip.exe" (
    echo [*] Fetching signed USB/IP-Win driver package for MSI bundling...
    mkdir "%PROJECT_ROOT%\client\drivers" >nul 2>&1
    curl -sL -o "%TEMP%\usbip-win.zip" "https://github.com/cezanne/usbip-win/releases/download/v0.3.6-dev/usbip-win-0.3.6-dev.zip"
    powershell -NoProfile -Command "Expand-Archive -Path \"%TEMP%\usbip-win.zip\" -DestinationPath \"%PROJECT_ROOT%\client\drivers\" -Force"
    if exist "%TEMP%\usbip-win.zip" del /f /q "%TEMP%\usbip-win.zip" >nul 2>&1
)

echo [*] Using WiX from: %WIX_DIR%

REM Use local fast C:\ temp directory for building and linking
set "MSI_WORK=%TEMP%\autousbip_msi_build"
set "LOCAL_MSI_OUT=%TEMP%\autousbip_msi_build\AutoUSBIP-QT-Client-Setup.msi"
if exist "%MSI_WORK%" rmdir /s /q "%MSI_WORK%" >nul 2>&1
mkdir "%MSI_WORK%" >nul 2>&1

echo.
echo [*] Compiling WiX Source...
"%CANDLE_EXE%" -nologo -arch x64 -ext WixUtilExtension "-dSourceDir=%PROJECT_ROOT%\client" "-dDistDir=%DIST_DIR%" -out "%MSI_WORK%\autousbip-client.wixobj" "%PROJECT_ROOT%\packaging\autousbip-client.wxs"
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] WiX candle failed with exit code %ERRORLEVEL%
    if "%~1" NEQ "--no-pause" pause
    popd
    exit /b %ERRORLEVEL%
)

echo.
echo [*] Linking MSI Installer...
"%LIGHT_EXE%" -nologo -sval -ext WixUIExtension -ext WixUtilExtension -out "%LOCAL_MSI_OUT%" "%MSI_WORK%\autousbip-client.wixobj"
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] WiX light failed with exit code %ERRORLEVEL%
    if "%~1" NEQ "--no-pause" pause
    popd
    exit /b %ERRORLEVEL%
)

if not exist "%DIST_DIR%" mkdir "%DIST_DIR%" >nul 2>&1
set "OUTPUT_MSI=%DIST_DIR%\AutoUSBIP-QT-Client-Setup.msi"

echo [*] Copying MSI installer to %OUTPUT_MSI%...
copy /Y "%LOCAL_MSI_OUT%" "%OUTPUT_MSI%" >nul

if exist "%MSI_WORK%" rmdir /s /q "%MSI_WORK%" >nul 2>&1

echo.
echo =========================================================
echo   SUCCESS! Windows MSI Installer is ready:
echo   %OUTPUT_MSI%
echo =========================================================

if "%~1" NEQ "--no-pause" pause
popd
endlocal
