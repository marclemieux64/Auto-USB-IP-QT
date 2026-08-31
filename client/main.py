from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Configure High-DPI, Wayland, and software GPU rasterizer for WebEngine
if sys.platform.startswith("linux"):
    os.environ["QT_QPA_PLATFORM"] = "wayland;xcb"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--no-sandbox --disable-gpu --disable-dev-shm-usage"
os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"

from PyQt6.QtCore import Qt, QCoreApplication
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication

logger = logging.getLogger("auto-usbip-client")

def global_exception_handler(exc_type, exc_value, exc_traceback):
    import traceback
    err_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logger.error(f"[PREVENTED CRASH] Unhandled exception in Qt thread/slot:\n{err_str}")

def handle_cli_integration():
    from pathlib import Path
    import subprocess
    home = Path.home()
    desktop_file = home / ".local" / "share" / "applications" / "org.autousbip.client.desktop"
    icon_svg = home / ".local" / "share" / "icons" / "hicolor" / "scalable" / "apps" / "org.autousbip.client.svg"
    icon_png = home / ".local" / "share" / "icons" / "hicolor" / "256x256" / "apps" / "org.autousbip.client.png"

    if "--install" in sys.argv:
        print("📦 Integrating Auto USB/IP-QT Client into desktop application menu...")
        exec_path = os.environ.get("APPIMAGE", str(Path(sys.executable).resolve()))
        desktop_file.parent.mkdir(parents=True, exist_ok=True)
        icon_svg.parent.mkdir(parents=True, exist_ok=True)
        icon_png.parent.mkdir(parents=True, exist_ok=True)

        assets_dir = Path(__file__).resolve().parent / "assets" / "branding"
        if (assets_dir / "app-icon.svg").exists():
            import shutil
            shutil.copyfile(assets_dir / "app-icon.svg", icon_svg)
        if (assets_dir / "app-icon.png").exists():
            import shutil
            shutil.copyfile(assets_dir / "app-icon.png", icon_png)

        content = f"""[Desktop Entry]
Name=Auto USB/IP-QT
Comment=Automatic USB-over-IP device manager and gamepad tester
Exec="{exec_path}"
Icon=org.autousbip.client
Terminal=false
Type=Application
Categories=Utility;Network;
Keywords=usb;usbip;remote;gamepad;controller;
StartupNotify=true
StartupWMClass=auto-usbip-client
X-AppImage-Version=2.4.0
"""
        desktop_file.write_text(content, encoding="utf-8")
        subprocess.run(["update-desktop-database", str(desktop_file.parent)], capture_output=True)
        print(f"✅ Desktop menu shortcut successfully installed: {desktop_file}")
        sys.exit(0)

    elif "--uninstall" in sys.argv:
        print("🗑️ Removing Auto USB/IP-QT Client desktop shortcuts and icons...")
        for p in (desktop_file, icon_svg, icon_png):
            if p.exists():
                p.unlink()
        subprocess.run(["update-desktop-database", str(desktop_file.parent)], capture_output=True)
        print("✅ Auto USB/IP-QT Client shortcuts and icons removed successfully.")
        sys.exit(0)


def main():
    handle_cli_integration()
    if "--ui-window" in sys.argv:
        from ui.window_launcher import run_ui_window
        sys.argv.remove("--ui-window")
        initial_js = sys.argv[1] if len(sys.argv) > 1 else ""
        run_ui_window(initial_js)
        return

    sys.excepthook = global_exception_handler
    logging.basicConfig(level=logging.INFO)
    from core.console import init_client_console
    init_client_console()
    from core.notifications import init_notification_subsystem
    init_notification_subsystem()
    from core.latency_optimizer import init_latency_optimizer
    init_latency_optimizer()

    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)

    from config import is_valid_server_address, PORT
    from services.server_connection import ServerConnection
    from app import AutoUsbipApp

    initial_servers = [
        ServerConnection(ip.strip(), PORT)
        for ip in sys.argv[1:]
        if is_valid_server_address(ip)
    ]

    if hasattr(Qt.HighDpiScaleFactorRoundingPolicy, "PassThrough"):
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

    app = QApplication(sys.argv)
    app.setApplicationName("Auto USB/IP-QT")
    app.setApplicationDisplayName("Auto USB/IP-QT")
    app.setDesktopFileName("org.autousbip.client")
    app.setQuitOnLastWindowClosed(False)

    tray_instance = AutoUsbipApp(app, initial_servers)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
