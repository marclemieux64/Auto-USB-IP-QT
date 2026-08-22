#!/usr/bin/env bash
# ==============================================================================
# AutoUSBIP-QT Client - Portable Linux Tarball (.tar.gz) Builder
# Output: dist/AutoUSBIP-QT-Client-Linux-x86_64.tar.gz
# ==============================================================================

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

echo "📦 ============================================================="
echo "   AutoUSBIP-QT Client — Portable Tarball (.tar.gz) Builder      "
echo "============================================================="

# 1. Determine Python & PyInstaller
PYTHON_BIN="${REPO_ROOT}/client/venv/bin/python"
if [ ! -x "${PYTHON_BIN}" ]; then
    PYTHON_BIN="$(which python3)"
fi

PYINSTALLER_BIN="${REPO_ROOT}/client/venv/bin/pyinstaller"
if [ ! -x "${PYINSTALLER_BIN}" ]; then
    PYINSTALLER_BIN="$(which pyinstaller 2>/dev/null || true)"
fi

if [ -z "${PYINSTALLER_BIN}" ]; then
    echo "📦 Installing PyInstaller in virtual environment..."
    "${PYTHON_BIN}" -m pip install pyinstaller
    PYINSTALLER_BIN="${REPO_ROOT}/client/venv/bin/pyinstaller"
fi

# 2. Build Python standalone bundle with PyInstaller if needed
echo -e "\n[1/2] Freezing Python application and Qt6 runtime..."
"${PYINSTALLER_BIN}" --clean --noconfirm "${REPO_ROOT}/packaging/autousbip-client.spec"

# 3. Assemble Portable Tarball
echo -e "\n[2/2] Assembling portable standalone release tarball..."
TARBALL_STAGING="${REPO_ROOT}/build/autousbip-qt-client-linux-x86_64"
rm -rf "${TARBALL_STAGING}"
mkdir -p "${TARBALL_STAGING}"

# Copy binary payload
cp -r "${REPO_ROOT}/dist/autousbip-qt-client/"* "${TARBALL_STAGING}/"

# Copy icons and desktop helpers
cp -f "${REPO_ROOT}/packaging/org.autousbip.client.desktop" "${TARBALL_STAGING}/"
cp -f "${REPO_ROOT}/packaging/install-menu.sh" "${TARBALL_STAGING}/"
cp -f "${REPO_ROOT}/packaging/uninstall-menu.sh" "${TARBALL_STAGING}/"
chmod +x "${TARBALL_STAGING}/install-menu.sh" "${TARBALL_STAGING}/uninstall-menu.sh"

ICON_SVG="${REPO_ROOT}/client/assets/branding/app-icon.svg"
ICON_PNG="${REPO_ROOT}/client/assets/branding/app-icon.png"
if [ -f "${ICON_SVG}" ]; then
    cp -f "${ICON_SVG}" "${TARBALL_STAGING}/org.autousbip.client.svg"
fi
if [ -f "${ICON_PNG}" ]; then
    cp -f "${ICON_PNG}" "${TARBALL_STAGING}/org.autousbip.client.png"
fi

mkdir -p "${REPO_ROOT}/dist"
OUTPUT_TARBALL="${REPO_ROOT}/dist/AutoUSBIP-QT-Client-Linux-x86_64.tar.gz"
rm -f "${OUTPUT_TARBALL}"
tar -czf "${OUTPUT_TARBALL}" -C "${REPO_ROOT}/build" autousbip-qt-client-linux-x86_64

echo -e "\n============================================================="
echo "🎉 Build complete! Generated release tarball:"
echo "   📦 ${OUTPUT_TARBALL} ($(du -h "${OUTPUT_TARBALL}" 2>/dev/null | cut -f1 || echo ''))"
echo "============================================================="
