from __future__ import annotations

import array
try:
    import fcntl
except ImportError:
    fcntl = None
import logging
import os
import struct
from pathlib import Path
try:
    from PyQt6.QtGui import QIcon
except ImportError:
    QIcon = None

logger = logging.getLogger("auto-usbip-client")

# Linux Joystick IOCTL Constants
JSIOCGAXES = 0x80016A11
JSIOCGBUTTONS = 0x80016A12
JSIOCGNAME_128 = 0x80806A13
JSIOCGAXMAP = 0x80406A32
JSIOCGBTNMAP = 0x80406A34

# Evdev IOCTL Constants for absolute axis reading
EVIOCGABS = 0x80184540
EVIOCGKEY = 0x80004518

# Pre-allocated buffers for motion and joystick state parsing
_MOTION_BUF = bytearray(24)
_JS_EVENT_FORMAT = "IhBB"
_JS_EVENT_SIZE = struct.calcsize(_JS_EVENT_FORMAT)


def get_gamepad_battery_info(vid: int | None = None, pid: int | None = None) -> tuple[QIcon, str] | None:
    """Scan /sys/class/power_supply for a controller battery without recursive sysfs walks."""
    ps_path = Path("/sys/class/power_supply")
    if not ps_path.exists():
        return None

    try:
        for entry in ps_path.iterdir():
            name = entry.name.lower()
            if any(k in name for k in ("sony_controller", "ps-controller", "xbox", "gamepad", "joy", "switch", "dualsense")):
                if vid is not None and pid is not None:
                    matched = False
                    dev_symlink = entry / "device"
                    if dev_symlink.exists():
                        parent_sys = dev_symlink.resolve()
                        for _ in range(6):
                            if parent_sys == Path("/") or not parent_sys.exists():
                                break
                            v_file = parent_sys / "idVendor"
                            p_file = parent_sys / "idProduct"
                            if v_file.exists() and p_file.exists():
                                try:
                                    v = int(v_file.read_text().strip(), 16)
                                    p = int(p_file.read_text().strip(), 16)
                                    if v == vid and p == pid:
                                        matched = True
                                        break
                                except Exception:
                                    pass
                            parent_sys = parent_sys.parent
                    if not matched:
                        continue

                cap_file = entry / "capacity"
                stat_file = entry / "status"
                if cap_file.exists():
                    try:
                        cap = int(cap_file.read_text().strip())
                        status = stat_file.read_text().strip() if stat_file.exists() else "Discharging"
                        is_charging = (status.lower() == "charging")
                        
                        icon = None
                        if QIcon is not None:
                            if is_charging:
                                icon = QIcon.fromTheme("battery-charging", QIcon.fromTheme("battery-good"))
                            elif cap <= 20:
                                icon = QIcon.fromTheme("battery-low", QIcon.fromTheme("battery-caution"))
                            elif cap <= 60:
                                icon = QIcon.fromTheme("battery-good")
                            else:
                                icon = QIcon.fromTheme("battery-full", QIcon.fromTheme("battery-good"))
                            
                        desc = f"{cap}%" + (" ⚡ (Charging)" if is_charging else "")
                        return icon, desc
                    except Exception:
                        pass
    except Exception as e:
        logger.debug(f"Error checking battery: {e}")
    return None


def _fast_joystick_button_count(js_path: str) -> int:
    """Read button count with a single non-blocking ioctl without draining event buffers."""
    try:
        fd = os.open(js_path, os.O_RDONLY | os.O_NONBLOCK)
        try:
            buf_btns = bytearray(2)
            if fcntl.ioctl(fd, JSIOCGBUTTONS, buf_btns) >= 0:
                return struct.unpack("H", buf_btns)[0]
        finally:
            os.close(fd)
    except Exception:
        pass
    return 0


