#!/usr/bin/env python3

import collections
import fcntl
import json
import logging
import os
import re
import select
import shutil
import signal
import socket
import ssl
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

# Elevate process priority to prevent background scheduler preemption
try:
    os.nice(-10)
except Exception:
    pass

logger = logging.getLogger("autousbip")
logger.setLevel(logging.INFO)
logger.propagate = False
LOG_BUFFER = collections.deque(maxlen=300)


class BufferLogHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            if not LOG_BUFFER or LOG_BUFFER[-1] != msg:
                LOG_BUFFER.append(msg)
        except Exception:
            pass


def log_op(level: str, tag: str, message: str):
    """Log an operational event to logger and buffer."""
    if level == "error":
        logger.error(f"[{tag.upper()}] {message}")
    elif level == "warning":
        logger.warning(f"[{tag.upper()}] {message}")
    else:
        logger.info(f"[{tag.upper()}] {message}")


def get_recent_logs(max_lines=150) -> list[str]:
    if LOG_BUFFER:
        return list(LOG_BUFFER)[-max_lines:]
    return [f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [INFO] Auto USB/IP daemon active on {get_local_ip()}:{PORT} (Monitoring USB ports)"]


try:
    from zeroconf import ServiceInfo, Zeroconf
    HAS_ZEROCONF = True
except ImportError:
    HAS_ZEROCONF = False

try:
    import pyudev
    HAS_PYUDEV = True
except ImportError:
    HAS_PYUDEV = False

PORT = 3240
CONTROL_PORT = 3241

# Default blacklist of known internal Raspberry Pi hardware, Ethernet adapters, and USB root/hub controllers
DEFAULT_BLACKLIST_VID_PID = {
    "0424:ec00",  # SMSC LAN9512/LAN9514 Fast Ethernet Adapter (Pi internal Ethernet)
    "0424:7800",  # Microchip/SMSC LAN7800 Gigabit Ethernet Adapter (Pi 3B+)
    "0424:7500",  # Microchip LAN7500 USB Gigabit Ethernet
    "0bda:8152",  # Realtek RTL8152 USB Fast Ethernet
    "0bda:8153",  # Realtek RTL8153 USB Gigabit Ethernet
    "0bda:8156",  # Realtek RTL8156 USB 2.5G Ethernet
    "0424:9514",  # Standard SMSC USB Hub controller
    "0424:9512",  # Standard SMSC USB Hub controller
    "0424:2514",  # Microchip USB 2.0 Hub Controller
    "0424:2512",  # Microchip USB 2.0 Hub Controller
    "2109:3431",  # VIA Labs USB 3.0 Hub (Raspberry Pi 4)
    "2109:2817",  # VIA Labs USB 2.0 Hub (Raspberry Pi 4)
    "1d6b:0002",  # Linux Foundation 2.0 root hub
    "1d6b:0003",  # Linux Foundation 3.0 root hub
    "1d6b:0001",  # Linux Foundation 1.1 root hub
    "05e3:0610",  # Genesys Logic USB 2.0 Hub
    "05e3:0608",  # Genesys Logic USB Hub
    "1a40:0101",  # Terminus Technology USB 2.0 Hub
    "1a40:0201",  # Terminus Technology USB Hub
    "0bda:5411",  # Realtek USB 2.0 Hub
    "0bda:0411",  # Realtek USB 3.0 Hub
}

BLACKLIST_VID_PID = set(DEFAULT_BLACKLIST_VID_PID)
SERVER_CONFIG_PATH = Path.home() / ".config" / "auto-usbip" / "server_config.json"

DEFAULT_SERVER_CONFIG = {
    "auto_bind": True,
    "startup_power_cycle": True,
    "vbus_off_delay": 2.5,
    "enable_auth": False,
    "auth_token": "",
    "enable_subnet_filter": False,
    "enable_discovery": True,
    "enable_wake_on_lan": False,
    "wol_target_macs": [],
    "enable_tls": True,
}

_CONFIG_LOCK = threading.Lock()
_CACHED_CONFIG = None
_CACHED_CONFIG_MTIME = 0
_SYNC_EVENT = threading.Event()


def ensure_tls_certificates() -> tuple[str, str] | None:
    """Ensure self-signed TLS certificate & private key exist for the control socket."""
    try:
        cert_dir = SERVER_CONFIG_PATH.parent
        cert_dir.mkdir(parents=True, exist_ok=True)
        cert_file = cert_dir / "server_cert.pem"
        key_file = cert_dir / "server_key.pem"

        if cert_file.exists() and key_file.exists() and cert_file.stat().st_size > 100:
            return str(cert_file), str(key_file)

        # Generate 2048-bit RSA self-signed certificate via OpenSSL
        cmd = [
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(key_file),
            "-out", str(cert_file),
            "-days", "3650",
            "-subj", "/CN=AutoUsbipServer"
        ]
        res = subprocess.run(cmd, capture_output=True)
        if res.returncode == 0 and cert_file.exists() and key_file.exists():
            os.chmod(str(key_file), 0o600)
            logger.info(f"[TLS] Generated new self-signed TLS certificate in {cert_dir}")
            return str(cert_file), str(key_file)
        else:
            logger.warning(f"[TLS] openssl certificate generation returned code {res.returncode}: {res.stderr.decode('utf-8', 'ignore')}")
    except Exception as e:
        logger.warning(f"[TLS] Failed to initialize TLS certificates: {e}")
    return None


def load_server_config() -> dict:
    global BLACKLIST_VID_PID, _CACHED_CONFIG, _CACHED_CONFIG_MTIME
    with _CONFIG_LOCK:
        try:
            if SERVER_CONFIG_PATH.exists():
                mtime = SERVER_CONFIG_PATH.stat().st_mtime
                if _CACHED_CONFIG is not None and mtime == _CACHED_CONFIG_MTIME:
                    return _CACHED_CONFIG.copy()

                raw = SERVER_CONFIG_PATH.read_text(encoding="utf-8")
                cfg = json.loads(raw)
                merged = DEFAULT_SERVER_CONFIG.copy()
                merged.update(cfg)

                if "blacklist" in cfg and isinstance(cfg["blacklist"], list):
                    BLACKLIST_VID_PID = set(DEFAULT_BLACKLIST_VID_PID).union(set(cfg["blacklist"]))
                else:
                    BLACKLIST_VID_PID = set(DEFAULT_BLACKLIST_VID_PID)

                _CACHED_CONFIG = merged.copy()
                _CACHED_CONFIG_MTIME = mtime
                return merged
        except Exception as e:
            logger.warning(f"Could not load server config: {e}")

        if _CACHED_CONFIG is None:
            _CACHED_CONFIG = DEFAULT_SERVER_CONFIG.copy()
            BLACKLIST_VID_PID = set(DEFAULT_BLACKLIST_VID_PID)
        return _CACHED_CONFIG


def save_server_config(cfg: dict) -> bool:
    global _CACHED_CONFIG, _CACHED_CONFIG_MTIME
    with _CONFIG_LOCK:
        try:
            SERVER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            SERVER_CONFIG_PATH.write_text(json.dumps(cfg, indent=4))
            _CACHED_CONFIG = cfg.copy()
            _CACHED_CONFIG_MTIME = SERVER_CONFIG_PATH.stat().st_mtime
            return True
        except Exception as e:
            logger.warning(f"Could not save server config: {e}")
            return False


GLOBAL_ZEROCONF = None


def update_zeroconf_broadcast(enable: bool):
    global GLOBAL_ZEROCONF
    if not HAS_ZEROCONF:
        return
    try:
        if enable:
            if GLOBAL_ZEROCONF is None:
                local_ip = get_local_ip()
                hostname = socket.gethostname()
                cfg = load_server_config()
                auth_needed = cfg.get("enable_auth", False) and bool(cfg.get("auth_token", ""))
                service_info = ServiceInfo(
                    "_usbip._tcp.local.",
                    f"AutoUSBIPServer-{hostname}._usbip._tcp.local.",
                    addresses=[socket.inet_aton(local_ip)],
                    port=PORT,
                    properties={
                        "version": "2.0",
                        "host": hostname,
                        "auth_required": "true" if auth_needed else "false",
                        "tls": "true" if cfg.get("enable_tls", True) else "false"
                    },
                    server=f"{hostname}.local.",
                )
                zc = Zeroconf()
                zc.register_service(service_info)
                GLOBAL_ZEROCONF = (zc, service_info)
                logger.info(f"[mDNS] Registered Zeroconf broadcast on {local_ip}:{PORT} (TLS: {cfg.get('enable_tls', True)})")
        else:
            if GLOBAL_ZEROCONF is not None:
                zc, s_info = GLOBAL_ZEROCONF
                zc.unregister_service(s_info)
                zc.close()
                GLOBAL_ZEROCONF = None
                logger.info("[mDNS] Zeroconf network discovery broadcast stopped.")
    except Exception as e:
        logger.warning(f"[mDNS] Error updating mDNS discovery service: {e}")


def ensure_kernel_modules():
    for mod in ("usbip_core", "usbip_host"):
        subprocess.run(["modprobe", mod], capture_output=True)


def safe_read_sysfs(path: Path) -> str:
    try:
        return path.read_text().strip()
    except Exception:
        return ""


def get_device_vid_pid(busid: str) -> str | None:
    sys_path = Path(f"/sys/bus/usb/devices/{busid}")
    id_vendor = safe_read_sysfs(sys_path / "idVendor")
    id_product = safe_read_sysfs(sys_path / "idProduct")
    if id_vendor and id_product:
        return f"{id_vendor}:{id_product}".lower()
    return None


_LSUSB_CACHE: tuple[float, dict[str, str]] = (0.0, {})

def get_lsusb_device_name_for_busid(busid: str) -> str:
    global _LSUSB_CACHE
    sys_path = Path(f"/sys/bus/usb/devices/{busid}")
    manufacturer = safe_read_sysfs(sys_path / "manufacturer")
    product = safe_read_sysfs(sys_path / "product")
    if product:
        return f"{manufacturer} {product}".strip() if manufacturer else product

    vid_pid = get_device_vid_pid(busid)
    if not vid_pid:
        return f"USB Device ({busid})"

    now = time.time()
    if (now - _LSUSB_CACHE[0]) < 10.0 and vid_pid in _LSUSB_CACHE[1]:
        return _LSUSB_CACHE[1][vid_pid]

    try:
        res = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=0.25)
        cache_map = {}
        for line in res.stdout.splitlines():
            m = re.search(r"ID\s+([0-9a-fA-F]{4}:[0-9a-fA-F]{4})\s*(.*)", line)
            if m:
                cache_map[m.group(1).lower()] = m.group(2).strip() or f"USB Device ({m.group(1)})"
        _LSUSB_CACHE = (now, cache_map)
        if vid_pid in cache_map:
            return cache_map[vid_pid]
    except Exception:
        pass

    return f"USB Device ({vid_pid})"


