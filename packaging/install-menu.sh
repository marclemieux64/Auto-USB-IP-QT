#!/usr/bin/env bash
# Auto USB/IP Client - Desktop Menu Integrator for Portable Tarball
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="${DIR}/autousbip-client"
DESKTOP_DIR="${HOME}/.local/share/applications"
ICON_DIR="${HOME}/.local/share/icons/hicolor/scalable/apps"

mkdir -p "${DESKTOP_DIR}" "${ICON_DIR}"

# Copy icon
if [ -f "${DIR}/org.autousbip.client.svg" ]; then
    cp -f "${DIR}/org.autousbip.client.svg" "${ICON_DIR}/org.autousbip.client.svg"
fi

# Create desktop entry pointing to this folder
cat << DESKTOP_EOF > "${DESKTOP_DIR}/org.autousbip.client.desktop"
[Desktop Entry]
Name=Auto USB/IP Client
Comment=Automatic USB-over-IP device manager and gamepad tester
Exec="${BIN}" %u
Icon=org.autousbip.client
Terminal=false
Type=Application
Categories=Utility;Network;
Keywords=usb;usbip;remote;gamepad;controller;
StartupNotify=true
StartupWMClass=auto-usbip-client
DESKTOP_EOF

chmod 644 "${DESKTOP_DIR}/org.autousbip.client.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${DESKTOP_DIR}" 2>/dev/null || true
fi

echo "✅ Auto USB/IP Client successfully added to your Application Menu!"
echo "   Launcher: ${DESKTOP_DIR}/org.autousbip.client.desktop"
echo "   Binary:   ${BIN}"
