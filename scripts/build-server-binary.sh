#!/usr/bin/env bash
# ==============================================================================
# Build Standalone Single-Binary Executable for AutoUSBIP-QT Server
# Output: dist/autousbip-qt-server
# ==============================================================================

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "Building standalone autousbip-qt-server single binary..."

# Use PyInstaller to bundle autousbip.py into a single onefile executable
PYINSTALLER_BIN="$REPO_ROOT/client/venv/bin/pyinstaller"
if [ ! -x "$PYINSTALLER_BIN" ]; then
    PYINSTALLER_BIN="$(which pyinstaller 2>/dev/null || true)"
fi
"$PYINSTALLER_BIN" \
    --onefile \
    --name "AutoUSBIP-QT-Server-Linux-x86_64" \
    --clean \
    --noconfirm \
    --distpath "$REPO_ROOT/dist" \
    --workpath "$REPO_ROOT/build/server" \
    --specpath "$REPO_ROOT/build/server" \
    "$REPO_ROOT/server/autousbip.py"

chmod +x "$REPO_ROOT/dist/AutoUSBIP-QT-Server-Linux-x86_64"
echo "============================================================="
echo "🎉 Server build complete! Single standalone binary:"
echo "   📦 $REPO_ROOT/dist/AutoUSBIP-QT-Server-Linux-x86_64 ($(du -h "$REPO_ROOT/dist/AutoUSBIP-QT-Server-Linux-x86_64" | cut -f1))"
echo "============================================================="