def is_usb_hub(busid: str) -> bool:
    dev_class = safe_read_sysfs(Path(f"/sys/bus/usb/devices/{busid}/bDeviceClass"))
    return dev_class == "09"


def get_uhubctl_path() -> str | None:
    path = shutil.which("uhubctl")
    if path:
        return path
    for p in ("/usr/sbin/uhubctl", "/usr/bin/uhubctl", "/usr/local/sbin/uhubctl", "/usr/local/bin/uhubctl"):
        if os.path.exists(p) and os.access(p, os.X_OK):
            return p
    return None


def power_cycle_vbus_ports(ports: str = "2,3,4,5"):
    uhub = get_uhubctl_path()
    if not uhub:
        logger.debug("uhubctl not installed; skipping VBUS power cycle.")
        return

    cfg = load_server_config()
    delay = cfg.get("vbus_off_delay", 2.5)

    logger.info(f"[VBUS POWER CYCLE] Cycling USB ports {ports} (Power OFF for {delay}s)...")
    try:
        subprocess.run([uhub, "-a", "off", "-p", ports], capture_output=True, timeout=5)
        time.sleep(delay)
        subprocess.run([uhub, "-a", "on", "-p", ports], capture_output=True, timeout=5)
        time.sleep(1.0)
        logger.info(f"[VBUS POWER CYCLE] USB ports {ports} power restored.")
    except Exception as e:
        logger.warning(f"Error during VBUS power cycle: {e}")


