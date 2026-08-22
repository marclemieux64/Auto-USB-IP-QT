#!/usr/bin/env bash
# AutoUSBIP-QT Client - Desktop Menu Remover
set -e

echo "🗑️ Removing AutoUSBIP-QT Client from Application Menu..."
rm -f "${HOME}/.local/share/applications/org.autousbip.client.desktop"
rm -f "${HOME}/.local/share/icons/hicolor/scalable/apps/org.autousbip.client.svg"
rm -f "${HOME}/.local/share/icons/hicolor/512x512/apps/org.autousbip.client.png"
rm -f "${HOME}/.local/share/icons/hicolor/256x256/apps/org.autousbip.client.png"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${HOME}/.local/share/applications" 2>/dev/null || true
fi

echo "✅ Desktop shortcuts removed successfully."
