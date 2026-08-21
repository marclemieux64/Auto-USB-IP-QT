from __future__ import annotations

import os
import sys
from pathlib import Path
from PyQt6.QtCore import Qt, QUrl, QSize, QTimer
from PyQt6.QtGui import QColor, QIcon, QGuiApplication
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QMessageBox, QInputDialog, QFileDialog, QLineEdit
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings

from ui.panel import CustomWebEnginePage

def get_app_icon() -> QIcon:
    svg_path = Path(__file__).resolve().parent.parent / "assets" / "branding" / "app-icon.svg"
    png_path = Path(__file__).resolve().parent.parent / "assets" / "branding" / "app-icon.png"
    if svg_path.exists():
        return QIcon(str(svg_path))
    elif png_path.exists():
        return QIcon(str(png_path))
    return QIcon.fromTheme("drive-removable-media-usb")


class StandalonePanelWindow(QWidget):
    def __init__(self, initial_js: str = ""):
        super().__init__()
        self.initial_js = initial_js
        self.setWindowTitle("Auto USB/IP")
        self.setWindowIcon(get_app_icon())

        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        self.browser = QWebEngineView(self)
        self.custom_page = CustomWebEnginePage(self, self.browser)
        self.browser.setPage(self.custom_page)

        self.browser.page().profile().downloadRequested.connect(self.on_download_requested)
        try:
            self.browser.page().profile().setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
        except Exception:
            pass

        settings = self.custom_page.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, False)

        self.browser.loadFinished.connect(self.on_load_finished)
        
        # Load local HTML file directly if present for instant rendering
        dashboard_path = Path(__file__).resolve().parent.parent / "web" / "index.html"
        if dashboard_path.exists():
            self.browser.setHtml(dashboard_path.read_text(encoding="utf-8"), QUrl("http://127.0.0.1:3242/"))
        else:
            self.browser.setUrl(QUrl("http://127.0.0.1:3242/"))

        self.browser.page().setBackgroundColor(QColor("#12141c"))
        self.root_layout.addWidget(self.browser)

        self.setMinimumSize(480, 420)
        self.resize(780, 840)

        screen = QGuiApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            x = geom.x() + (geom.width() - self.width()) // 2
            y = geom.y() + (geom.height() - self.height()) // 2
            self.move(x, y)

    def on_load_finished(self, ok: bool):
        if not ok:
            QTimer.singleShot(800, lambda: self.browser.setUrl(QUrl("http://127.0.0.1:3242/")))
        else:
            self.browser.page().runJavaScript("if (window.fetchStatus) window.fetchStatus();")
            if self.initial_js:
                QTimer.singleShot(200, lambda: self.browser.page().runJavaScript(self.initial_js))

    def on_download_requested(self, download_item):
        suggested = download_item.suggestedFileName() or "auto-usbip-backup.json"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Backup / Configuration",
            suggested,
            "JSON Files (*.json);;All Files (*)",
        )
        if path:
            p = Path(path)
            download_item.setDownloadDirectory(str(p.parent))
            download_item.setDownloadFileName(p.name)
            download_item.accept()
        else:
            download_item.cancel()


def run_ui_window(initial_js: str = ""):
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setApplicationName("AutoUSBIP-QT")
    app.setApplicationDisplayName("AutoUSBIP-QT")
    app.setDesktopFileName("org.autousbip.client")

    win = StandalonePanelWindow(initial_js)
    win.show()
    sys.exit(app.exec())