def find_joystick_nodes_for_device(busid: str | None, devnum: int | None = None, is_vhci: bool = False, vid: int | None = None, pid: int | None = None) -> list[str]:
    """Locate all Linux input device nodes (/dev/input/js*, /dev/input/event*, /dev/hidraw*) for a USB device."""
    js_nodes: list[str] = []
    ev_nodes: list[str] = []
    hr_nodes: list[str] = []

    v_hex = f"{vid:04x}" if vid else None
    p_hex = f"{pid:04x}" if pid else None

    # 1. Search sysfs /sys/class/input
    for sys_path in Path("/sys/class/input").glob("input*"):
        try:
            real_target = sys_path.resolve()
            path_str = str(real_target).lower()
            matched = False

            # Match by VID:PID in sysfs path or id files
            if v_hex and p_hex:
                if f":{v_hex}:{p_hex}" in path_str or f"/{v_hex}:{p_hex}" in path_str:
                    matched = True
                else:
                    v_file = sys_path / "id" / "vendor"
                    p_file = sys_path / "id" / "product"
                    if v_file.exists() and p_file.exists():
                        try:
                            if int(v_file.read_text().strip(), 16) == vid and int(p_file.read_text().strip(), 16) == pid:
                                matched = True
                        except Exception:
                            pass

            # Match by VHCI port index
            if not matched and is_vhci and busid is not None:
                try:
                    port_idx = int(busid)
                    if "vhci_hcd" in path_str and f"-{port_idx + 1}/" in path_str:
                        matched = True
                except ValueError:
                    pass

            if matched:
                for child in sys_path.iterdir():
                    if child.name.startswith("js"):
                        dev_node = f"/dev/input/{child.name}"
                        if os.path.exists(dev_node) and dev_node not in js_nodes:
                            js_nodes.append(dev_node)
                    elif child.name.startswith("event"):
                        dev_node = f"/dev/input/{child.name}"
                        if os.path.exists(dev_node) and dev_node not in ev_nodes:
                            ev_nodes.append(dev_node)
        except Exception:
            pass

    # Sort joystick nodes by button count
    js_nodes.sort(key=_fast_joystick_button_count, reverse=True)

    # 2. Match corresponding /dev/hidraw* device node
    for h in sorted(Path("/sys/class/hidraw").glob("hidraw*")):
        try:
            device_path = h.resolve()
            path_str = str(device_path).lower()
            matched = False
            if v_hex and p_hex and f":{v_hex}:{p_hex}" in path_str:
                matched = True
            elif is_vhci and busid is not None:
                try:
                    port_idx = int(busid)
                    if "vhci_hcd" in path_str and f"-{port_idx + 1}/" in path_str:
                        matched = True
                except ValueError:
                    pass

            if matched:
                hr_node = f"/dev/{h.name}"
                if os.path.exists(hr_node) and hr_node not in hr_nodes:
                    hr_nodes.append(hr_node)
        except Exception:
            pass

    return js_nodes + ev_nodes + hr_nodes


def find_touchpad_event_node(device_vid: int, device_pid: int, has_vid_pid: bool) -> str | None:
    """Find the specific /dev/input/event* device node for the controller touchpad."""
    if has_vid_pid:
        for input_path in Path("/sys/class/input").glob("input*"):
            v_file = input_path / "id" / "vendor"
            p_file = input_path / "id" / "product"
            name_file = input_path / "name"
            if v_file.exists() and p_file.exists():
                try:
                    v = int(v_file.read_text().strip(), 16)
                    p = int(p_file.read_text().strip(), 16)
                    if v == device_vid and p == device_pid:
                        name = name_file.read_text().strip().lower() if name_file.exists() else ""
                        if "touchpad" in name:
                            for child in input_path.iterdir():
                                if child.name.startswith("event"):
                                    dev_node = f"/dev/input/{child.name}"
                                    if os.path.exists(dev_node):
                                        return dev_node
                except Exception:
                    pass

    # Generic fallback search by device name
    for ev_path in sorted(Path("/dev/input").glob("event*")):
        try:
            sys_name = Path(f"/sys/class/input/{ev_path.name}/device/name")
            if sys_name.exists():
                name = sys_name.read_text().strip().lower()
                if "touchpad" in name or ("dualsense" in name and "touchpad" in name):
                    return str(ev_path)
        except Exception:
            pass
    return None


