from __future__ import annotations

import logging
import os
import sys

# Configure High-DPI, Wayland, and software GPU rasterizer for WebEngine
os.environ["QT_QPA_PLATFORM"] = "wayland;xcb"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--no-sandbox --disable-gpu --disable-dev-shm-usage"
os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"

from PyQt6.QtCore import Qt, QCoreApplication
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication

def global_exception_handler(exc_type, exc_value, exc_traceback):
    import traceback
    err_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logger.error(f"[PREVENTED CRASH] Unhandled exception in Qt thread/slot:\n{err_str}")

def main():
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
