import logging
import os
import shutil
import subprocess
import sys
import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

REMOTE_DEVICE_IN_USE_CACHE: dict[tuple[str, str], dict] = {}

@dataclass
class ImportedPort:
    port: str
    status: str
    speed: str
    devid: str
    busid: str
    uri: str
    device_name: str = ""

# Suppress console window popping up on Windows when executing child processes
_SUBPROCESS_KWARGS = {}
if sys.platform == "win32":
    _SUBPROCESS_KWARGS["creationflags"] = subprocess.CREATE_NO_WINDOW

def _get_windows_driver_dir() -> Path:
    """Return the primary driver directory, checking Program Files first, then LocalAppData."""
    # 1. Check next to client executable (e.g. C:\Program Files\AutoUSBIP-QT\drivers or root)
    exe_dir = Path(sys.executable).parent
    if (exe_dir / "drivers" / "usbip.exe").exists():
        return exe_dir / "drivers"
    if (exe_dir / "usbip.exe").exists():
        return exe_dir
    
    # 2. Check LocalAppData fallback
    local_app_data = os.environ.get('LOCALAPPDATA')
    base = Path(local_app_data) if local_app_data else (Path.home() / 'AppData' / 'Local')
    driver_dir = base / 'auto-usbip' / 'bin'
    driver_dir.mkdir(parents=True, exist_ok=True)
    return driver_dir

def _install_windows_driver_auto() -> bool:
    """Automatically download, extract, and install the signed USB/IP-Win VHCI driver package."""
    try:
        import urllib.request
        import zipfile
        import tempfile

        app_bin = _get_windows_driver_dir()

        logger.info("[Windows Driver Pre-Flight] USB/IP driver binaries not found. Initiating automated setup...")
        zip_url = "https://github.com/cezanne/usbip-win/releases/download/v0.3.6-dev/usbip-win-0.3.6-dev.zip"
        
        with tempfile.TemporaryDirectory(prefix="autousbip_driver_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            zip_file = tmp_path / "usbip-win.zip"
            
            logger.info(f"[Windows Driver Pre-Flight] Downloading signed usbip-win driver from {zip_url}...")
            urllib.request.urlretrieve(zip_url, zip_file)
            
            logger.info("[Windows Driver Pre-Flight] Extracting driver package...")
            with zipfile.ZipFile(zip_file, "r") as zf:
                zf.extractall(tmp_path)

            for ext in ("usbip.exe", "usbip_test.exe", "*.sys", "*.inf", "*.cer"):
                for matched in tmp_path.rglob(ext):
                    dest = app_bin / matched.name
                    shutil.copy2(matched, dest)
                    logger.info(f"[Windows Driver Pre-Flight] Bundled driver component: {matched.name}")

            inf_files = list(app_bin.rglob("usbip_vhci.inf"))
            cer_files = list(app_bin.rglob("*.cer"))

            if inf_files:
                inf_path = str(inf_files[0].resolve())
                cer_cmds = ""
                if cer_files:
                    cer_path = str(cer_files[0].resolve())
                    cer_cmds = f'certutil -addstore \"TrustedPublisher\" \"{cer_path}\" ; certutil -addstore \"Root\" \"{cer_path}\" ; '
                
                cmd = f'Start-Process powershell -Verb RunAs -Wait -ArgumentList "-NoProfile -ExecutionPolicy Bypass -Command {cer_cmds}pnputil /add-driver `{inf_path}` /install"'
                
                logger.info("[Windows Driver Pre-Flight] Requesting UAC elevation to register VHCI driver with pnputil...")
                res = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd], capture_output=True, text=True, timeout=60.0)
                logger.info(f"[Windows Driver Pre-Flight] Driver installer exit code: {res.returncode}")

        bundled_win_usbip = app_bin / "usbip.exe"
        return bundled_win_usbip.exists() or (shutil.which("usbip.exe") is not None)
    except Exception as e:
        logger.error(f"[Windows Driver Pre-Flight] Automated driver setup failed: {e}", exc_info=True)
        return False


def ensure_vhci_loaded() -> bool:
    """Ensure the Linux kernel vhci-hcd module or Windows USB/IP driver is available, auto-installing if missing."""
    if sys.platform == "win32":
        bundled_win_usbip = _get_windows_driver_dir() / "usbip.exe"
        if bundled_win_usbip.exists() or shutil.which("usbip.exe"):
            return True
        logger.info("[Windows Driver Pre-Flight] usbip.exe not present. Triggering automatic driver installation...")
        return _install_windows_driver_auto()

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