def find_motion_event_node(device_vid: int, device_pid: int, has_vid_pid: bool) -> str | None:
    """Find the specific /dev/input/event* device node for the controller 6-axis IMU sensors."""
    if has_vid_pid:
        for input_path in Path("/sys/class/input").glob("input*"):
            v_file = input_path / "id" / "vendor"
            p_file = input_path / "id" / "product"
            name_file = input_path / "name"
            if v_file.exists() and p_file.exists():
                try:
                    v = int(v_file.read_text().strip(), 16)
                    p = int(p_file.read_text().strip(), 16)
                    if v == device_vid and p == device_pid:
                        name = name_file.read_text().strip().lower() if name_file.exists() else ""
                        if "motion" in name or "sensors" in name or "accel" in name:
                            for child in input_path.iterdir():
                                if child.name.startswith("event"):
                                    dev_node = f"/dev/input/{child.name}"
                                    if os.path.exists(dev_node):
                                        return dev_node
                except Exception:
                    pass

    for ev_path in sorted(Path("/dev/input").glob("event*")):
        try:
            sys_name = Path(f"/sys/class/input/{ev_path.name}/device/name")
            if sys_name.exists():
                name = sys_name.read_text().strip().lower()
                if "motion" in name or "sensor" in name:
                    return str(ev_path)
        except Exception:
            pass
    return None


_GLOBAL_TOUCHPAD_STATE = {}

def read_touchpad_state(event_node: str) -> tuple[float, float, bool, bool]:
    """Read instant absolute touchpad coordinates and click state from kernel evdev stream."""
    from core.touchpad_control import read_touchpad_coordinates
    return read_touchpad_coordinates(event_node)


def read_motion_state(event_node: str) -> list[float]:
    """Read instant absolute 6-axis IMU gyro and accelerometer states."""
    values = [0.0] * 6
    if not event_node or not os.path.exists(event_node):
        return values

    try:
        fd = os.open(event_node, os.O_RDONLY | os.O_NONBLOCK)
    except Exception:
        return values

    try:
        # Read ABS_X..ABS_RZ (0x00..0x05) using pre-allocated buffer
        for i in range(6):
            if fcntl.ioctl(fd, EVIOCGABS + i, _MOTION_BUF) >= 0:
                val, minimum, maximum, fuzz, flat, res = struct.unpack("iiiiii", _MOTION_BUF)
                if maximum > minimum:
                    normalized = (val - minimum) / float(maximum - minimum) * 2.0 - 1.0
                    values[i] = round(max(-1.0, min(1.0, normalized)), 2)
    except Exception:
        pass
    finally:
        try:
            os.close(fd)
        except Exception:
            pass

    return values


def detect_gamepad_family(dev_name: str, vid: int | None = None, pid: int | None = None) -> tuple[str, str, str]:
    """Classify the controller brand family, display title, and specific controller subtype."""
    # Priority 1: Query community SDL_GameControllerDB
    try:
        from .sdl_db import lookup_sdl_gamepad_mapping
        m = lookup_sdl_gamepad_mapping(vid=vid, pid=pid, dev_name=dev_name)
        if m:
            return m.family, m.name, m.controller_type
    except Exception:
        pass

    # Priority 2: Fallback dynamic capability scan
    name_l = (dev_name or "").lower()
    
    # 1. PlayStation Family
    if vid == 0x054C or any(k in name_l for k in ("dualsense", "dualshock", "playstation", "ps5", "ps4", "ps3", "sixaxis", "sony")):
        if "dualsense" in name_l or (vid == 0x054C and pid in (0x0CE6, 0x0DF2)):
            return "playstation", "PlayStation 5 DualSense Wireless Controller", "PlayStation – DualSense"
        elif "ps4" in name_l or "dualshock 4" in name_l or (vid == 0x054C and pid in (0x05C4, 0x09CC)):
            return "playstation", "PlayStation 4 DualShock 4 Controller", "PlayStation – DualShock 4"
        elif "ps3" in name_l or (vid == 0x054C and pid == 0x0268):
            return "playstation", "PlayStation 3 Sixaxis/DualShock 3", "PlayStation – DualShock 3"
        return "playstation", dev_name or "Sony PlayStation Controller", "PlayStation – Compatible"

    # 2. Xbox Family
    if vid in (0x045E, 0x0E6F, 0x24C6, 0x1532) or any(k in name_l for k in ("xbox", "x-box", "microsoft", "xinput")):
        if "series" in name_l:
            return "xbox", "Xbox Wireless Controller", "Xbox – Series X/S"
        elif "one" in name_l:
            return "xbox", "Xbox One Controller", "Xbox – One"
        elif "360" in name_l:
            return "xbox", "Xbox 360 Controller", "Xbox – 360"
        return "xbox", dev_name or "Microsoft Xbox Controller", "Xbox – Compatible"

    # 3. Nintendo Family (NES, SNES, Switch, Wii, Gamecube, N64, Retro)
    if (
        vid in (0x057E, 0x12BD, 0x0079, 0x0810, 0x1A34, 0x20BC, 0x0E8F, 0x2DC8)
        or any(k in name_l for k in ("nes", "snes", "nintendo", "switch", "famicom", "gamecube", "wii", "n64", "gembird", "8bitdo", "joy-con", "pro controller", "retro", "2axes 11keys"))
    ):
        if "nes" in name_l or vid == 0x12BD or "2axes" in name_l or "gembird" in name_l:
            subtype = "Nintendo – NES (Clone / Retro)" if (vid != 0x057E or "gembird" in name_l or "2axes" in name_l) else "Nintendo – NES"
            return "nintendo", "NES USB Controller", subtype
        elif "snes" in name_l or "super nintendo" in name_l:
            subtype = "Nintendo – SNES (Clone / Retro)" if vid != 0x057E else "Nintendo – SNES"
            return "nintendo", "SNES USB Controller", subtype
        elif "gamecube" in name_l:
            return "nintendo", "Nintendo GameCube Controller", "Nintendo – GameCube"
        elif "wii" in name_l:
            return "nintendo", "Nintendo Wii Controller", "Nintendo – Wii"
        elif "switch" in name_l or vid == 0x057E:
            return "nintendo", "Nintendo Switch Pro Controller", "Nintendo – Switch Pro"
        return "nintendo", dev_name or "Nintendo USB Controller", "Nintendo – Compatible / Clone"

    return "generic", dev_name or "USB Gamepad", "Generic – HID Gamepad"


