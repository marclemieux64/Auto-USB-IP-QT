from __future__ import annotations

import logging
import threading
import time
from typing import Callable
from PyQt6.QtCore import QObject, pyqtSlot
try:
    from PyQt6.QtDBus import QDBusConnection
except ImportError:
    QDBusConnection = None

logger = logging.getLogger("auto-usbip-client")


class PowerManager(QObject):
    """Manages system sleep/resume lifecycle via PyQt6 QtDBus & monotonic watchdog."""

    def __init__(self, on_resume_callback: Callable[[], None] | None = None):
        super().__init__()
        self.on_resume_callback = on_resume_callback
        self._watchdog_thread: threading.Thread | None = None
        self._running = False
        self._last_resume_time = 0.0
        self._lock = threading.Lock()

    def start(self):
        """Start listening for D-Bus PrepareForSleep signals and monotonic watchdog."""
        self._running = True
        self._setup_dbus()
        self._watchdog_thread = threading.Thread(target=self._run_watchdog, daemon=True)
        self._watchdog_thread.start()

    def _setup_dbus(self):
        if QDBusConnection is None:
            logger.debug("PowerManager: QtDBus not available on this platform. Using monotonic watchdog exclusively.")
            return
        try:
            bus = QDBusConnection.systemBus()
            if bus.isConnected():
                connected = bus.connect(
                    "org.freedesktop.login1",
                    "/org/freedesktop/login1",
                    "org.freedesktop.login1.Manager",
                    "PrepareForSleep",
                    self._on_prepare_for_sleep,
                )
                if connected:
                    logger.info("PowerManager: Subscribed to systemd login1 PrepareForSleep signals via QtDBus.")
                else:
                    logger.debug("PowerManager: Could not connect PrepareForSleep signal.")
        except Exception as e:
            logger.debug(f"PowerManager QtDBus error: {e}")

    def _trigger_resume(self, source: str):
        now = time.monotonic()
        with self._lock:
            if now - self._last_resume_time < 5.0:
                logger.debug(f"PowerManager: Resume event from '{source}' ignored (debounced).")
                return
            self._last_resume_time = now

        logger.info(f"PowerManager: System resumed ({source}). Triggering recovery callback...")
        if self.on_resume_callback:
            try:
                self.on_resume_callback()
            except Exception as e:
                logger.error(f"Error in on_resume_callback: {e}")

    @pyqtSlot(bool)
    def _on_prepare_for_sleep(self, sleeping: bool):
        if not sleeping:
            self._trigger_resume("QtDBus")

    def _run_watchdog(self):
        last_time = time.monotonic()
        while self._running:
            time.sleep(1.0)
            now = time.monotonic()
            if (now - last_time) > 4.5:
                self._trigger_resume("Watchdog gap")
            last_time = now

    def stop(self):
        self._running = False