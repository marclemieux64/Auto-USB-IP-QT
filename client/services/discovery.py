from __future__ import annotations

import logging
import socket
import threading
from PyQt6.QtCore import QObject, QThread, pyqtSignal

try:
    from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
    HAS_ZEROCONF = True
except ImportError:
    HAS_ZEROCONF = False

logger = logging.getLogger("auto-usbip-client")


class ScannerSignals(QObject):
    state_updated = pyqtSignal(list, list, list, list, list, list)
    server_discovered = pyqtSignal(str, int, str, str)
    auth_required = pyqtSignal(object)


class ServerDiscoveryWorker(QThread):
    server_found = pyqtSignal(str, int, str, str, bool)
    server_lost = pyqtSignal(str)

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._stop_event = threading.Event()
        self.zeroconf: Zeroconf | None = None
        self.browser: ServiceBrowser | None = None

    def run(self):
        if not HAS_ZEROCONF:
            logger.error("Zeroconf module is missing! Discovery disabled.")
            return

        logger.info("ServerDiscoveryWorker starting mDNS listener...")

        class Listener(ServiceListener):
            def __init__(self, worker: ServerDiscoveryWorker):
                self.worker = worker

            def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
                self.worker.server_lost.emit(name)

            def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
                # Fast timeout (500ms max) to prevent blocking the socket thread
                info = zc.get_service_info(type_, name, timeout=500)
                if not info:
                    return

                properties = {}
                if info.properties:
                    for k, v in info.properties.items():
                        try:
                            key_str = k.decode("utf-8", "ignore") if isinstance(k, bytes) else str(k)
                            val_str = v.decode("utf-8", "ignore") if isinstance(v, bytes) else str(v)
                            properties[key_str] = val_str
                        except Exception:
                            pass

                hostname = properties.get("host", info.server.replace(".local.", "") if info.server else "Unknown")
                version = properties.get("version", "")
                auth_req = properties.get("auth_required", "false").lower() in ("true", "1", "yes")

                # Safely parse both IPv4 and IPv6 without socket errors
                for addr in info.addresses:
                    try:
                        if len(addr) == 4:
                            ip = socket.inet_ntop(socket.AF_INET, addr)
                        elif len(addr) == 16:
                            ip = socket.inet_ntop(socket.AF_INET6, addr)
                        else:
                            continue

                        logger.info(f"mDNS discovered server at {ip}:{info.port} (Host: {hostname}, Version: {version}, Auth: {auth_req})")
                        self.worker.server_found.emit(ip, info.port, hostname, version, auth_req)
                    except Exception as e:
                        logger.debug(f"Failed to parse discovered address: {e}")

            def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
                self.add_service(zc, type_, name)

        try:
            self.zeroconf = Zeroconf()
            listener = Listener(self)
            self.browser = ServiceBrowser(self.zeroconf, "_usbip._tcp.local.", listener)
            
            # Wait efficiently on the stop event instead of polling sleep
            self._stop_event.wait()
        except Exception as e:
            logger.warning(f"Zeroconf discovery loop error: {e}")
        finally:
            if self.zeroconf:
                try:
                    self.zeroconf.remove_all_service_listeners()
                    self.zeroconf.close()
                except Exception:
                    pass

    def stop(self):
        self._stop_event.set()
        self.wait(1000)