def _find_usbip_bin() -> str:
    """Find the usbip executable across all Linux distributions (Ubuntu, Debian, Fedora, Arch, Alpine, NixOS, openSUSE)."""
    # 1. Check standard PATH
    found = shutil.which("usbip")
    if found:
        return found
    
    # 2. Check standard system binary locations
    candidate_paths = [
        "/usr/sbin/usbip",
        "/usr/bin/usbip",
        "/sbin/usbip",
        "/bin/usbip",
        "/usr/local/sbin/usbip",
        "/usr/local/bin/usbip",
        "/run/current-system/sw/bin/usbip",  # NixOS
    ]
    for p in candidate_paths:
        if Path(p).is_file() and os.access(p, os.X_OK):
            return p

    # 3. Check Debian/Ubuntu linux-tools kernel specific paths: /usr/lib/linux-tools/*/usbip
    linux_tools_matches = list(Path("/usr/lib/linux-tools").glob("*/usbip"))
    if linux_tools_matches:
        # Sort to pick highest kernel version
        linux_tools_matches.sort(key=lambda x: str(x), reverse=True)
        return str(linux_tools_matches[0])

    return "usbip"


def _get_usbip_cmd(args: list[str]) -> list[str]:
    global _CAN_RUN_USBIP_DIRECT, _HAS_PKEXEC
    if sys.platform == "win32":
        bundled_win_usbip = _get_windows_driver_dir() / "usbip.exe"
        if bundled_win_usbip.exists():
            return [str(bundled_win_usbip)] + args
        return ["usbip.exe"] + args

    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return [_find_usbip_bin()] + args

    # 1. Direct execution (udev TAG+="uaccess" or cap_net_admin,cap_sys_admin+ep)
    if _CAN_RUN_USBIP_DIRECT is None:
        try:
            test_res = subprocess.run([_find_usbip_bin(), "port"], capture_output=True, text=True, timeout=0.4)
            _CAN_RUN_USBIP_DIRECT = (test_res.returncode == 0 or "permission denied" not in test_res.stderr.lower())
        except Exception:
            _CAN_RUN_USBIP_DIRECT = False

    usbip_path = _find_usbip_bin()
    if _CAN_RUN_USBIP_DIRECT:
        return [usbip_path] + args

    # 2. Polkit pkexec integration (org.autousbip.client.policy)
    if _HAS_PKEXEC is None:
        _HAS_PKEXEC = shutil.which("pkexec") is not None

    if _HAS_PKEXEC:
        return ["pkexec", "--disable-internal-agent", usbip_path] + args

    # 3. Graceful fallback to passwordless sudo if Polkit is not available
    return ["sudo", "-n", usbip_path] + args


def list_imported_ports() -> List[ImportedPort]:
    """
    Parses output of `usbip port` to find all currently attached/imported USB/IP devices.
    Returns a list of ImportedPort dataclass instances.
    """
    ensure_vhci_loaded()
    cmd = _get_usbip_cmd(["port"])
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=3.0, **_SUBPROCESS_KWARGS)
    except Exception as e:
        logger.debug(f"Failed to query imported usbip ports: {e}")
        return []

    lines = res.stdout.splitlines()
    ports: List[ImportedPort] = []
    
    current_port: Optional[ImportedPort] = None
    
    # Regex patterns
    # Port 00: <Port in Use> at Full Speed(12Mbps) OR Port 0: <Port in Use>
    port_header_re = re.compile(r"^Port\s+(\d+):\s+<([^>]+)>\s*(?:at\s+([^(]+)\s*(?:\(([^)]+)\))?)?")
    # -> usbip://192.168.1.100:3240/1-1
    uri_re = re.compile(r"^\s*->\s+usbip://([^/:]+(?::\d+)?)/(\S+)")
    # (Port in Use) or device details
    #   Vendor 046d : Logitech, Inc. (046d:c216)
    devid_re = re.compile(r"\(([0-9a-fA-F]{4}:[0-9a-fA-F]{4})\)")

    for line in lines:
        p_match = port_header_re.search(line)
        if p_match:
            if current_port and current_port.busid:
                ports.append(current_port)
            p_num = p_match.group(1)
            p_status = p_match.group(2).strip()
            p_speed = p_match.group(3).strip() if p_match.group(3) else ""
            current_port = ImportedPort(
                port=p_num,
                status=p_status,
                speed=p_speed,
                devid="",
                busid="",
                uri="",
                device_name=""
            )
            continue
            
        if current_port:
            u_match = uri_re.search(line)
            if u_match:
                current_port.uri = u_match.group(1)
                current_port.busid = u_match.group(2)
                continue
                
            d_match = devid_re.search(line)
            if d_match and not current_port.devid:
                current_port.devid = d_match.group(1).lower()
                # Clean up rest of line for description if available
                dev_desc = line.split("->")[0].strip()
                if dev_desc:
                    current_port.device_name = dev_desc
                continue

    if current_port and current_port.busid:
        ports.append(current_port)

    return ports


