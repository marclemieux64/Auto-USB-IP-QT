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


class SubnetScannerWorker(QThread):
    scan_progress = pyqtSignal(int, int)  # current, total
    server_found = pyqtSignal(str, int, str, str, bool)
    scan_finished = pyqtSignal(int)  # count found

    def __init__(self, subnet_cidr: str = "", port: int = 3241, timeout: float = 0.35, parent=None):
        super().__init__(parent)
        self.subnet_cidr = subnet_cidr
        self.port = port
        self.timeout = timeout
        self._stop_event = threading.Event()

    def run(self):
        import ipaddress
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from core.server_control import ServerControlClient

        target_ips = []
        try:
            if not self.subnet_cidr:
                # Auto-detect local subnet from local IP
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("10.255.255.255", 1))
                local_ip = s.getsockname()[0]
                s.close()
                parts = local_ip.split(".")
                self.subnet_cidr = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"

            net = ipaddress.ip_network(self.subnet_cidr, strict=False)
            target_ips = [str(ip) for ip in net.hosts()]
        except Exception as e:
            logger.warning(f"Invalid subnet range '{self.subnet_cidr}': {e}")
            self.scan_finished.emit(0)
            return

        total = len(target_ips)
        found_count = 0
        checked_count = 0

        def _probe_ip(ip_str: str):
            if self._stop_event.is_set():
                return None
            try:
                # Fast TCP handshake check first on control port 3241
                with socket.create_connection((ip_str, self.port), timeout=self.timeout):
                    pass
                
                # Fetch server metadata via ServerControlClient
                client = ServerControlClient(ip_str, port=self.port, timeout=0.8, use_tls=True)
                stat = client.get_status()
                if stat and stat.get("status") in ("ok", "error"):
                    auth_req = stat.get("status") == "error" and "Unauthorized" in stat.get("message", "")
                    cfg = stat.get("config", {})
                    host = cfg.get("host", ip_str)
                    ver = cfg.get("version", "2.0")
                    return (ip_str, 3240, host, ver, auth_req)
            except Exception:
                pass
            return None

        logger.info(f"[Subnet Scanner] Starting probe of {total} hosts on {self.subnet_cidr}...")
        with ThreadPoolExecutor(max_workers=32) as executor:
            future_to_ip = {executor.submit(_probe_ip, ip): ip for ip in target_ips}
            for future in as_completed(future_to_ip):
                if self._stop_event.is_set():
                    break
                checked_count += 1
                self.scan_progress.emit(checked_count, total)
                res = future.result()
                if res:
                    ip, port, host, ver, auth = res
                    found_count += 1
                    logger.info(f"[Subnet Scanner] Found AutoUSBIP server at {ip}:{port} (Host: {host})")
                    self.server_found.emit(ip, port, host, ver, auth)

        logger.info(f"[Subnet Scanner] Finished scan of {self.subnet_cidr}. Found {found_count} server(s).")
        self.scan_finished.emit(found_count)

    def stop(self):
        self._stop_event.set()
        self.wait(1000)
