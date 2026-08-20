from __future__ import annotations

import json
import logging
import os
import shutil
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from serial.tools import list_ports

from config import USB_ID_REGEX

logger = logging.getLogger("auto-usbip-client")

def ensure_vhci_loaded() -> bool:
    """Ensure the Linux kernel vhci-hcd module is loaded."""
    if sys.platform != "linux":
        return True
    if Path("/sys/devices/platform/vhci_hcd.0").exists() or Path("/sys/devices/platform/vhci_hcd").exists() or Path("/sys/module/vhci_hcd").exists():
        return True
    try:
        subprocess.run(["modprobe", "vhci-hcd"], capture_output=True, timeout=1.0)
        if Path("/sys/module/vhci_hcd").exists():
            return True
        if shutil.which("pkexec"):
            subprocess.run(["pkexec", "--disable-internal-agent", "modprobe", "vhci-hcd"], capture_output=True, timeout=3.0)
    except Exception:
        pass
    return Path("/sys/module/vhci_hcd").exists()


_CAN_RUN_USBIP_DIRECT: bool | None = None
_HAS_PKEXEC: bool | None = None


def _get_usbip_cmd(args: list[str]) -> list[str]:
    global _CAN_RUN_USBIP_DIRECT, _HAS_PKEXEC
    if sys.platform == "win32":
        from core.resources import get_app_dir
        bundled_win_usbip = get_app_dir() / "bin" / "usbip.exe"
        if bundled_win_usbip.exists():
            return [str(bundled_win_usbip)] + args
        return ["usbip.exe"] + args

    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return ["usbip"] + args

    # 1. Direct execution (udev TAG+="uaccess" or cap_net_admin,cap_sys_admin+ep)
    if _CAN_RUN_USBIP_DIRECT is None:
        try:
            test_res = subprocess.run(["usbip", "port"], capture_output=True, text=True, timeout=0.4)
            _CAN_RUN_USBIP_DIRECT = (test_res.returncode == 0 or "permission denied" not in test_res.stderr.lower())
        except Exception:
            _CAN_RUN_USBIP_DIRECT = False

    if _CAN_RUN_USBIP_DIRECT:
        return ["usbip"] + args

    # 2. Polkit pkexec integration (org.autousbip.client.policy)
    if _HAS_PKEXEC is None:
        _HAS_PKEXEC = shutil.which("pkexec") is not None

    if _HAS_PKEXEC:
        return ["pkexec", "--disable-internal-agent", "usbip"] + args

    # 3. Graceful fallback to passwordless sudo if Polkit is not available
    return ["sudo", "-n", "usbip"] + args


REMOTE_DEV_REGEX = re.compile(r"^\s*([A-Za-z0-9.\-_]+):\s*(.+)$")
VID_PID_REGEX = re.compile(r"\(([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\)")

REMOTE_DEVICE_NAME_CACHE: dict[tuple[str, str], str] = {}


def get_remote_usb_devices_info(ip: str, token: str = "") -> list[tuple[str, str]] | None:
    from core.usb_ids import resolve_usb_device_name
    devices: list[tuple[str, str]] = []

    # 1. Query server control socket on port 3241 via encrypted TLS ServerControlClient
    server_has_control_daemon = False
    try:
        from core.server_control import ServerControlClient
        client = ServerControlClient(ip, token=token, timeout=1.5, use_tls=True)
        resp_data = client.get_devices()
        if resp_data is not None:
            server_has_control_daemon = True
            if resp_data.get("status") == "ok" and "devices" in resp_data:
                bound = set(resp_data.get("currently_bound", []))
                for bus_id, dev_title in resp_data["devices"].items():
                    if bus_id not in bound:
                        continue
                    devices.append((bus_id, dev_title))
                    REMOTE_DEVICE_NAME_CACHE[(ip.strip(), bus_id.strip())] = dev_title
                return devices
            elif resp_data.get("status") == "error" and "Unauthorized" in resp_data.get("message", ""):
                # Authentication token is missing or invalid! Strictly return None so no devices are attached or exposed.
                logger.warning(f"[Security] Server {ip} authentication failed: Valid token required.")
                return None
    except Exception as e:
        logger.debug(f"Server control client check error for {ip}: {e}")

    # If the server has an Auto-USBIP daemon with auth or was reached, do not bypass auth.
    if server_has_control_daemon:
        return None

    # 2. Fallback to standard raw usbip list -p -r only for legacy/unmanaged USB/IP servers without Auto-USBIP daemon
    try:
        p = subprocess.run(_get_usbip_cmd(["list", "-p", "-r", ip]), capture_output=True, text=True, timeout=1.5)
        if p.returncode != 0:
            return devices
        for line in p.stdout.splitlines():
            match = REMOTE_DEV_REGEX.match(line)
            if match:
                bus_id = match.group(1)
                raw_desc = match.group(2).strip()
                desc = raw_desc

                vid_pid_match = VID_PID_REGEX.search(raw_desc)
                if vid_pid_match:
                    vid_str, pid_str = vid_pid_match.groups()
                    desc = resolve_usb_device_name(vid_str, pid_str, raw_desc, bus_id=bus_id)

                devices.append((bus_id, desc))
                REMOTE_DEVICE_NAME_CACHE[(ip.strip(), bus_id.strip())] = desc
        return devices
    except Exception:
        return []


def get_remote_usb_devices(ip: str, token: str = "") -> list[str]:
    info = get_remote_usb_devices_info(ip, token=token)
    if info is None:
        return []
    return [bus_id for bus_id, _ in info]


