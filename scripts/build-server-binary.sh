#!/usr/bin/env bash
# ==============================================================================
# Build Standalone Single-Binary Executable for AutoUSBIP-QT Server
# Output: dist/autousbip-server
# ==============================================================================

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "Building standalone autousbip-server single binary..."

# Use PyInstaller to bundle autousbip.py into a single onefile executable
"$REPO_ROOT/client/venv/bin/pyinstaller" \
    --onefile \
    --name "autousbip-server" \
    --clean \
    --noconfirm \
    --distpath "$REPO_ROOT/dist" \
    --workpath "$REPO_ROOT/build/server" \
    --specpath "$REPO_ROOT/build/server" \
    "$REPO_ROOT/server/autousbip.py"

chmod +x "$REPO_ROOT/dist/autousbip-server"
echo "============================================================="
echo "🎉 Server build complete! Single standalone binary:"
echo "   📦 $REPO_ROOT/dist/autousbip-server ($(du -h "$REPO_ROOT/dist/autousbip-server" | cut -f1))"
echo "============================================================="
