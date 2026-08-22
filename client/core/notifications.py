from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

logger = logging.getLogger("auto-usbip-client")

_is_windows = sys.platform == "win32"
_is_linux = sys.platform.startswith("linux")


def init_notification_subsystem():
    """Register Windows App User Model ID so toasts display cleanly in Action Center."""
    if _is_windows:
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("org.autousbip.client")
            logger.debug("[Notifications] Registered Windows AppUserModelID: org.autousbip.client")
        except Exception as e:
            logger.debug(f"[Notifications] Error setting Windows AUMID: {e}")


def show_toast(title: str, message: str, icon_type: str = "info"):
    """
    Cross-platform desktop toast notification dispatcher.
    Runs asynchronously in a background thread to prevent UI pauses.
    """
    def _dispatch():
        try:
            # 1. Windows Native Notification Handling
            if _is_windows:
                _show_windows_toast(title, message, icon_type)
                return

            # 2. Linux Desktop Notification Handling
            if _is_linux:
                _show_linux_notification(title, message, icon_type)
                return

        except Exception as e:
            logger.debug(f"[Notifications] Notification dispatch exception: {e}")

    threading.Thread(target=_dispatch, daemon=True).start()


def _show_windows_toast(title: str, message: str, icon_type: str):
    """Dispatch Windows 10/11 Action Center toast notification via PowerShell / WinRT if available."""
    try:
        clean_title = title.replace("'", "''").replace('"', '`"')
        clean_msg = message.replace("'", "''").replace('"', '`"')
        
        ps_cmd = (
            '[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null; '
            '[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null; '
            f'$xml = New-Object Windows.Data.Xml.Dom.XmlDocument; '
            f'$xml.LoadXml(\'<toast duration="short"><visual><binding template="ToastGeneric"><text>{clean_title}</text><text>{clean_msg}</text></binding></visual></toast>\'); '
            '$toast = [Windows.UI.Notifications.ToastNotification]::new($xml); '
            '[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("org.autousbip.client").Show($toast)'
        )

        creation_flags = 0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
            timeout=4
        )
    except Exception as e:
        logger.debug(f"[Notifications] PowerShell toast error: {e}")


def _show_linux_notification(title: str, message: str, icon_type: str):
    """Dispatch Linux FreeDesktop notification via notify-send."""
    urgency = "critical" if icon_type == "error" else ("normal" if icon_type == "warn" else "low")
    try:
        subprocess.run(
            [
                "notify-send",
                "-a", "Auto USB/IP-QT",
                "-i", "org.autousbip.client",
                "-u", urgency,
                "-t", "4000",
                title,
                message
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2
        )
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.debug(f"[Notifications] notify-send error: {e}")
