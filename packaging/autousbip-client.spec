# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys

repo_root = Path.cwd()
client_dir = repo_root / "client"

datas = [
    (str(client_dir / "web"), "web"),
    (str(client_dir / "assets"), "assets"),
    (str(client_dir / "security"), "security"),
    (str(client_dir / "core" / "gamepad" / "gamecontrollerdb.txt"), "core/gamepad"),
]

hiddenimports = [
    "PyQt6",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtWebEngineCore",
    "PyQt6.QtNetwork",
    "PyQt6.sip",
    "zeroconf",
    "zeroconf._utils.ipaddress",
    "zeroconf._handlers.answers",
    "ifaddr",
    "serial",
    "serial.tools.list_ports",
    "api",
    "core",
    "services",
    "ui",
]

a = Analysis(
    [str(client_dir / "client.py")],
    pathex=[str(client_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy", "pandas", "unittest", "pytest", "numpy"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="autousbip-qt-client",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(client_dir / "assets" / "branding" / "app-icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="autousbip-qt-client",
)