def get_imported_devices():
    from services.server_connection import ImportedDevice
    try:
        p = subprocess.run(_get_usbip_cmd(["port"]), capture_output=True, text=True, timeout=1.5)
        ports: list[ImportedDevice] = []
        if p.returncode != 0:
            return ports
        serial_connections = list_ports.comports()

        matches = ImportedDevice.BLOCK_REGEX.findall(p.stdout)
        for port, speed, desc in matches:
            ports.append(ImportedDevice(port, speed, desc, serial_connections))
        return ports
    except Exception:
        return []


_PORT_MAP_CACHE: tuple[float, dict[str, tuple[str, str]]] = (0.0, {})


def get_port_to_bus_map(force_refresh: bool = False) -> dict[str, tuple[str, str]]:
    global _PORT_MAP_CACHE
    now = time.time()
    if not force_refresh and (now - _PORT_MAP_CACHE[0]) < 1.0:
        return _PORT_MAP_CACHE[1]

    try:
        p = subprocess.run(_get_usbip_cmd(["port"]), capture_output=True, text=True, timeout=1.5)
        port_map: dict[str, tuple[str, str]] = {}
        if p.returncode != 0:
            _PORT_MAP_CACHE = (now, port_map)
            return port_map

        current_port = None
        for line in p.stdout.splitlines():
            port_match = re.match(r"^Port\s+([0-9a-zA-Z.\-_]+):", line)
            if port_match:
                current_port = port_match.group(1)
            elif current_port and "usbip://" in line:
                uri_match = re.search(r"usbip://([^:/]+):[0-9]+/([A-Za-z0-9.\-_]+)", line)
                if uri_match:
                    s_ip = uri_match.group(1)
                    b_id = uri_match.group(2)
                    port_map[current_port] = (s_ip, b_id)
                    try:
                        p_int = str(int(current_port))
                        port_map[p_int] = (s_ip, b_id)
                        port_map[p_int.zfill(2)] = (s_ip, b_id)
                    except Exception:
                        pass
                    current_port = None
        _PORT_MAP_CACHE = (now, port_map)
        return port_map
    except Exception:
        return _PORT_MAP_CACHE[1]


def get_locally_attached_vid_pids() -> set[str]:
    """Instantly inspect local Linux sysfs for currently attached USB VID:PIDs with zero sudo overhead."""
    usb_dir = Path("/sys/bus/usb/devices")
    vids = set()
    if usb_dir.exists():
        try:
            for dev in usb_dir.iterdir():
                v_file = dev / "idVendor"
                p_file = dev / "idProduct"
                if v_file.exists() and p_file.exists():
                    try:
                        v = v_file.read_text().strip().lower().zfill(4)
                        p = p_file.read_text().strip().lower().zfill(4)
                        if v != "1d6b":  # Exclude root Linux hubs
                            vids.add(f"{v}:{p}")
                    except Exception:
                        pass
        except Exception:
            pass
    return vids


def set_vhci_polling_rate(port: str, interval_ms: int = 1) -> bool:
    """Set the interrupt endpoint bInterval for a specific imported VHCI port."""
    try:
        port_num = int(port)
        vhci_base = Path("/sys/devices/platform/vhci_hcd.0")
        if not vhci_base.exists():
            vhci_base = Path("/sys/devices/platform/vhci_hcd")

        for ep_path in vhci_base.glob(f"**/*-{port_num + 1}/**/ep_*"):
            interval_file = ep_path / "interval"
            if interval_file.exists():
                try:
                    interval_file.write_text(str(interval_ms))
                    logger.info(f"Set polling interval to {interval_ms}ms on {ep_path.name}")
                except PermissionError:
                    subprocess.run(
                        ["sudo", "-n", "sh", "-c", f"echo {interval_ms} > {interval_file}"],
                        capture_output=True,
                    )
        return True
    except Exception as e:
        logger.debug(f"Failed to adjust VHCI polling rate: {e}")
        return False


def attach_device(server: str, usbid: str) -> bool:
    """Attach remote USB device to local VHCI port and apply low-latency polling."""
    try:
        cmd = _get_usbip_cmd(["attach", "-r", server, "-b", usbid])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=4.0)
        if result.returncode == 0:
            time.sleep(0.15)
            port_map = get_port_to_bus_map(force_refresh=True)
            for port, (s_ip, b_id) in port_map.items():
                if s_ip == server and b_id == usbid:
                    set_vhci_polling_rate(port, interval_ms=1)
                    break
            return True
        return False
    except Exception:
        return False


def detach_device(port: str) -> bool:
    """Detach a device cleanly by port index."""
    global _PORT_MAP_CACHE
    _PORT_MAP_CACHE = (0.0, {})
    try:
        p_str = str(port).strip()
        p_int = str(int(p_str)) if p_str.isdigit() else p_str
        p_pad = p_int.zfill(2) if p_int.isdigit() else p_str

        p = subprocess.run(_get_usbip_cmd(["detach", "-p", p_int]), capture_output=True, text=True, timeout=2.0)
        if p.returncode != 0 and p_pad != p_int:
            p = subprocess.run(_get_usbip_cmd(["detach", "-p", p_pad]), capture_output=True, text=True, timeout=2.0)
        return p.returncode == 0
    except Exception:
        return False


def detach_all_ports():
    for device in get_imported_devices():
        device.detach()


detach_port = detach_device