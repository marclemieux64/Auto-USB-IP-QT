from __future__ import annotations

import os
import sys
from pathlib import Path


def get_resource_path(rel_path: str = "") -> Path:
    """
    Resolve resource path dynamically across:
    1. PyInstaller onefile temp bundle (sys._MEIPASS)
    2. PyInstaller onedir / Nuitka standalone executables (sys.executable parent)
    3. Linux AppImage environments (APPDIR environment variable)
    4. Linux standard package installations (/usr/share/auto-usbip)
    5. Normal Python development environment
    """
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            # PyInstaller --onefile extracted temp directory
            base = Path(sys._MEIPASS)
        else:
            # PyInstaller --onedir or Nuitka standalone build
            base = Path(sys.executable).resolve().parent
    elif "APPDIR" in os.environ:
        # AppImage runtime layout
        app_dir = Path(os.environ["APPDIR"])
        base = app_dir / "usr" / "share" / "auto-usbip"
        if not base.exists():
            base = app_dir
    else:
        # Development environment or system install
        dev_base = Path(__file__).resolve().parent.parent
        sys_share = Path("/usr/share/auto-usbip")
        
        # If installed system-wide without dev files present, use /usr/share
        if not (dev_base / "assets").exists() and sys_share.exists():
            base = sys_share
        else:
            base = dev_base

    return (base / rel_path) if rel_path else base


def get_app_dir() -> Path:
    """Return canonical directory containing the executable or repository root."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent