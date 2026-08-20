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

from app import AutoUsbipApp
from config import PORT
from services.server_connection import ServerConnection

logger = logging.getLogger("auto-usbip-client")


def global_exception_handler(exc_type, exc_value, exc_traceback):
    import traceback
    err_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logger.error(f"[PREVENTED CRASH] Unhandled exception in Qt thread/slot:\n{err_str}")

def main():
    sys.excepthook = global_exception_handler
    logging.basicConfig(level=logging.INFO)
    from core.console import init_client_console
    init_client_console()

    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)

    initial_servers = [ServerConnection(ip, PORT) for ip in sys.argv[1:]]

    if hasattr(Qt.HighDpiScaleFactorRoundingPolicy, "PassThrough"):
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

    app = QApplication(sys.argv)
    app.setApplicationName("Auto USB/IP")
    app.setApplicationDisplayName("Auto USB/IP")
    app.setDesktopFileName("org.autousbip.client")
    app.setQuitOnLastWindowClosed(False)

    tray_instance = AutoUsbipApp(app, initial_servers)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