def power_cycle_vbus_port_for_busid(busid: str):
    uhub = get_uhubctl_path()
    if not uhub:
        reset_usb_device(busid)
        return

    match = re.search(r"^[0-9]+-([0-9]+)", busid)
    port_num = match.group(1) if match else None

    if port_num:
        logger.info(f"[VBUS POWER CYCLE] Power cycling port {port_num} for device {busid}...")
        try:
            cfg = load_server_config()
            delay = cfg.get("vbus_off_delay", 2.5)
            subprocess.run([uhub, "-a", "off", "-p", port_num], capture_output=True, timeout=4)
            time.sleep(delay)
            subprocess.run([uhub, "-a", "on", "-p", port_num], capture_output=True, timeout=4)
            time.sleep(0.8)
            logger.info(f"[VBUS POWER CYCLE] Port {port_num} ({busid}) power restored.")
            return
        except Exception as e:
            logger.warning(f"Failed uhubctl power cycle on port {port_num}: {e}")

    reset_usb_device(busid)


def reset_usb_device(busid: str):
    dev_path = Path(f"/sys/bus/usb/devices/{busid}")
    if not dev_path.exists():
        return

    authorized_path = dev_path / "authorized"
    if authorized_path.exists():
        try:
            logger.info(f"[VBUS RESET] Deauthorizing & reauthorizing {busid}...")
            authorized_path.write_text("0")
            time.sleep(0.5)
            authorized_path.write_text("1")
            time.sleep(0.5)
            return
        except Exception as e:
            logger.warning(f"Could not toggle authorized for {busid}: {e}")

    unbind_existing_interface_drivers(busid)


