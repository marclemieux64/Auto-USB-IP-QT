from __future__ import annotations

import logging
from PyQt6.QtCore import QObject
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

logger = logging.getLogger("auto-usbip-client")


class TrayManager(QObject):
    def __init__(self, controller: any, app: QApplication):
        super().__init__()
        self.controller = controller
        self.app = app
        self.icon = self.controller.get_app_icon()

        self.tray = QSystemTrayIcon(self.icon, self.app)
        self.tray_menu = QMenu()

        act_detach_all = self.tray_menu.addAction(
            QIcon.fromTheme("list-remove-all-symbolic", QIcon.fromTheme("edit-delete")), "Detach All Devices"
        )
        act_detach_all.triggered.connect(self.controller.detach_all_devices)

        act_restart = self.tray_menu.addAction(
            QIcon.fromTheme("view-refresh"), "Restart Client"
        )
        act_restart.triggered.connect(self.controller.restart)

        act_options = self.tray_menu.addAction(
            QIcon.fromTheme("configure"), "Options..."
        )
        act_options.triggered.connect(self.controller.open_options_dialog)

        self.tray_menu.addSeparator()

        act_quit = self.tray_menu.addAction(
            QIcon.fromTheme("application-exit"), "Quit"
        )
        act_quit.triggered.connect(self.app.quit)

        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(self.controller.on_tray_activated)
        self.tray.show()

    def update_tooltip(self, devices: list, servers: list):
        count = len(devices)
        if count == 0:
            status = "No devices attached"
        elif count == 1:
            status = "1 device attached"
        else:
            status = f"{count} devices attached"

        srv_count = len([s for s in servers if s.enabled])
        self.tray.setToolTip(f"Auto USB/IP\n{status}\n{srv_count} server(s) active")

    def show_message(self, title: str, message: str, icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information):
        self.tray.showMessage(title, message, icon, 3000)
