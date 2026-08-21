from __future__ import annotations

import logging
import os
import subprocess
import sys
import urllib.parse
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


class NativePlasmaPanel:
    """
    Process-isolated Dashboard Window Controller.
    Running the Chromium UI in a dedicated process guarantees that clicking the title bar 'X'
    closes the window cleanly without terminating the core USB/IP background daemon, tray icon,
    or device connections.
    """
    def __init__(self, controller):
        self.controller = controller
        self._proc: subprocess.Popen | None = None

    def isVisible(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def hide(self):
        if self._proc is not None and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass
        self._proc = None

    def show(self, initial_js: str = ""):
        if self.isVisible():
            return

        executable = sys.executable
        if getattr(sys, "frozen", False):
            # In PyInstaller / AppImage standalone executable
            args = [executable, "--ui-window"]
        else:
            args = [executable, str(Path(__file__).resolve().parent.parent / "main.py"), "--ui-window"]

        if initial_js:
            args.append(initial_js)

        try:
            self._proc = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
        except Exception as e:
            logger.error(f"Error launching UI window process: {e}")

    def refresh(self):
        pass

    def open_options_dialog(self):
        self.show("if (window.openClientOptionsModal) openClientOptionsModal();")

    def open_gamepad_tester(self, port: str):
        target_dev = next((d for d in self.controller.cached_devices if str(d.port) == str(port)), None)
        title = target_dev.clean_name if target_dev else f"Port {port}"
        enc = urllib.parse.quote(title)
        self.show(f"if (window.openGamepadTesterModal) openGamepadTesterModal('{port}', '{enc}');")
