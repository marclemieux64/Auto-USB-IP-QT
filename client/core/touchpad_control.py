from __future__ import annotations

import errno
try:
    import fcntl
except ImportError:
    fcntl = None
import logging
import os
import struct
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("auto-usbip-client")

EVIOCGRAB = 0x40044590
EVIOCGABS = 0x80184540
EVIOCGKEY = 0x80404505

# Persistent FDs: {canonical_ev_node: fd}
TOUCHPAD_FDS: Dict[str, int] = {}
# Grab state: {canonical_ev_node: bool}
TOUCHPAD_GRABBED: Dict[str, bool] = {}
# Desired state: {port_str: bool}
PORT_MOUSE_STATE: Dict[str, bool] = {}
# Real-time multi-touch state cache: {canonical_ev_node: dict}
TOUCHPAD_STATE: Dict[str, dict] = {}


def _normalize_port(port: str | int | None) -> str:
    if port is None:
        return "0"
    p_str = str(port).strip()
    return str(int(p_str)) if p_str.isdigit() else p_str


def find_touchpad_node_for_port(port: str | int | None, vid: int = 0, pid: int = 0) -> str | None:
    """Accurately find the specific /dev/input/event* device node for the controller touchpad."""
    norm_port = _normalize_port(port)
    try:
        port_idx = int(norm_port)
    except (ValueError, TypeError):
        port_idx = None

    v_hex = f"{vid:04x}".lower() if vid else None
    p_hex = f"{pid:04x}".lower() if pid else None

    # 1. Match by sysfs input node named "touchpad" on matching VHCI port or VID:PID
    for sys_path in sorted(Path("/sys/class/input").glob("input*")):
        try:
            name_file = sys_path / "name"
            if not name_file.exists():
                continue
            name = name_file.read_text().strip().lower()
            if "touchpad" not in name:
                continue

            real_target = str(sys_path.resolve()).lower()

            if port_idx is not None:
                if f"-{port_idx + 1}/" in real_target or f"-{port_idx + 1}:" in real_target:
                    for child in sys_path.iterdir():
                        if child.name.startswith("event"):
                            ev = f"/dev/input/{child.name}"
                            if os.path.exists(ev):
                                return ev

            if v_hex and p_hex and f":{v_hex}:{p_hex}" in real_target:
                for child in sys_path.iterdir():
                    if child.name.startswith("event"):
                        ev = f"/dev/input/{child.name}"
                        if os.path.exists(ev):
                            return ev
        except Exception:
            pass

    # 2. Match any PlayStation Touchpad input node
    for sys_path in sorted(Path("/sys/class/input").glob("input*")):
        try:
            name_file = sys_path / "name"
            if not name_file.exists():
                continue
            name = name_file.read_text().strip().lower()
            if "touchpad" in name and ("dualsense" in name or "wireless controller" in name or "sony" in name):
                for child in sys_path.iterdir():
                    if child.name.startswith("event"):
                        ev = f"/dev/input/{child.name}"
                        if os.path.exists(ev):
                            return ev
        except Exception:
            pass

    return None


def get_touchpad_fd(ev_node: str) -> int | None:
    """Get or open a persistent non-blocking file descriptor for the touchpad node."""
    global TOUCHPAD_FDS
    if not ev_node or not os.path.exists(ev_node):
        return None

    fd = TOUCHPAD_FDS.get(ev_node)
    if fd is not None and fd > 0:
        return fd

    try:
        fd = os.open(ev_node, os.O_RDONLY | os.O_NONBLOCK)
        TOUCHPAD_FDS[ev_node] = fd
        return fd
    except Exception as e:
        logger.debug(f"Could not open touchpad node {ev_node}: {e}")
        return None


def is_touchpad_mouse_enabled(port: str | int | None) -> bool:
    """Check if the trackpad is actively allowed to move the desktop mouse cursor."""
    norm_port = _normalize_port(port)
    ev_node = find_touchpad_node_for_port(norm_port)
    if ev_node and TOUCHPAD_GRABBED.get(ev_node, False):
        return False
    return PORT_MOUSE_STATE.get(norm_port, True)