def attach_device(host: str, busid: str, port: int = 3240) -> tuple[bool, str]:
    """
    Attaches a remote USB device using `usbip attach -r <host> -b <busid>` (and `-p <port>` if non-default).
    Returns (success: bool, message: str).
    """
    ensure_vhci_loaded()
    
    # Check if already imported
    imported = list_imported_ports()
    for imp in imported:
        if imp.busid == busid and (host in imp.uri):
            logger.info(f"Device {busid} from {host} is already attached to Port {imp.port}.")
            return True, f"Device already attached on Port {imp.port}"

    args = ["attach", "-r", host, "-b", busid]
    if port != 3240:
        args.extend(["-p", str(port)])
        
    cmd = _get_usbip_cmd(args)
    try:
        logger.info(f"Executing USB/IP attach: {' '.join(cmd)}")
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=8.0, **_SUBPROCESS_KWARGS)
        if res.returncode == 0:
            logger.info(f"Successfully attached device {busid} from {host}")
            return True, "Successfully attached device"
        else:
            err = res.stderr.strip() or res.stdout.strip()
            logger.warning(f"Failed to attach device {busid}: {err}")
            return False, f"Attach failed: {err}"
    except subprocess.TimeoutExpired:
        logger.error(f"Attach command timed out for {busid}@{host}")
        return False, "Attach command timed out"
    except Exception as e:
        logger.error(f"Exception while attaching device {busid}: {e}")
        return False, str(e)


def detach_port(port: str) -> tuple[bool, str]:
    """
    Detaches a port using `usbip detach -p <port>`.
    Returns (success: bool, message: str).
    """
    ensure_vhci_loaded()
    # Normalize port string (e.g. '00' -> '0' if needed depending on tool, but standard accepts integer string)
    cmd = _get_usbip_cmd(["detach", "-p", str(int(port))])
    try:
        logger.info(f"Executing USB/IP detach for port {port}: {' '.join(cmd)}")
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5.0, **_SUBPROCESS_KWARGS)
        if res.returncode == 0:
            logger.info(f"Successfully detached port {port}")
            return True, f"Port {port} detached"
        else:
            err = res.stderr.strip() or res.stdout.strip()
            logger.warning(f"Failed to detach port {port}: {err}")
            return False, f"Detach failed: {err}"
    except subprocess.TimeoutExpired:
        logger.error(f"Detach command timed out for port {port}")
        return False, "Detach timed out"
    except Exception as e:
        logger.error(f"Exception while detaching port {port}: {e}")
        return False, str(e)


def detach_device(host_or_port: str, busid: str | None = None) -> tuple[bool, str]:
    """
    Finds the imported port corresponding to host and busid (or direct port if single argument), and detaches it.
    Returns (success: bool, message: str).
    """
    if busid is None:
        return detach_port(host_or_port)

    host = host_or_port
    imported = list_imported_ports()
    target_port: Optional[str] = None
    for imp in imported:
        if imp.busid == busid and (host in imp.uri or not host):
            target_port = imp.port
            break
            
    if target_port is None:
        logger.info(f"Device {busid} (host {host}) is not currently attached.")
        return True, "Device not attached"
        
    return detach_port(target_port)

def get_locally_attached_vid_pids() -> set[str]:
    """Inspect local Linux sysfs for currently attached USB VID:PIDs with zero sudo overhead."""
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

def get_port_to_bus_map(force_refresh: bool = False) -> dict[str, tuple[str, str]]:
    """Maps imported port numbers to (server_ip, busid)."""
    ports = list_imported_ports()
    port_map = {}
    for p in ports:
        port_map[p.port] = (p.uri, p.busid)
        if p.port.isdigit():
            port_map[str(int(p.port))] = (p.uri, p.busid)
            port_map[p.port.zfill(2)] = (p.uri, p.busid)
    return port_map

def detach_all_ports():
    """Detach all currently imported ports."""
    for p in list_imported_ports():
        detach_port(p.port)

def get_imported_devices() -> list:
    """Return list of imported devices as ImportedDevice objects."""
    from services.server_connection import ImportedDevice
    ports = list_imported_ports()
    imported_list = []
    for p in ports:
        imported_list.append(
            ImportedDevice(
                port=p.port,
                speed_raw=p.speed,
                desc_raw=f"{p.device_name} ({p.devid})" if p.devid else (p.device_name or "USB Device"),
                serial_connections=[]
            )
        )
    return imported_list

def get_remote_usb_devices_info(server: str, port: int = 3240, token: str = "") -> list[tuple[str, str]] | None:
    """Query remote server for exportable USB devices."""
    ensure_vhci_loaded()
    args = ["list", "-r", server]
    if port != 3240:
        args.extend(["-p", str(port)])
    cmd = _get_usbip_cmd(args)
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=3.5, **_SUBPROCESS_KWARGS)
        if res.returncode != 0:
            return []
        
        devices = []
        # Parse usbip list output:
        #  - 1-1: Logitech, Inc. (046d:c216)
        #  - 1-1.2: SanDisk Corp. Cruzer (0781:5567)
        dev_re = re.compile(r"^\s*([0-9]+-[0-9.]+):\s*(.*)$")
        for line in res.stdout.splitlines():
            m = dev_re.match(line)
            if m:
                devices.append((m.group(1), m.group(2).strip()))
        return devices
    except Exception as e:
        logger.debug(f"Failed to query remote USB devices from {server}: {e}")
        return []
