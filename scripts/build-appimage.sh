#!/usr/bin/env bash
# ==============================================================================
# AutoUSBIP-QT Client - AppImage Release Builder
# Output: dist/AutoUSBIP-QT-Client-Linux-x86_64.AppImage
# ==============================================================================

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

echo "🔨 ============================================================="
echo "   AutoUSBIP-QT Client — AppImage Release Builder                "
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
echo -e "\n[1/3] Freezing Python application and Qt6 runtime..."
"${PYINSTALLER_BIN}" --clean --noconfirm "${REPO_ROOT}/packaging/autousbip-client.spec"

# 3. Construct AppDir layout
echo -e "\n[2/3] Constructing AppDir structure..."
APPDIR="${REPO_ROOT}/build/AutoUSBIP-QT.AppDir"
rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin" "${APPDIR}/usr/share/metainfo"

# Copy AppRun, Desktop entries, and AppStream metadata
mkdir -p "${APPDIR}/usr/share/applications" "${APPDIR}/usr/share/metainfo"
cp -f "${REPO_ROOT}/packaging/AppRun" "${APPDIR}/AppRun"
chmod +x "${APPDIR}/AppRun"

cp -f "${REPO_ROOT}/packaging/org.autousbip.client.desktop" "${APPDIR}/org.autousbip.client.desktop"
cp -f "${REPO_ROOT}/packaging/org.autousbip.client.desktop" "${APPDIR}/usr/share/applications/org.autousbip.client.desktop"

if [ -f "${REPO_ROOT}/packaging/org.autousbip.client.metainfo.xml" ]; then
    cp -f "${REPO_ROOT}/packaging/org.autousbip.client.metainfo.xml" "${APPDIR}/usr/share/metainfo/org.autousbip.client.metainfo.xml"
fi

# Copy icons (AppImage spec mandates .DirIcon MUST be PNG)
ICON_SVG="${REPO_ROOT}/client/assets/branding/app-icon.svg"
ICON_PNG="${REPO_ROOT}/client/assets/branding/app-icon.png"

mkdir -p "${APPDIR}/usr/share/icons/hicolor/scalable/apps"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/512x512/apps"
mkdir -p "${APPDIR}/usr/share/pixmaps"

if [ -f "${ICON_PNG}" ]; then
    cp -f "${ICON_PNG}" "${APPDIR}/org.autousbip.client.png"
    cp -f "${ICON_PNG}" "${APPDIR}/usr/share/icons/hicolor/512x512/apps/org.autousbip.client.png"
    cp -f "${ICON_PNG}" "${APPDIR}/usr/share/pixmaps/org.autousbip.client.png"
    cp -f "${ICON_PNG}" "${APPDIR}/.DirIcon"
fi

if [ -f "${ICON_SVG}" ]; then
    cp -f "${ICON_SVG}" "${APPDIR}/org.autousbip.client.svg"
    cp -f "${ICON_SVG}" "${APPDIR}/usr/share/icons/hicolor/scalable/apps/org.autousbip.client.svg"
    cp -f "${ICON_SVG}" "${APPDIR}/usr/share/pixmaps/org.autousbip.client.svg"
    if [ ! -f "${ICON_PNG}" ]; then
        cp -f "${ICON_SVG}" "${APPDIR}/.DirIcon"
    fi
fi

# Copy frozen binaries and assets
cp -r "${REPO_ROOT}/dist/autousbip-qt-client/"* "${APPDIR}/usr/bin/"

# 4. Generate AppImage
echo -e "\n[3/3] Generating final AppImage package..."
mkdir -p "${REPO_ROOT}/dist"
OUTPUT_APPIMAGE="${REPO_ROOT}/dist/AutoUSBIP-QT-Client-Linux-x86_64.AppImage"
rm -f "${OUTPUT_APPIMAGE}"

ARCH=x86_64 "${APPIMAGETOOL}" --no-appstream "${APPDIR}" "${OUTPUT_APPIMAGE}"
chmod +x "${OUTPUT_APPIMAGE}"

echo -e "\n============================================================="
echo "🎉 AppImage build complete!"
echo "   📦 AppImage: ${OUTPUT_APPIMAGE} ($(du -h "${OUTPUT_APPIMAGE}" 2>/dev/null | cut -f1 || echo ''))"
echo "============================================================="