def set_touchpad_mouse_enabled(port: str | int | None, enabled: bool) -> bool:
    """Toggle whether the PlayStation trackpad moves the desktop mouse cursor or is isolated for gaming."""
    global TOUCHPAD_GRABBED, PORT_MOUSE_STATE

    norm_port = _normalize_port(port)
    PORT_MOUSE_STATE[norm_port] = enabled

    ev_node = find_touchpad_node_for_port(norm_port)
    if not ev_node:
        logger.warning(f"Could not locate touchpad event node for port {port}")
        return True

    fd = get_touchpad_fd(ev_node)
    if not fd:
        return True

    if enabled:
        # Release grab -> enable desktop mouse
        if TOUCHPAD_GRABBED.get(ev_node, False):
            try:
                fcntl.ioctl(fd, EVIOCGRAB, 0)
            except Exception as e:
                logger.debug(f"EVIOCGRAB release error on {ev_node}: {e}")
            TOUCHPAD_GRABBED[ev_node] = False
            logger.info(f"Released trackpad grab on {ev_node} (port {port}). Desktop mouse enabled.")
        return True
    else:
        # Acquire grab -> disable desktop mouse (Gaming Mode)
        if not TOUCHPAD_GRABBED.get(ev_node, False):
            try:
                fcntl.ioctl(fd, EVIOCGRAB, 1)
                TOUCHPAD_GRABBED[ev_node] = True
                logger.info(f"Acquired trackpad grab on {ev_node} (port {port}). Desktop mouse disabled.")
            except OSError as err:
                if err.errno == errno.EBUSY:
                    TOUCHPAD_GRABBED[ev_node] = True
                    logger.info(f"{ev_node} already grabbed. Desktop mouse disabled.")
                else:
                    logger.warning(f"Failed to grab {ev_node}: {err}")
                    return False
        return True


