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
"$REPO_ROOT/client/venv/bin/pyinstaller" \
    --onefile \
    --name "autousbip-qt-server" \
    --clean \
    --noconfirm \
    --distpath "$REPO_ROOT/dist" \
    --workpath "$REPO_ROOT/build/server" \
    --specpath "$REPO_ROOT/build/server" \
    "$REPO_ROOT/server/autousbip.py"

chmod +x "$REPO_ROOT/dist/autousbip-qt-server"
echo "============================================================="
echo "🎉 Server build complete! Single standalone binary:"
echo "   📦 $REPO_ROOT/dist/autousbip-qt-server ($(du -h "$REPO_ROOT/dist/autousbip-qt-server" | cut -f1))"
echo "============================================================="
