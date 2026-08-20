from __future__ import annotations

import logging
import os
import threading
import time
from PyQt6.QtCore import QThread

from config import POLLING_TIME, PORT_KEEPALIVE_TIMEOUT, load_config
from core.usbip import (
    attach_device,
    get_locally_attached_vid_pids,
    detach_all_ports,
    get_imported_devices,
    get_remote_usb_devices_info,
)

from services.discovery import ScannerSignals
from services.server_connection import AvailableDevice, ImportedDevice, ServerConnection

logger = logging.getLogger("auto-usbip-client")


class DeviceScanner(QThread):
    def __init__(self, servers: list[ServerConnection], parent=None):
        super().__init__(parent)
        self.servers = servers
        self._running = True
        self.signals = ScannerSignals()
        self.last_servers: set[str] = set()
        self.last_devices: set[int] = set()
        self.last_device_map: dict[int, ImportedDevice] = {}
        self.cached_available_devices: list[dict] = []

        self._trigger_event = threading.Event()
        self.ignored_devices: dict[tuple[str, str], str] = {}
        cfg = load_config()
        if cfg.get("remember_detached", True):
            for key_str, dev_name in cfg.get("ignored_devices", {}).items():
                if "@@" in key_str:
                    s_ip, bus_id = key_str.split("@@", 1)
                    self.ignored_devices[(s_ip, bus_id)] = dev_name

    def run(self):
        os.environ["KEEPALIVE_TIMEOUT"] = str(PORT_KEEPALIVE_TIMEOUT)
        logger.info("Cleaning up preexisting connections")
        detach_all_ports()

        last_loop_time = time.monotonic()

        while self._running:
            now_mono = time.monotonic()
            config = load_config()
            polling_interval = config.get("polling_interval", POLLING_TIME)

            # Detect sleep/suspend resume (time jump greater than expected interval + 3.5s)
            if (now_mono - last_loop_time) > max(15.0, polling_interval * 3 + 8.0):
                logger.warning(
                    f"[SLEEP RESUME] Detected system wake from sleep/suspend ({now_mono - last_loop_time:.1f}s gap). "
                    "Resetting stale local VHCI ports and clearing server zombie connections..."
                )
                detach_all_ports()
                self.last_devices.clear()
                from core.server_control import ServerControlClient
                for s in self.servers:
                    if getattr(s, "enabled", True):
                        try:
                            ServerControlClient(s.ip, token=getattr(s, "token", "")).reset_zombies()
                        except Exception:
                            pass
                time.sleep(0.5)

            last_loop_time = time.monotonic()
            auto_attach = config.get("auto_attach", True)
            raw_bl = config.get("blacklisted_devices", [])
            blacklisted = set()
            for item in raw_bl:
                if isinstance(item, dict):
                    for k in ("identifier", "vid_pid", "bus_id", "name"):
                        val = item.get(k)
                        if val:
                            blacklisted.add(str(val).strip())
                            blacklisted.add(str(val).strip().lower())
                elif isinstance(item, str):
                    blacklisted.add(item.strip())
                    blacklisted.add(item.strip().lower())

            if not self.servers or not any(s.enabled and s.is_alive for s in self.servers):
                detach_all_ports()
                self.ignored_devices.clear()
                self.signals.state_updated.emit(
                    self.servers,
                    [],
                    [],
                    [],
                    [],
                    [],
                )
                self.last_servers.clear()
                self.last_devices.clear()
                for _ in range(int(polling_interval * 10)):
                    if not self._running:
                        break
                    time.sleep(0.1)
                continue

            online_servers = []
            available_devices: list[tuple[str, str, str]] = []
            remote_available_list: list[dict] = []

            for s in self.servers:
                if s.enabled and s.is_alive:
                    online_servers.append(s)
                    res_devs = get_remote_usb_devices_info(s.ip, token=getattr(s, "token", ""))
                    if res_devs is None:
                        if (s.ip, "auth_prompted") not in self.ignored_devices:
                            self.ignored_devices[(s.ip, "auth_prompted")] = "true"
                            self.signals.auth_required.emit(s)
                        continue
                    else:
                        self.ignored_devices.pop((s.ip, "auth_prompted"), None)

                    for dev_id, dev_desc in res_devs:
                        vid_pid_match = ImportedDevice.VID_PID_REGEX.search(dev_desc) or ImportedDevice.VID_PID_REGEX.search(dev_id)
                        v_key = f"{vid_pid_match.group(1)}:{vid_pid_match.group(2)}".lower() if vid_pid_match else dev_id
                        if dev_id in blacklisted or v_key in blacklisted or (v_key and v_key.upper() in blacklisted) or dev_desc in blacklisted:
                            continue


                        remote_available_list.append({
                            "server_ip": s.ip,
                            "bus_id": dev_id,
                            "desc": dev_desc,
                            "vid_pid": f"({v_key})" if vid_pid_match else "",
                            "identifier_key": v_key if vid_pid_match else dev_id
                        })

                        # Optional BadUSB Device Class Security Filter
                        is_blocked_by_class = False
                        if config.get("enable_device_class_filter", False):
                            desc_lower = dev_desc.lower()
                            if config.get("block_mass_storage", False) and any(k in desc_lower for k in ("mass storage", "flash drive", "usb drive", "disk", "storage", "(08/")):
                                is_blocked_by_class = True
                            elif config.get("block_network_devices", False) and any(k in desc_lower for k in ("ethernet", "network", "wi-fi", "wifi", "802.11", "rndis", "wireless", "(02/", "(e0/")):
                                is_blocked_by_class = True
                            elif config.get("block_hid_keyboards", False) and any(k in desc_lower for k in ("keyboard", "keypad", "rubber ducky")):
                                is_blocked_by_class = True

                            if is_blocked_by_class:
                                logger.warning(f"[BadUSB Defense] Auto-attach blocked for '{dev_desc}' ({dev_id}) on {s.ip} by device class security filter.")

                        # If device was detached/ignored by user or blocked by security filter, do NOT auto-attach!
                        if (s.ip, dev_id) in self.ignored_devices:
                            curr_val = self.ignored_devices[(s.ip, dev_id)]
                            if len(dev_desc) > len(curr_val) or "unknown" in curr_val.lower() or curr_val == f"Remote Device ({dev_id})":
                                self.ignored_devices[(s.ip, dev_id)] = dev_desc
                        elif auto_attach and not is_blocked_by_class:
                            available_devices.append((s.ip, dev_id, dev_desc))
                        else:
                            self.ignored_devices[(s.ip, dev_id)] = dev_desc



            from core.usbip import get_port_to_bus_map
            current_port_map = get_port_to_bus_map()
            attached_pairs = set(current_port_map.values())

            # Attach unattached devices concurrently in parallel threads
            to_attach = []
            for s_ip, dev_id, dev_desc in available_devices:
                if (s_ip, dev_id) in attached_pairs:
                    continue
                to_attach.append((s_ip, dev_id))

            if to_attach:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(to_attach))) as executor:
                    list(executor.map(lambda args: attach_device(args[0], args[1]), to_attach))

            self.cached_available_devices = remote_available_list
            current_attached = get_imported_devices()

            # Enforce immediate detach on any currently attached device matching the blacklist
            if blacklisted and current_attached:
                from core.usbip import detach_device
                needs_refetch = False
                for dev in current_attached:
                    b_id = getattr(dev, "bus_id", getattr(dev, "busid", ""))
                    v_match = ImportedDevice.VID_PID_REGEX.search(dev.description) or (ImportedDevice.VID_PID_REGEX.search(b_id) if b_id else None)
                    v_k = f"{v_match.group(1)}:{v_match.group(2)}".lower() if v_match else ""
                    if (
                        (b_id and b_id in blacklisted)
                        or (v_k and (v_k in blacklisted or v_k.lower() in blacklisted))
                        or dev.description in blacklisted
                        or dev.description.lower() in blacklisted
                        or str(dev.port) in blacklisted
                    ):
                        detach_device(str(dev.port))
                        needs_refetch = True
                if needs_refetch:
                    current_attached = get_imported_devices()
            from core.usbip import get_port_to_bus_map
            port_map = get_port_to_bus_map()
            current_server_ips = {s.ip for s in online_servers}
            current_device_keys = {hash(d) for d in current_attached}
            current_device_map = {hash(d): d for d in current_attached}

            new_server_ips = current_server_ips - self.last_servers
            lost_server_ips = self.last_servers - current_server_ips

            new_dev_keys = current_device_keys - self.last_devices
            lost_dev_keys = self.last_devices - current_device_keys

            new_devices = [
                current_device_map[k] for k in new_dev_keys if k in current_device_map
            ]
            lost_devices = [
                self.last_device_map[k] for k in lost_dev_keys if k in self.last_device_map
            ]

            self.signals.state_updated.emit(
                self.servers,
                current_attached,
                list(new_server_ips),
                list(lost_server_ips),
                new_devices,
                lost_devices,
            )

            self.last_servers = current_server_ips
            self.last_devices = current_device_keys
            self.last_device_map = current_device_map

            self._trigger_event.wait(timeout=float(polling_interval))
            self._trigger_event.clear()

        detach_all_ports()

    def stop(self):
        self._running = False

    @property
    def imported_devices(self) -> list[ImportedDevice]:
        return list(self.last_device_map.values()) if self.last_device_map else get_imported_devices()

    @property
    def available_devices(self) -> list[AvailableDevice]:
        res = []
        for d in self.cached_available_devices:
            if isinstance(d, dict):
                res.append(AvailableDevice(
                    server_ip=d.get("server_ip", ""),
                    busid=d.get("bus_id", d.get("busid", "")),
                    description=d.get("desc", d.get("description", "USB Device"))
                ))
            elif isinstance(d, AvailableDevice):
                res.append(d)
        return res

    def set_servers(self, servers: list[ServerConnection]):
        self.servers = servers

    def trigger_scan(self):
        self._trigger_event.set()