def read_touchpad_multi_touch(event_node: str) -> dict[str, Any]:
    """Read real-time 2-finger multi-touch coordinates, finger count, zone, and click state with isolated MT slot axes."""
    global TOUCHPAD_STATE

    default_res = {
        "f1": {"x": 0.5, "y": 0.5, "active": False},
        "f2": {"x": 0.5, "y": 0.5, "active": False},
        "click": False,
        "finger_count": 0,
        "zone": "None",
    }

    if not event_node or not os.path.exists(event_node):
        return default_res

    fd = get_touchpad_fd(event_node)
    if not fd:
        return default_res

    state = TOUCHPAD_STATE.setdefault(event_node, {
        "active_slot": 0,
        "max_x": 1919,
        "max_y": 1079,
        "initialized": False,
        "slot0_id": -1,
        "slot1_id": -1,
        "slot0_x": 0.5,
        "slot0_y": 0.5,
        "slot1_x": 0.5,
        "slot1_y": 0.5,
        "click": False,
    })

    if not state["initialized"]:
        try:
            buf_x = bytearray(24)
            if fcntl.ioctl(fd, EVIOCGABS + 0x35, buf_x) >= 0:
                _, _, mx, _, _, _ = struct.unpack("iiiiii", buf_x)
                if mx > 0:
                    state["max_x"] = mx
            buf_y = bytearray(24)
            if fcntl.ioctl(fd, EVIOCGABS + 0x36, buf_y) >= 0:
                _, _, my, _, _, _ = struct.unpack("iiiiii", buf_y)
                if my > 0:
                    state["max_y"] = my
            state["initialized"] = True
        except Exception:
            pass

    try:
        while True:
            try:
                ev_data = os.read(fd, 24 * 64)
                if not ev_data:
                    break
                for offset in range(0, len(ev_data) - 23, 24):
                    _, _, ev_type, ev_code, ev_val = struct.unpack("qqHHi", ev_data[offset:offset+24])
                    if ev_type == 0x03:  # EV_ABS
                        if ev_code == 0x2F:  # ABS_MT_SLOT
                            state["active_slot"] = 0 if ev_val <= 0 else 1
                        elif ev_code == 0x39:  # ABS_MT_TRACKING_ID
                            if state["active_slot"] == 0:
                                state["slot0_id"] = ev_val
                            else:
                                state["slot1_id"] = ev_val
                        elif ev_code == 0x35:  # ABS_MT_POSITION_X (Slot-specific)
                            norm_x = round(max(0.0, min(1.0, ev_val / float(state["max_x"]))), 4)
                            if state["active_slot"] == 0:
                                state["slot0_x"] = norm_x
                            else:
                                state["slot1_x"] = norm_x
                        elif ev_code == 0x36:  # ABS_MT_POSITION_Y (Slot-specific)
                            norm_y = round(max(0.0, min(1.0, ev_val / float(state["max_y"]))), 4)
                            if state["active_slot"] == 0:
                                state["slot0_y"] = norm_y
                            else:
                                state["slot1_y"] = norm_y
                        elif ev_code == 0x00:  # ABS_X (Legacy single-touch axis -> Slot 0 ONLY)
                            norm_x = round(max(0.0, min(1.0, ev_val / float(state["max_x"]))), 4)
                            state["slot0_x"] = norm_x
                        elif ev_code == 0x01:  # ABS_Y (Legacy single-touch axis -> Slot 0 ONLY)
                            norm_y = round(max(0.0, min(1.0, ev_val / float(state["max_y"]))), 4)
                            state["slot0_y"] = norm_y
                    elif ev_type == 0x01:  # EV_KEY
                        if ev_code == 0x14A:  # BTN_TOUCH
                            if ev_val == 0:
                                state["slot0_id"] = -1
                                state["slot1_id"] = -1
                            elif state["slot0_id"] == -1 and state["slot1_id"] == -1:
                                state["slot0_id"] = 1
                        elif ev_code == 0x14D:  # BTN_TOOL_DOUBLETAP
                            if ev_val == 1:
                                if state["slot0_id"] == -1:
                                    state["slot0_id"] = 1
                                if state["slot1_id"] == -1:
                                    state["slot1_id"] = 2
                            else:
                                state["slot1_id"] = -1
                        elif ev_code in (0x110, 0x111):  # BTN_LEFT, BTN_RIGHT
                            state["click"] = bool(ev_val)
            except (BlockingIOError, InterruptedError):
                break
            except Exception:
                break
    except Exception:
        pass

    s0_act = (state["slot0_id"] != -1)
    s1_act = (state["slot1_id"] != -1)

    if s0_act and s1_act:
        f1 = {"x": state["slot0_x"], "y": state["slot0_y"], "active": True}
        f2 = {"x": state["slot1_x"], "y": state["slot1_y"], "active": True}
        count = 2
    elif s0_act:
        f1 = {"x": state["slot0_x"], "y": state["slot0_y"], "active": True}
        f2 = {"x": state["slot1_x"], "y": state["slot1_y"], "active": False}
        count = 1
    elif s1_act:
        f1 = {"x": state["slot1_x"], "y": state["slot1_y"], "active": True}
        f2 = {"x": state["slot0_x"], "y": state["slot0_y"], "active": False}
        count = 1
    else:
        f1 = {"x": state["slot0_x"], "y": state["slot0_y"], "active": False}
        f2 = {"x": state["slot1_x"], "y": state["slot1_y"], "active": False}
        count = 0

    # Determine interactive software zone (Left / Right / Center)
    zone = "None"
    if f1["active"]:
        x_val = f1["x"]
        if x_val < 0.45:
            zone = "Left"
        elif x_val > 0.55:
            zone = "Right"
        else:
            zone = "Center"

    return {
        "f1": f1,
        "f2": f2,
        "click": state["click"],
        "finger_count": count,
        "zone": zone,
    }


def read_touchpad_coordinates(event_node: str) -> tuple[float, float, bool, bool]:
    """Legacy single-point signature compatibility."""
    data = read_touchpad_multi_touch(event_node)
    f1 = data["f1"]
    return f1["x"], f1["y"], (data["finger_count"] > 0), data["click"]


def cleanup_all_touchpad_grabs() -> None:
    """Release all touchpad grabs and close file descriptors on exit."""
    global TOUCHPAD_FDS, TOUCHPAD_GRABBED
    for node, fd in list(TOUCHPAD_FDS.items()):
        if fd > 0:
            try:
                fcntl.ioctl(fd, EVIOCGRAB, 0)
            except Exception:
                pass
            try:
                os.close(fd)
            except Exception:
                pass
    TOUCHPAD_FDS.clear()
    TOUCHPAD_GRABBED.clear()
