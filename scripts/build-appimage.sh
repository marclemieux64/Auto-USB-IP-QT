#!/usr/bin/env bash
# ==============================================================================
# AutoUSBIP-QT Client - Release Builder (AppImage + Portable Tarball)
# ==============================================================================

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

echo "🔨 ============================================================="
echo "   AutoUSBIP-QT Client — Release Builder (AppImage & Tarball)    "
echo "============================================================="

# 1. Determine Python and AppImageTool
PYTHON_BIN="${REPO_ROOT}/client/venv/bin/python"
if [ ! -x "${PYTHON_BIN}" ]; then
    PYTHON_BIN="$(which python3)"
fi

PYINSTALLER_BIN="${REPO_ROOT}/client/venv/bin/pyinstaller"
if [ ! -x "${PYINSTALLER_BIN}" ] || ! "${PYINSTALLER_BIN}" --version >/dev/null 2>&1; then
    PYINSTALLER_BIN="$(which pyinstaller 2>/dev/null || true)"
fi
if [ -z "${PYINSTALLER_BIN}" ] && [ -x "${HOME}/.local/bin/pyinstaller" ]; then
    PYINSTALLER_BIN="${HOME}/.local/bin/pyinstaller"
fi

if [ -z "${PYINSTALLER_BIN}" ]; then
    echo "📦 Installing PyInstaller in virtual environment..."
    "${PYTHON_BIN}" -m pip install pyinstaller
    PYINSTALLER_BIN="${REPO_ROOT}/client/venv/bin/pyinstaller"
fi

APPIMAGETOOL="${REPO_ROOT}/tools/appimagetool"
if [ ! -x "${APPIMAGETOOL}" ]; then
    echo "📦 Downloading appimagetool..."
    mkdir -p "${REPO_ROOT}/tools"
    curl -sL -o "${REPO_ROOT}/tools/appimagetool-x86_64.AppImage" "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "${REPO_ROOT}/tools/appimagetool-x86_64.AppImage"
    cd "${REPO_ROOT}/tools"
    ./appimagetool-x86_64.AppImage --appimage-extract >/dev/null 2>&1
    mv squashfs-root appimagetool-dist
    ln -sf appimagetool-dist/AppRun appimagetool
    rm -f appimagetool-x86_64.AppImage
    cd "${REPO_ROOT}"
fi

# 2. Build Python standalone bundle with PyInstaller
echo "\n[1/4] Freezing Python application and Qt6 runtime..."
"${PYINSTALLER_BIN}" --clean --noconfirm "${REPO_ROOT}/packaging/autousbip-client.spec"

# 3. Construct AppDir layout
echo "\n[2/4] Constructing AppDir structure..."
APPDIR="${REPO_ROOT}/build/AutoUSBIP-QT.AppDir"
rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin" "${APPDIR}/usr/share/metainfo"

# Copy AppRun, Desktop entries, and AppStream metadata
cp -f "${REPO_ROOT}/packaging/AppRun" "${APPDIR}/AppRun"
chmod +x "${APPDIR}/AppRun"

cp -f "${REPO_ROOT}/packaging/org.autousbip.client.desktop" "${APPDIR}/org.autousbip.client.desktop"
cp -f "${REPO_ROOT}/packaging/org.autousbip.client.desktop" "${APPDIR}/default.desktop" 2>/dev/null || true

if [ -f "${REPO_ROOT}/packaging/org.autousbip.client.metainfo.xml" ]; then
    cp -f "${REPO_ROOT}/packaging/org.autousbip.client.metainfo.xml" "${APPDIR}/usr/share/metainfo/org.autousbip.client.metainfo.xml"
    cp -f "${REPO_ROOT}/packaging/org.autousbip.client.metainfo.xml" "${APPDIR}/usr/share/metainfo/default.appdata.xml" 2>/dev/null || true
fi

# Copy icons
ICON_SVG="${REPO_ROOT}/client/assets/branding/app-icon.svg"
ICON_PNG="${REPO_ROOT}/client/assets/branding/app-icon.png"

if [ -f "${ICON_SVG}" ]; then
    cp -f "${ICON_SVG}" "${APPDIR}/org.autousbip.client.svg"
    cp -f "${ICON_SVG}" "${APPDIR}/.DirIcon"
fi

if [ -f "${ICON_PNG}" ]; then
    cp -f "${ICON_PNG}" "${APPDIR}/org.autousbip.client.png"
fi

# Copy frozen binaries and assets
cp -r "${REPO_ROOT}/dist/autousbip-qt-client/"* "${APPDIR}/usr/bin/"

# 4. Generate AppImage
echo "\n[3/4] Generating final AppImage package..."
mkdir -p "${REPO_ROOT}/dist"
OUTPUT_APPIMAGE="${REPO_ROOT}/dist/AutoUSBIP-QT-x86_64.AppImage"
rm -f "${OUTPUT_APPIMAGE}"

ARCH=x86_64 "${APPIMAGETOOL}" "${APPDIR}" "${OUTPUT_APPIMAGE}"
chmod +x "${OUTPUT_APPIMAGE}"

# 5. Generate Portable Tarball
echo "\n[4/4] Generating portable standalone tarball (.tar.gz)..."
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

if [ -f "${ICON_SVG}" ]; then
    cp -f "${ICON_SVG}" "${TARBALL_STAGING}/org.autousbip.client.svg"
fi
if [ -f "${ICON_PNG}" ]; then
    cp -f "${ICON_PNG}" "${TARBALL_STAGING}/org.autousbip.client.png"
fi

OUTPUT_TARBALL="${REPO_ROOT}/dist/AutoUSBIP-QT-x86_64.tar.gz"
rm -f "${OUTPUT_TARBALL}"
tar -czf "${OUTPUT_TARBALL}" -C "${REPO_ROOT}/build" autousbip-qt-client-linux-x86_64

echo "\n============================================================="
echo "🎉 Build complete! Generated release artifacts:"
echo "   📦 AppImage: ${OUTPUT_APPIMAGE} ($(du -h "${OUTPUT_APPIMAGE}" | cut -f1))"
echo "   📦 Tarball:  ${OUTPUT_TARBALL} ($(du -h "${OUTPUT_TARBALL}" | cut -f1))"
echo "============================================================="
