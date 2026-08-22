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
    pause
    popd
    exit /b 1
)

set "WIX_DIR=%PROJECT_ROOT%\tools\wix"
set "CANDLE_EXE=%WIX_DIR%\candle.exe"
set "LIGHT_EXE=%WIX_DIR%\light.exe"

if not exist "%CANDLE_EXE%" (
    echo [ERROR] WiX candle.exe not found in %WIX_DIR%
    pause
    popd
    exit /b 1
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
    pause
    popd
    exit /b %ERRORLEVEL%
)

echo.
echo [*] Linking MSI Installer...
"%LIGHT_EXE%" -nologo -sval -ext WixUIExtension -ext WixUtilExtension -out "%LOCAL_MSI_OUT%" "%MSI_WORK%\autousbip-client.wixobj"
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] WiX light failed with exit code %ERRORLEVEL%
    pause
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

pause
popd
endlocal