def unbind_existing_interface_drivers(busid: str):
    sys_path = Path(f"/sys/bus/usb/devices/{busid}")
    if not sys_path.exists():
        return

    for iface in sys_path.glob(f"{busid}:*"):
        driver_path = iface / "driver"
        if driver_path.exists():
            driver_unbind = driver_path / "unbind"
            if driver_unbind.exists():
                try:
                    driver_unbind.write_text(iface.name)
                    logger.debug(f"Unbound kernel driver from interface {iface.name}")
                except Exception as e:
                    logger.debug(f"Failed unbinding {iface.name}: {e}")


def bind_usbdevice(busid: str):
    vid_pid = get_device_vid_pid(busid)
    if vid_pid and vid_pid in BLACKLIST_VID_PID:
        logger.info(f"Skipping binding of blacklisted hardware {busid} ({vid_pid})")
        return

    dev_name = get_lsusb_device_name_for_busid(busid)
    logger.info(f"[BINDING] Exporting {busid} -> '{dev_name}' to USB/IP...")
    unbind_existing_interface_drivers(busid)

    res = subprocess.run(["usbip", "bind", "-b", busid], capture_output=True, text=True)
    if res.returncode == 0:
        logger.info(f"[BOUND] Successfully exported {busid} ('{dev_name}')")
    else:
        logger.warning(f"Failed to bind {busid}: {res.stderr.strip()}")


def configure_tcp_keepalive():
    try:
        subprocess.run(["sysctl", "-w", "net.ipv4.tcp_keepalive_time=5"], capture_output=True)
        subprocess.run(["sysctl", "-w", "net.ipv4.tcp_keepalive_intvl=2"], capture_output=True)
        subprocess.run(["sysctl", "-w", "net.ipv4.tcp_keepalive_probes=3"], capture_output=True)
        logger.info("Configured low-latency TCP keepalive (5s probe, 2s intvl).")
    except Exception as e:
        logger.warning(f"Could not set TCP keepalive sysctl: {e}")


def rebind_all_devices():
    logger.info("[REBIND] Rebinding all USB devices...")
    for b in list_available_devices():
        unbind_usbdevice(b)
        time.sleep(0.05)
        bind_usbdevice(b)
    logger.info("[REBIND] All USB devices rebound.")


def unbind_usbdevice(busid: str):
    subprocess.run(["usbip", "unbind", "-b", busid], capture_output=True)


def get_currently_bound_busids() -> set[str]:
    bound = set()
    try:
        res = subprocess.run(["usbip", "list", "-p", "-l"], capture_output=True, text=True, timeout=1.0)
        for line in res.stdout.splitlines():
            if "busid=" in line and "status=Exported" in line:
                m = re.search(r"busid=([A-Za-z0-9.\-_]+)", line)
                if m:
                    bound.add(m.group(1).strip())
    except Exception:
        pass
    return bound


def is_network_adapter(busid: str) -> bool:
    sys_path = Path(f"/sys/bus/usb/devices/{busid}")
    for net_path in sys_path.glob("**/net/*"):
        if net_path.exists():
            return True
    vid_pid = get_device_vid_pid(busid)
    if vid_pid and vid_pid in BLACKLIST_VID_PID:
        return True
    return False


def cleanup_blacklisted_bindings():
    bound = get_currently_bound_busids()
    for busid in bound:
        vid_pid = get_device_vid_pid(busid)
        if vid_pid and vid_pid in BLACKLIST_VID_PID:
            logger.info(f"Unbinding blacklisted hardware device {busid} ({vid_pid})...")
            unbind_usbdevice(busid)


def list_available_devices() -> list[str]:
    devices = []
    usb_dir = Path("/sys/bus/usb/devices")
    if not usb_dir.exists():
        return devices

    for p in usb_dir.iterdir():
        name = p.name
        # Match USB device busids like "1-1", "1-1.2", "2-1.3", ignoring root hubs "usb1", "usb2" and interface endpoints "1-1:1.0"
        if re.match(r"^[0-9]+-[0-9]+(\.[0-9]+)*$", name):
            if is_usb_hub(name):
                continue
            if is_network_adapter(name):
                continue
            vid_pid = get_device_vid_pid(name)
            if vid_pid and vid_pid in BLACKLIST_VID_PID:
                continue
            devices.append(name)

    return sorted(devices)


_last_logged_devices = None
_last_sync_tick = 0


