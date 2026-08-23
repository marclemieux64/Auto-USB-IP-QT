from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, pyqtSlot
from PyQt6.QtGui import QCursor, QGuiApplication, QIcon, QPixmap
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon

from config import ClientConfig, load_config, play_sound_cue, save_config
from core.usb_ids import UsbIdsDatabase
from core.usbip import attach_device, detach_all_ports, detach_port, detach_device
from services import (
    AvailableDevice,
    DeviceScanner,
    ImportedDevice,
    PowerManager,
    ServerConnection,
    ServerDiscoveryWorker,
    WebServerDaemon,
)
from ui.panel import NativePlasmaPanel
from ui.tray import TrayManager

logger = logging.getLogger("auto-usbip-client")


class AutoUsbipApp(QObject):
    def __init__(self, app: QApplication, initial_servers: list[ServerConnection]):
        super().__init__()
        self.app = app
        self.last_toggle_time = 0.0
        self.config = ClientConfig()
        self.usb_db = UsbIdsDatabase()

        # 0. Driver Pre-Flight: Ensure Linux kernel vhci-hcd module is loaded via Polkit
        from core.usbip import ensure_vhci_loaded
        if not ensure_vhci_loaded():
            logger.warning("[Driver Pre-Flight] Linux kernel module 'vhci-hcd' is not active. Devices may not attach until loaded.")
        else:
            logger.info("[Driver Pre-Flight] Linux kernel VHCI driver active and verified.")

        # 1. Load Server Connections
        from config import is_valid_server_address
        cfg = load_config()
        saved_servers = [
            ServerConnection.from_dict(d)
            for d in cfg.get("servers", [])
            if d.get("ip") and is_valid_server_address(d.get("ip"))
        ]
        self.servers: list[ServerConnection] = []
        for s in initial_servers + saved_servers:
            if is_valid_server_address(s.ip) and s not in self.servers:
                self.servers.append(s)
        self.save_servers_to_config()

        self.discovered_servers: list[dict] = []
        self.cached_devices: list[ImportedDevice] = []

        # 2. Native System Tray & WebEngine Panel
        self.tray_manager = TrayManager(self, self.app)
        self.panel = NativePlasmaPanel(self)

        # 3. Start Background Daemons
        self.web_server = WebServerDaemon(self, port=3242)
        self.web_server.start()

        self.power_manager = PowerManager(on_resume_callback=self.on_sleep_wake)
        self.power_manager.start()

        self.scanner = DeviceScanner(self.servers)
        self.scanner.signals.state_updated.connect(self.on_state_updated)
        self.scanner.start()

        self.discovery = ServerDiscoveryWorker(self)
        self.discovery.server_found.connect(self.on_server_found)
        self.discovery.start()

        self.tray_manager.update_tooltip([], self.servers)
        if getattr(self.config, "enable_wol_wake", False):
            from core.wol import sync_client_wol_to_servers
            sync_client_wol_to_servers(self)

    def get_app_icon(self) -> QIcon:
        from core.resources import get_resource_path
        svg_path = get_resource_path("assets/branding/app-icon.svg")
        png_path = get_resource_path("assets/branding/app-icon.png")
        fallback_png = get_resource_path("assets/branding/systray-logo.png")

        from PyQt6.QtGui import QImage, QPixmap, QPainter
        from PyQt6.QtCore import Qt
        icon = QIcon()

        if svg_path.exists():
            try:
                from PyQt6.QtSvg import QSvgRenderer
                renderer = QSvgRenderer(str(svg_path))
                for size in (16, 22, 24, 32, 48, 64, 128, 256, 512):
                    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
                    img.fill(Qt.GlobalColor.transparent)
                    p = QPainter(img)
                    renderer.render(p)
                    p.end()
                    icon.addPixmap(QPixmap.fromImage(img))
                return icon
            except Exception as e:
                logger.warning(f"Error rendering SVG icon: {e}")

        target_png = png_path if png_path.exists() else fallback_png
        if target_png.exists():
            src_img = QImage(str(target_png))
            for size in (16, 22, 24, 32, 48, 64, 128, 256, 512):
                scaled = src_img.scaled(
                    size,
                    size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                icon.addPixmap(QPixmap.fromImage(scaled))
            return icon
        return QIcon.fromTheme("drive-removable-media-usb", QIcon.fromTheme("dialog-information"))

    def save_servers_to_config(self):
        cfg = load_config()
        cfg["servers"] = [s.to_dict() for s in self.servers]
        save_config(cfg)

    def sync_servers_to_config(self):
        self.save_servers_to_config()

    # Desktop Window / Panel Visibility
    def on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_panel()

    def toggle_panel(self):
        now = time.time()
        if now - self.last_toggle_time < 0.25:
            return
        self.last_toggle_time = now

        if self.panel.isVisible():
            self.panel.hide()
        else:
            self.panel.show()

    def show_panel(self):
        self.panel.show()

    def open_options_dialog(self):
        self.panel.open_options_dialog()

    def quit_application(self):
        logger.info("Quitting AutoUSBIP-QT Client...")
        if hasattr(self, "panel"):
            self.panel.hide()
        if hasattr(self, "power_manager"):
            try:
                self.power_manager.stop()
            except Exception:
                pass
        if hasattr(self, "discovery"):
            try:
                self.discovery.stop()
            except Exception:
                pass
        if hasattr(self, "scanner"):
            try:
                self.scanner.stop()
            except Exception:
                pass
        if hasattr(self, "web_server"):
            try:
                self.web_server.stop()
            except Exception:
                pass
        self.app.quit()
        sys.exit(0)

    def restart(self):
        if hasattr(self, "panel"):
            self.panel.hide()
        time.sleep(0.3)
        python = sys.executable
        os.execl(python, python, *sys.argv)

    # Scanner & Discovery Signal Handlers
    @pyqtSlot(list, list, list, list, list, list)
    def on_state_updated(
        self,
        servers: list[ServerConnection],
        current_attached: list[ImportedDevice],
        new_server_ips: list[str],
        lost_server_ips: list[str],
        new_devices: list[ImportedDevice],
        lost_devices: list[ImportedDevice],
    ):
        self.cached_devices = current_attached
        self.tray_manager.update_tooltip(current_attached, servers)

        if self.config.show_notifications:
            for d in new_devices:
                b_id = getattr(d, 'bus_id', getattr(d, 'port', ''))
                d_desc = getattr(d, 'desc', getattr(d, 'description', 'USB Device'))
                clean = self.usb_db.get_device_name(b_id, d_desc)
                self.tray_manager.show_message("Device Connected", f"Attached: {clean}")
                from core.notifications import show_toast
                show_toast("Auto USB/IP: Device Connected", f"Attached: {clean}", icon_type="info")
                play_sound_cue("device-added")
            for d in lost_devices:
                b_id = getattr(d, 'bus_id', getattr(d, 'port', ''))
                d_desc = getattr(d, 'desc', getattr(d, 'description', 'USB Device'))
                clean = self.usb_db.get_device_name(b_id, d_desc)
                self.tray_manager.show_message("Device Disconnected", f"Detached: {clean}")
                from core.notifications import show_toast
                show_toast("Auto USB/IP: Device Disconnected", f"Detached: {clean}", icon_type="info")
                play_sound_cue("device-removed")

    @pyqtSlot(str, int, str, str, bool)
    def on_server_found(self, ip: str, port: int, name: str, version: str, auth_required: bool):
        existing = next((d for d in self.discovered_servers if d["ip"] == ip and d["port"] == port), None)
        if existing:
            existing["name"] = name or ip
            existing["auth_required"] = auth_required
            existing["service_name"] = name
        else:
            self.discovered_servers.append({
                "name": name or ip,
                "port": port,
                "ip": ip,
                "auth_required": auth_required,
                "service_name": name
            })

    @pyqtSlot(str)
    def on_server_lost(self, service_name: str):
        clean_name = service_name.replace("._usbip._tcp.local.", "").replace("AutoUSBIP-QT-", "").replace("AutoUSBIPServer-", "").strip().lower()
        self.discovered_servers = [
            d for d in self.discovered_servers
            if d.get("service_name") != service_name
            and d.get("name", "").strip().lower() != clean_name
            and d.get("ip", "").strip().lower() != clean_name
        ]

    # Device Operations
    def attach_single_device(self, dev: AvailableDevice):
        if hasattr(self, "scanner"):
            srv = next((s for s in self.scanner.servers if s.ip == dev.server_ip), None)
            if srv and getattr(srv, "enabled", True):
                res_devs = get_remote_usb_devices_info(srv.ip, token=getattr(srv, "token", ""))
                if res_devs is None:
                    logger.warning(f"[Security] Rejecting attach: Server {dev.server_ip} requires a valid authentication token.")
                    return
            self.scanner.ignored_devices.pop((dev.server_ip, dev.busid), None)
            if getattr(self.config, "remember_detached", True):
                key = f"{dev.server_ip}@@{dev.busid}"
                if key in self.config.ignored_devices:
                    self.config.ignored_devices.pop(key, None)
                    self.config.save()
        attach_device(dev.server_ip, dev.busid)
        if hasattr(self, "scanner"):
            self.scanner.trigger_scan()

    def detach_single_device(self, port: str):
        from core.usbip import get_port_to_bus_map, detach_port
        port_map = get_port_to_bus_map()
        p_str = str(port).strip()
        p_int = str(int(p_str)) if p_str.isdigit() else p_str
        p_pad = p_int.zfill(2) if p_int.isdigit() else p_str
        
        pair = port_map.get(p_str) or port_map.get(p_int) or port_map.get(p_pad)
        if hasattr(self, "scanner"):
            dev = next((d for d in self.scanner.imported_devices if str(getattr(d, "port", "")).lstrip("0") == p_int.lstrip("0")), None)
            if dev:
                s_ip = getattr(dev, "server_ip", "")
                b_id = getattr(dev, "bus_id", getattr(dev, "busid", ""))
                if s_ip and b_id:
                    pair = (s_ip, b_id)
        
        if pair and hasattr(self, "scanner"):
            s_ip, bus_id = pair
            if s_ip and bus_id:
                self.scanner.ignored_devices[(s_ip, bus_id)] = f"Detached ({bus_id})"
                if getattr(self.config, "remember_detached", True):
                    self.config.ignored_devices[f"{s_ip}@@{bus_id}"] = f"Detached ({bus_id})"
                    self.config.save()

        detach_port(str(port))
        if hasattr(self, "scanner"):
            self.scanner.trigger_scan()

    def detach_all_devices(self):
        from core.usbip import get_port_to_bus_map, detach_all_ports
        port_map = get_port_to_bus_map()
        if hasattr(self, "scanner"):
            for p, (s_ip, bus_id) in port_map.items():
                if s_ip and bus_id:
                    self.scanner.ignored_devices[(s_ip, bus_id)] = f"Detached ({bus_id})"
                    if getattr(self.config, "remember_detached", True):
                        self.config.ignored_devices[f"{s_ip}@@{bus_id}"] = f"Detached ({bus_id})"
            if getattr(self.config, "remember_detached", True):
                self.config.save()
        detach_all_ports()
        if hasattr(self, "scanner"):
            self.scanner.trigger_scan()

    def find_storage_mount_point(self, port: str) -> str | None:
        try:
            res = subprocess.run("lsblk -J -o NAME,MOUNTPOINT,TRAN,VENDOR,MODEL", shell=True, capture_output=True, text=True)
            if res.returncode == 0:
                import json
                data = json.loads(res.stdout)
                for dev in data.get("blockdevices", []):
                    if dev.get("tran") == "usb":
                        if dev.get("mountpoint"):
                            return dev.get("mountpoint")
                        for child in dev.get("children", []):
                            if child.get("mountpoint"):
                                return child.get("mountpoint")
        except Exception:
            pass
        return None

    def on_sleep_wake(self):
        """Clean stale connections and trigger re-binding upon system resume from sleep."""
        logger.info("System sleep resume: resetting zombies and refreshing connections...")
        def _do_resume():
            import time
            from core.usbip import detach_all_ports
            detach_all_ports()
            if hasattr(self, "scanner"):
                self.scanner.ignored_devices.clear()
                self.scanner.last_devices.clear()
                self.scanner.last_device_map.clear()
            for s in self.servers:
                if s.enabled:
                    from core.server_control import reset_zombies
                    try:
                        reset_zombies(s.ip, token=s.token)
                    except Exception as e:
                        logger.debug(f"Error resetting zombies on {s.ip}: {e}")
            time.sleep(1.5)
            if hasattr(self, "scanner"):
                self.scanner.trigger_scan()

        threading.Thread(target=_do_resume, daemon=True).start()
