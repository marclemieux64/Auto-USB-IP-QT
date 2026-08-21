from __future__ import annotations

import logging
from pathlib import Path
from PyQt6.QtCore import Qt, QUrl, QSize
from PyQt6.QtGui import QColor, QIcon
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QMessageBox, QInputDialog, QFileDialog, QLineEdit
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings

logger = logging.getLogger("auto-usbip-client")

DARK_DIALOG_STYLE = """
QDialog, QMessageBox, QInputDialog {
    background-color: #1b1e2b;
    color: #f3f4f6;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 13px;
}
QLabel {
    color: #f3f4f6;
}
QPushButton {
    background-color: #2d3348;
    color: #ffffff;
    border: 1px solid rgba(59, 130, 246, 0.4);
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 600;
    min-width: 75px;
}
QPushButton:hover {
    background-color: #3b82f6;
    border-color: #3b82f6;
}
QPushButton:pressed {
    background-color: #2563eb;
}
QLineEdit {
    background-color: #232738;
    color: #ffffff;
    border: 1px solid #2e344a;
    border-radius: 6px;
    padding: 6px 8px;
}
QLineEdit:focus {
    border: 1px solid #3b82f6;
}
"""


class CustomWebEnginePage(QWebEnginePage):
    def __init__(self, panel, parent=None):
        super().__init__(parent)
        self.panel = panel

    def javaScriptAlert(self, securityOrigin: QUrl, msg: str):
        box = QMessageBox(self.panel)
        box.setStyleSheet(DARK_DIALOG_STYLE)
        box.setWindowTitle("Auto USB/IP")
        box.setText(msg)
        box.setIcon(QMessageBox.Icon.Information)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()

    def javaScriptConfirm(self, securityOrigin: QUrl, msg: str) -> bool:
        box = QMessageBox(self.panel)
        box.setStyleSheet(DARK_DIALOG_STYLE)
        box.setWindowTitle("Auto USB/IP")
        box.setText(msg)
        box.setIcon(QMessageBox.Icon.Question)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        res = box.exec()
        return res == QMessageBox.StandardButton.Yes

    def javaScriptPrompt(self, securityOrigin: QUrl, msg: str, defaultValue: str) -> tuple[bool, str]:
        dlg = QInputDialog(self.panel)
        dlg.setStyleSheet(DARK_DIALOG_STYLE)
        dlg.setWindowTitle("Auto USB/IP")
        dlg.setLabelText(msg)
        dlg.setTextValue(defaultValue)
        ok = dlg.exec() == QInputDialog.DialogCode.Accepted
        text = dlg.textValue() if ok else ""
        return (ok, text)

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        logger.info(f"[DesktopWebEngine JS] line {lineNumber}: {message}")


class NativePlasmaPanel(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._active_tester = None

        # Prevent closing panel from destroying the widget or quitting the app
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        # Standard native window with full window decoration and title bar
        self.setWindowTitle("Auto USB/IP")
        self.setWindowIcon(self.controller.get_app_icon())

        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        self.browser = QWebEngineView(self)
        self.custom_page = CustomWebEnginePage(self, self.browser)
        self.browser.setPage(self.custom_page)

        # Hook download requests so backups/configs save cleanly to user desired path
        self.browser.page().profile().downloadRequested.connect(self.on_download_requested)
        try:
            from PyQt6.QtWebEngineCore import QWebEngineProfile
            self.browser.page().profile().setHttpCacheType(QWebEngineProfile.HttpCacheType.NoCache)
            self.browser.page().profile().clearHttpCache()
        except Exception:
            pass

        settings = self.custom_page.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, False)

        self.browser.loadFinished.connect(self.on_load_finished)
        self.browser.setUrl(QUrl("http://127.0.0.1:3242/"))
        self.browser.page().setBackgroundColor(QColor("#12141c"))
        self.root_layout.addWidget(self.browser)

        self.setMinimumSize(480, 420)
        self.resize(780, 840)

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

    def open_gamepad_tester(self, port: str):
        import urllib.parse
        target_dev = next((d for d in self.controller.cached_devices if str(d.port) == str(port)), None)
        title = target_dev.clean_name if target_dev else f"Port {port}"
        enc = urllib.parse.quote(title)
        if not self.isVisible():
            self.controller.show_panel()
        self.browser.page().runJavaScript(f"if (window.openGamepadTesterModal) openGamepadTesterModal('{port}', '{enc}');")

    def closeEvent(self, event):
        # Hide to tray without triggering Chromium render widget buffer unmap crash
        event.ignore()
        self.hide_to_tray()

    def hide_to_tray(self):
        self.lower()
        self.move(-99999, -99999)
        self._is_docked_tray = True

    def is_panel_open(self) -> bool:
        return self.isVisible() and not getattr(self, "_is_docked_tray", False) and self.pos().x() > -5000

    def sizeHint(self):
        return QSize(780, 840)

    def minimumSizeHint(self):
        return QSize(600, 580)

    def on_load_finished(self, ok: bool):
        if not ok:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(800, lambda: self.browser.setUrl(QUrl("http://127.0.0.1:3242")))
        else:
            self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, "browser") and self.browser:
            dashboard_path = Path(__file__).resolve().parent.parent / "web" / "index.html"
            if dashboard_path.exists():
                self.browser.setHtml(dashboard_path.read_text(encoding="utf-8"), QUrl("http://127.0.0.1:3242/"))
            else:
                self.browser.setUrl(QUrl("http://127.0.0.1:3242/"))
            self.refresh()

    def refresh(self, *args, **kwargs):
        if hasattr(self, "browser") and self.browser:
            self.browser.page().runJavaScript("if (window.fetchStatus) window.fetchStatus();")

    def open_options(self):
        if hasattr(self, "browser") and self.browser:
            self.browser.page().runJavaScript("if (window.openClientOptionsModal) openClientOptionsModal();")

    def open_options_dialog(self):
        self.open_options()