def sync_devices():
    global _last_logged_devices, _last_sync_tick
    cfg = load_server_config()
    if not cfg.get("auto_bind", True):
        return

    detected_busids = list_available_devices()
    bound_busids = get_currently_bound_busids()
    current_set = set(detected_busids)

    # 1. Bind any unbound eligible devices
    for busid in detected_busids:
        if busid not in bound_busids:
            bind_usbdevice(busid)

    # 2. Unbind removed devices
    for busid in bound_busids:
        if busid not in current_set:
            unbind_usbdevice(busid)

    # 3. Check Wake-on-LAN trigger if new device was plugged in
    if _last_logged_devices is not None:
        newly_plugged = current_set - _last_logged_devices
        if newly_plugged and cfg.get("enable_wake_on_lan", False):
            target_macs = cfg.get("wol_target_macs", [])
            for mac in target_macs:
                if mac:
                    log_op("info", "WOL", f"New USB device plugged in on bus ({', '.join(newly_plugged)})! Broadcasting Wake-on-LAN to {mac}...")
                    send_wake_on_lan(mac)

    now = time.time()
    if current_set != _last_logged_devices or (now - _last_sync_tick > 10):
        _last_logged_devices = current_set
        _last_sync_tick = now
        dev_summaries = [f"bus {b} -> {get_lsusb_device_name_for_busid(b)}" for b in detected_busids]
        m = get_system_metrics()
        m_str = f"CPU: {m.get('cpu_temp', 'N/A')} | RAM: {m.get('ram_usage', 'N/A')}"
        if dev_summaries:
            log_op("info", "DAEMON TICK", f"{len(detected_busids)} USB port(s) exported to USB/IP ({m_str})")
            for ds in dev_summaries:
                log_op("info", "PORT STATUS", f"  • {ds} [BOUND & READY]")
        else:
            log_op("info", "DAEMON TICK", f"Monitoring USB ports... No active target devices plugged in ({m_str})")


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


class GracefulKiller:
    kill_now = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, *args):
        self.kill_now = True


def send_wake_on_lan(mac_address: str, broadcast_ip: str = "255.255.255.255", port: int = 9) -> bool:
    try:
        cleaned_mac = re.sub(r"[^0-9a-fA-F]", "", mac_address)
        if len(cleaned_mac) != 12:
            return False
        mac_bytes = bytes.fromhex(cleaned_mac)
        magic_packet = b"\xff" * 6 + mac_bytes * 16
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(magic_packet, (broadcast_ip, port))
        logger.info(f"[WOL] Sent Wake-on-LAN magic packet to {mac_address}")
        return True
    except Exception as e:
        logger.warning(f"[WOL] Failed to send Wake-on-LAN packet to {mac_address}: {e}")
        return False


def start_wol_input_monitor_thread(killer: GracefulKiller):
    def monitor_loop():
        input_dir = Path("/dev/input")
        last_event_time = 0
        opened_fds = {}

        while not killer.kill_now:
            try:
                cfg = load_server_config()
                if not cfg.get("enable_wake_on_lan", False) or not cfg.get("wol_target_macs"):
                    for fd in list(opened_fds.keys()):
                        try:
                            os.close(fd)
                        except Exception:
                            pass
                    opened_fds.clear()
                    time.sleep(2.0)
                    continue

                if input_dir.exists():
                    for event_node in input_dir.glob("event*"):
                        node_str = str(event_node)
                        if node_str not in opened_fds.values():
                            try:
                                fd = os.open(node_str, os.O_RDONLY | os.O_NONBLOCK)
                                opened_fds[fd] = node_str
                            except Exception:
                                pass

                if not opened_fds:
                    time.sleep(1.0)
                    continue

                rlist, _, _ = select.select(list(opened_fds.keys()), [], [], 1.0)
                for fd in rlist:
                    try:
                        data = os.read(fd, 64)
                        if data and len(data) >= 16:
                            now = time.time()
                            if now - last_event_time > 3.0:
                                last_event_time = now
                                target_macs = cfg.get("wol_target_macs", [])
                                for mac in target_macs:
                                    if mac:
                                        log_op("info", "WOL", f"User input detected on {opened_fds.get(fd, 'controller/keyboard')}! Sending Wake-on-LAN to {mac}...")
                                        send_wake_on_lan(mac)
                    except (OSError, IOError):
                        try:
                            os.close(fd)
                        except Exception:
                            pass
                        opened_fds.pop(fd, None)
            except Exception as e:
                logger.debug(f"WOL monitor error: {e}")
                time.sleep(1.0)

        for fd in opened_fds:
            try:
                os.close(fd)
            except Exception:
                pass

    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()
    return t


