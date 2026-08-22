# Auto USB/IP - Windows Driver Automated Setup
# Downloads, unpacks, and installs the signed USB/IP-Win VHCI virtual USB driver package.

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Auto USB/IP Qt - Automated Windows Driver Installer     " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Check for Administrator privileges
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Warning "Administrator rights required to install Windows kernel drivers."
    Write-Host "Relaunching with elevated privileges..." -ForegroundColor Yellow
    Start-Process powershell.exe -ArgumentList ("-NoProfile -ExecutionPolicy Bypass -File `"{0}`"" -f $MyInvocation.MyCommand.Path) -Verb RunAs
    exit
}

$workDir = Join-Path $env:TEMP "autousbip-win-setup"
if (Test-Path $workDir) { Remove-Item -Recurse -Force $workDir }
New-Item -ItemType Directory -Path $workDir | Out-Null

$appBinDir = Join-Path $PSScriptRoot "..\client\bin"
if (-not (Test-Path $appBinDir)) {
    New-Item -ItemType Directory -Path $appBinDir -Force | Out-Null
}

$zipUrl = "https://github.com/cezanne/usbip-win/releases/download/v0.3.6-dev/usbip-win-0.3.6-dev.zip"
$zipPath = Join-Path $workDir "usbip-win.zip"

Write-Host "[1/3] Downloading usbip-win signed driver package..." -ForegroundColor Green
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13
Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing

Write-Host "[2/3] Extracting driver files..." -ForegroundColor Green
Expand-Archive -Path $zipPath -DestinationPath $workDir -Force

$extractedDir = Get-ChildItem -Path $workDir -Directory | Select-Object -First 1
$sourceFiles = if ($extractedDir) { $extractedDir.FullName } else { $workDir }

# Copy binaries to client/bin
Get-ChildItem -Path $sourceFiles -Recurse -Include "usbip.exe", "usbip_test.exe", "*.sys", "*.inf", "*.cer" | ForEach-Object {
    Copy-Item $_.FullName -Destination $appBinDir -Force
    Write-Host "  -> Bundled: $($_.Name)" -ForegroundColor DarkGray
}

Write-Host "[3/3] Installing USB/IP Virtual Host Controller Interface (VHCI)..." -ForegroundColor Green
$infFile = Get-ChildItem -Path $appBinDir -Filter "usbip_vhci.inf" -Recurse | Select-Object -First 1

if ($infFile) {
    # Install certificate if present
    $cerFile = Get-ChildItem -Path $appBinDir -Filter "*.cer" -Recurse | Select-Object -First 1
    if ($cerFile) {
        Write-Host "  -> Trusting driver certificate..." -ForegroundColor DarkGray
        certutil -addstore "TrustedPublisher" $cerFile.FullName | Out-Null
        certutil -addstore "Root" $cerFile.FullName | Out-Null
    }

    Write-Host "  -> Installing VHCI driver INF via pnputil..." -ForegroundColor DarkGray
    pnputil /add-driver $infFile.FullName /install
    Write-Host "`n✅ USB/IP Windows driver installed successfully!" -ForegroundColor Green
} else {
    Write-Warning "INF file not found in extracted bundle. Ensure usbip.exe is placed in client/bin/."
}

Write-Host "`nSetup complete. You can now launch Auto USB/IP Qt Client." -ForegroundColor Cyan