def read_joystick_state(js_path: str) -> dict | None:
    """Read instant snapshot of a Linux joystick device (/dev/input/js*) with chunked event draining."""
    if not os.path.exists(js_path):
        return None

    try:
        fd = os.open(js_path, os.O_RDONLY | os.O_NONBLOCK)
    except Exception:
        return None

    try:
        buf_name = bytearray(128)
        try:
            fcntl.ioctl(fd, JSIOCGNAME_128, buf_name)
            dev_name = buf_name.split(b"\x00")[0].decode("utf-8", "replace").strip()
        except Exception:
            dev_name = "Gamepad"

        buf_axes = bytearray(1)
        buf_btns = bytearray(2)
        num_axes = 0
        num_btns = 0
        if fcntl.ioctl(fd, JSIOCGAXES, buf_axes) >= 0:
            num_axes = buf_axes[0]
        if fcntl.ioctl(fd, JSIOCGBUTTONS, buf_btns) >= 0:
            num_btns = struct.unpack("H", buf_btns)[0]

        axmap = array.array("B", [0] * num_axes)
        try:
            fcntl.ioctl(fd, JSIOCGAXMAP, axmap, True)
            axis_map = list(axmap)
        except Exception:
            axis_map = list(range(num_axes))

        btnmap = array.array("H", [0] * num_btns)
        try:
            fcntl.ioctl(fd, JSIOCGBTNMAP, btnmap, True)
            button_map = list(btnmap)
        except Exception:
            button_map = list(range(num_btns))

        axes = [0.0] * num_axes
        buttons = [0] * num_btns

        # Drain events in 64-event chunks to minimize syscall overhead
        chunk_size = _JS_EVENT_SIZE * 64
        while True:
            try:
                data = os.read(fd, chunk_size)
                if not data:
                    break
                for offset in range(0, len(data), _JS_EVENT_SIZE):
                    chunk = data[offset : offset + _JS_EVENT_SIZE]
                    if len(chunk) < _JS_EVENT_SIZE:
                        continue
                    t, val, ev_type, ev_num = struct.unpack(_JS_EVENT_FORMAT, chunk)
                    if (ev_type & 0x02) and ev_num < num_axes:
                        axes[ev_num] = max(-1.0, min(1.0, val / 32767.0))
                    elif (ev_type & 0x01) and ev_num < num_btns:
                        buttons[ev_num] = 1 if val else 0
            except (BlockingIOError, InterruptedError):
                break
            except Exception:
                break

        return {
            "name": dev_name,
            "num_axes": num_axes,
            "num_buttons": num_btns,
            "axis_map": axis_map,
            "button_map": button_map,
            "axes": axes,
            "buttons": buttons
        }
    finally:
        try:
            os.close(fd)
        except Exception:
            pass