def get_system_metrics() -> dict:
    metrics = {
        "cpu_temp": "N/A",
        "cpu_usage": "N/A",
        "ram_usage": "N/A",
        "uptime": "N/A"
    }
    # CPU Temp
    for thermal_path in (Path("/sys/class/thermal/thermal_zone0/temp"), Path("/sys/devices/virtual/thermal/thermal_zone0/temp")):
        if thermal_path.exists():
            try:
                raw = thermal_path.read_text().strip()
                c = float(raw) / 1000.0
                metrics["cpu_temp"] = f"{c:.1f}°C"
                break
            except Exception:
                pass

    # RAM
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        mem_total = 0
        mem_avail = 0
        for l in lines:
            if l.startswith("MemTotal:"):
                mem_total = int(l.split()[1])
            elif l.startswith("MemAvailable:"):
                mem_avail = int(l.split()[1])
        if mem_total > 0:
            used_pct = int(((mem_total - mem_avail) / mem_total) * 100)
            metrics["ram_usage"] = f"{used_pct}%"
    except Exception:
        pass

    # Uptime
    try:
        with open("/proc/uptime") as f:
            up_secs = float(f.readline().split()[0])
        mins = int(up_secs // 60)
        hours = mins // 60
        days = hours // 24
        if days > 0:
            metrics["uptime"] = f"{days}d {hours % 24}h {mins % 60}m"
        elif hours > 0:
            metrics["uptime"] = f"{hours}h {mins % 60}m"
        else:
            metrics["uptime"] = f"{mins}m"
    except Exception:
        pass

    return metrics


def start_control_socket_thread(killer: GracefulKiller):
    def listener():
        ssl_ctx = None
        cfg = load_server_config()
        if cfg.get("enable_tls", True):
            tls_files = ensure_tls_certificates()
            if tls_files:
                cert_f, key_f = tls_files
                try:
                    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                    ssl_ctx.load_cert_chain(certfile=cert_f, keyfile=key_f)
                    logger.info(f"[TLS] Control socket secured with TLS 1.3 / 1.2.")
                except Exception as e:
                    logger.warning(f"[TLS] Could not initialize SSL context: {e}")
                    ssl_ctx = None

        try:
            server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            server_sock.bind(("0.0.0.0", CONTROL_PORT))
            server_sock.listen(5)
            server_sock.settimeout(2.0)
            logger.info(f"Control socket listening on port {CONTROL_PORT} (TLS: {'Active' if ssl_ctx else 'Disabled'})")

            while not killer.kill_now:
                try:
                    raw_conn, addr = server_sock.accept()
                    raw_conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    if hasattr(socket, "TCP_QUICKACK"):
                        raw_conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
                    raw_conn.settimeout(2.5)

                    client_ip = addr[0]
                    cfg_sec = load_server_config()

                    if cfg_sec.get("enable_subnet_filter", False):
                        if not (client_ip.startswith("192.168.") or client_ip.startswith("10.") or client_ip.startswith("172.") or client_ip in ("127.0.0.1", "::1")):
                            raw_conn.close()
                            continue

                    conn = raw_conn
                    if ssl_ctx and cfg_sec.get("enable_tls", True):
                        try:
                            conn = ssl_ctx.wrap_socket(raw_conn, server_side=True)
                        except ssl.SSLError as ssl_err:
                            logger.debug(f"[TLS] Handshake rejected/failed from {client_ip}: {ssl_err}")
                            raw_conn.close()
                            continue
                        except Exception as e:
                            logger.debug(f"[TLS] Connection wrap error from {client_ip}: {e}")
                            raw_conn.close()
                            continue

                    data = conn.recv(4096)
                    if data:
                        try:
                            req = json.loads(data.decode("utf-8"))
                            cmd = req.get("cmd", "")
                        except Exception:
                            cmd = data.decode("utf-8").strip()
                            req = {}

                        if cfg_sec.get("enable_auth", False):
                            token_sent = req.get("token", "") if isinstance(req, dict) else ""
                            expected_token = cfg_sec.get("auth_token", "")
                            if expected_token and token_sent != expected_token:
                                resp = json.dumps({"status": "error", "message": "Unauthorized"})
                                conn.sendall(resp.encode("utf-8"))
                                conn.close()
                                continue

                        if cmd in ("GET_LOGS", "GET_CONSOLE"):
                            lines_count = int(req.get("lines", 150)) if isinstance(req, dict) else 150
                            logs_list = get_recent_logs(lines_count)
                            available = list_available_devices()
                            dev_map = {b: get_lsusb_device_name_for_busid(b) for b in available}
                            resp = json.dumps({
                                "status": "ok",
                                "logs": logs_list,
                                "metrics": get_system_metrics(),
                                "devices": dev_map,
                                "currently_bound": list(get_currently_bound_busids()),
                            })
                            conn.sendall(resp.encode("utf-8"))
                        elif cmd == "GET_DEVICES" or "GET_DEVICES" in str(cmd):
                            available = list_available_devices()
                            dev_map = {b: get_lsusb_device_name_for_busid(b) for b in available}
                            resp = json.dumps({
                                "status": "ok",
                                "devices": dev_map,
                                "currently_bound": list(get_currently_bound_busids()),
                            })
                            conn.sendall(resp.encode("utf-8"))
                        elif cmd == "GET_STATUS":
                            available = list_available_devices()
                            dev_map = {b: get_lsusb_device_name_for_busid(b) for b in available}
                            resp = json.dumps({
                                "status": "ok",
                                "metrics": get_system_metrics(),
                                "devices": dev_map,
                                "blacklist": sorted(list(BLACKLIST_VID_PID)),
                                "currently_bound": list(get_currently_bound_busids()),
                                "tls": bool(ssl_ctx is not None and load_server_config().get("enable_tls", True)),
                                "config": load_server_config(),
                            })
                            conn.sendall(resp.encode("utf-8"))
                        elif cmd == "GET_CONFIG":
                            resp = json.dumps({"status": "ok", "config": load_server_config()})
                            conn.sendall(resp.encode("utf-8"))
                        elif cmd == "SET_CONFIG":
                            cfg = load_server_config()
                            new_cfg = req.get("config", {})
                            if isinstance(new_cfg, dict):
                                cfg.update(new_cfg)
                                if "auth_token" in new_cfg:
                                    token_val = str(new_cfg["auth_token"]).strip()
                                    cfg["auth_token"] = token_val
                                    cfg["enable_auth"] = bool(token_val)
                                if "enable_auth" in new_cfg:
                                    cfg["enable_auth"] = bool(new_cfg["enable_auth"]) and bool(cfg.get("auth_token", ""))
                                if "enable_discovery" in new_cfg:
                                    cfg["enable_discovery"] = bool(new_cfg["enable_discovery"])
                                    update_zeroconf_broadcast(cfg["enable_discovery"])
                                if "enable_tls" in new_cfg:
                                    cfg["enable_tls"] = bool(new_cfg["enable_tls"])
                                if "blacklist" in new_cfg and isinstance(new_cfg["blacklist"], list):
                                    BLACKLIST_VID_PID.clear()
                                    BLACKLIST_VID_PID.update(new_cfg["blacklist"])
                                    cleanup_blacklisted_bindings()
                                save_server_config(cfg)
                                resp = json.dumps({"status": "ok", "config": cfg})
                            else:
                                resp = json.dumps({"status": "error", "message": "Invalid config payload"})
                            conn.sendall(resp.encode("utf-8"))
                        elif cmd in ("RESET_ZOMBIES", "REBIND_ALL", "CLEAR_ZOMBIES"):
                            resp = json.dumps({"status": "ok", "message": "Rebinding..."})
                            conn.sendall(resp.encode("utf-8"))
                            threading.Thread(target=rebind_all_devices, daemon=True).start()
                        elif cmd in ("RESET_POWER", "CYCLE_POWER", "POWER_CYCLE"):
                            ports = req.get("ports") or req.get("port") if isinstance(req, dict) else None
                            busid = req.get("busid") or req.get("bus_id") if isinstance(req, dict) else None
                            if busid:
                                resp = json.dumps({"status": "ok", "message": f"Power cycle on bus {busid}"})
                                conn.sendall(resp.encode("utf-8"))
                                threading.Thread(target=power_cycle_vbus_port_for_busid, args=(busid,), daemon=True).start()
                            else:
                                if not ports:
                                    ports = "2,3,4,5"
                                resp = json.dumps({"status": "ok", "message": f"Power cycle on ports {ports}"})
                                conn.sendall(resp.encode("utf-8"))
                                threading.Thread(target=power_cycle_vbus_ports, args=(ports,), daemon=True).start()
                        elif cmd == "ADD_BLACKLIST":
                            vid_pid = req.get("vid_pid", "").strip().lower()
                            if vid_pid:
                                BLACKLIST_VID_PID.add(vid_pid)
                                cleanup_blacklisted_bindings()
                                resp = json.dumps({"status": "ok", "message": f"Added {vid_pid}", "blacklist": sorted(list(BLACKLIST_VID_PID))})
                            else:
                                resp = json.dumps({"status": "error", "message": "Invalid vid_pid"})
                            conn.sendall(resp.encode("utf-8"))
                        elif cmd == "REMOVE_BLACKLIST":
                            vid_pid = req.get("vid_pid", "").strip().lower()
                            if vid_pid in BLACKLIST_VID_PID:
                                BLACKLIST_VID_PID.remove(vid_pid)
                                sync_devices()
                                resp = json.dumps({"status": "ok", "message": f"Removed {vid_pid}", "blacklist": sorted(list(BLACKLIST_VID_PID))})
                            else:
                                resp = json.dumps({"status": "error", "message": f"{vid_pid} not in blacklist"})
                            conn.sendall(resp.encode("utf-8"))
                        elif cmd == "RESTART_DAEMON":
                            resp = json.dumps({"status": "ok", "message": "Restarting..."})
                            conn.sendall(resp.encode("utf-8"))
                            def _do_restart():
                                time.sleep(0.5)
                                os.execv(sys.executable, [sys.executable] + sys.argv)
                            threading.Thread(target=_do_restart, daemon=True).start()
                        elif cmd == "REGISTER_WOL_CLIENT":
                            mac = req.get("mac", "").strip().lower()
                            enabled = req.get("enabled", True)
                            cfg = load_server_config()
                            macs = set(cfg.get("wol_target_macs", []))
                            if enabled and mac:
                                macs.add(mac)
                            elif mac in macs:
                                macs.remove(mac)
                            cfg["wol_target_macs"] = sorted(list(macs))
                            cfg["enable_wake_on_lan"] = len(macs) > 0
                            save_server_config(cfg)
                            resp = json.dumps({"status": "ok", "macs": cfg["wol_target_macs"]})
                            conn.sendall(resp.encode("utf-8"))
                        elif cmd == "REBOOT_SYSTEM":
                            resp = json.dumps({"status": "ok", "message": "Rebooting..."})
                            conn.sendall(resp.encode("utf-8"))
                            def _do_reboot():
                                time.sleep(0.5)
                                subprocess.run(["systemctl", "reboot"])
                            threading.Thread(target=_do_reboot, daemon=True).start()

                    conn.close()
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.debug(f"Control socket error: {e}")
            server_sock.close()
        except Exception as e:
            logger.warning(f"Could not start control socket on port {CONTROL_PORT}: {e}")

    t = threading.Thread(target=listener, daemon=True)
    t.start()
    return t


def main():
    global logger
    buf_h = BufferLogHandler()
    buf_h.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(buf_h)
    logger.info("Starting auto-usbip server daemon...")
    ensure_kernel_modules()
    configure_tcp_keepalive()
    power_cycle_vbus_ports()

    killer = GracefulKiller()
    start_control_socket_thread(killer)
    start_wol_input_monitor_thread(killer)

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        result = s.connect_ex(("127.0.0.1", PORT))
        s.close()
        if result != 0:
            logger.info("[USBIPD] Launching native usbipd daemon...")
            subprocess.run(["usbipd", "-D"])
            time.sleep(0.2)
        else:
            logger.info("[USBIPD] usbipd daemon active and listening on port 3240.")
    except Exception as e:
        logger.error(f"Error checking usbipd: {e}")

    cfg = load_server_config()
    if cfg.get("enable_discovery", True):
        update_zeroconf_broadcast(True)

    sync_devices()

    udev_observer = None
    if HAS_PYUDEV:
        try:
            context = pyudev.Context()
            monitor = pyudev.Monitor.from_netlink(context)
            monitor.filter_by(subsystem="usb")

            def _on_udev_event(action, device):
                try:
                    dev_node = device.device_node or device.sys_name
                    prod = device.get('ID_MODEL', device.get('PRODUCT', ''))
                    logger.info(f"[HOTPLUG] Physical USB event: '{action.upper()}' on {dev_node} ({prod})")
                except Exception:
                    pass
                _SYNC_EVENT.set()

            udev_observer = pyudev.MonitorObserver(monitor, callback=_on_udev_event)
            udev_observer.start()
            logger.info("pyudev active: instant USB hotplug detection enabled.")
        except Exception as e:
            logger.warning(f"pyudev monitoring setup failed: {e}")

    heartbeat_interval = 60 if HAS_PYUDEV else 5

    try:
        while not killer.kill_now:
            event_triggered = _SYNC_EVENT.wait(timeout=heartbeat_interval)
            if killer.kill_now:
                break
            if event_triggered:
                _SYNC_EVENT.clear()
                time.sleep(0.1)
                sync_devices()
    except Exception as e:
        logger.error(f"Server exception: {e}")
    finally:
        logger.info("Shutting down auto-usbip server...")
        if udev_observer:
            try:
                udev_observer.stop()
            except Exception:
                pass
        update_zeroconf_broadcast(False)
        logger.info("Cleanup complete.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        logging.basicConfig(filename=sys.argv[1], filemode="w", level=logging.INFO)
    else:
        logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("autousbip")
    main()
