from __future__ import annotations

import fcntl
import logging
import os
import struct
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any

logger = logging.getLogger("auto-usbip-client")

# Dynamically resolve struct input_event format (16 bytes on 32-bit, 24 bytes on 64-bit)
# 64-bit: 8B sec, 8B usec, 2B type, 2B code, 4B value = 24B ("qqHHi")
# 32-bit: 4B sec, 4B usec, 2B type, 2B code, 4B value = 16B ("llHHi")
if struct.calcsize("P") == 8:
    EVENT_FORMAT = "qqHHi"
else:
    EVENT_FORMAT = "llHHi"

EVENT_SIZE = struct.calcsize(EVENT_FORMAT)


class ControllerLatencyTracker:
    """
    High-precision, non-blocking controller polling latency and frequency monitor.
    Samples Linux evdev input event timestamps to measure real-time inter-packet
    arrival interval (latency in ms) and polling rate (Hz) over USB/IP tunnels.
    """

    def __init__(self):
        # map: event_node -> { 'fd': int, 'last_syn_t': float, 'samples': deque, 'nominal_ms': float, 'last_seen': float }
        self._nodes: dict[str, dict[str, Any]] = {}
        self._port_to_node: dict[str, str] = {}

    def get_latency_for_port(self, port: str, vid: int | None = None, pid: int | None = None) -> dict[str, Any]:
        """Resolve event node for port and sample instant polling latency."""
        node = self._port_to_node.get(port)
        if not node or not os.path.exists(node):
            # Clean up old node if it changed
            if node and node in self._nodes:
                self._close_node(node)

            node = self._find_best_event_node(port, vid, pid)
            if node:
                self._port_to_node[port] = node

        if not node:
            return {"latency_ms": None, "polling_hz": None, "latency_str": None, "is_active": False}

        return self.sample_node(node)

    def sample_node(self, event_node: str) -> dict[str, Any]:
        """Read pending input events non-blockingly and update polling rate statistics."""
        if not event_node or not os.path.exists(event_node):
            self._close_node(event_node)
            return {"latency_ms": None, "polling_hz": None, "latency_str": None, "is_active": False}

        if event_node not in self._nodes:
            try:
                fd = os.open(event_node, os.O_RDONLY | os.O_NONBLOCK)
                nominal = self._detect_usb_nominal_interval(event_node)
                self._nodes[event_node] = {
                    "fd": fd,
                    "last_syn_t": None,
                    "samples": deque(maxlen=64),
                    "nominal_ms": nominal,
                    "last_seen": 0.0,
                }
            except Exception as e:
                logger.debug(f"Could not open evdev node {event_node} for latency tracking: {e}")
                return {"latency_ms": None, "polling_hz": None, "latency_str": None, "is_active": False}

        info = self._nodes[event_node]
        fd = info["fd"]

        try:
            # Drain non-blocking evdev buffer (reads up to 32 events per iteration)
            while True:
                data = os.read(fd, EVENT_SIZE * 32)
                if not data:
                    break
                for i in range(0, len(data), EVENT_SIZE):
                    chunk = data[i : i + EVENT_SIZE]
                    if len(chunk) < EVENT_SIZE:
                        continue
                    tv_sec, tv_usec, ev_type, ev_code, ev_val = struct.unpack(EVENT_FORMAT, chunk)
                    # Filter for EV_SYN / SYN_REPORT which marks a complete hardware HID packet
                    if ev_type == 0 and ev_code == 0:
                        t = tv_sec + (tv_usec / 1_000_000.0)
                        if info["last_syn_t"] is not None:
                            dt_ms = (t - info["last_syn_t"]) * 1000.0
                            # Hardware interval filter: between 0.2ms (1000Hz+ USB) and 40.0ms (25Hz)
                            if 0.2 <= dt_ms <= 40.0:
                                info["samples"].append(dt_ms)
                                info["last_seen"] = time.monotonic()
                        info["last_syn_t"] = t
        except (BlockingIOError, InterruptedError):
            pass
        except Exception as e:
            logger.debug(f"Error reading evdev node {event_node}: {e}")
            self._close_node(event_node)
            return {"latency_ms": None, "polling_hz": None, "latency_str": None, "is_active": False}

        now = time.monotonic()
        samples = list(info["samples"])
        
        # Calculate active stream polling rate
        if samples and (now - info["last_seen"]) < 3.0:
            samples.sort()
            # Use 25th percentile (fastest quarter of packets) to isolate true polling rate from input release delays
            idx = max(0, int(len(samples) * 0.25))
            lat_ms = samples[idx]
            is_active = True
        else:
            lat_ms = info["nominal_ms"] or 4.0
            is_active = False

        lat_rounded = round(lat_ms, 1)
        hz = int(round(1000.0 / lat_ms)) if lat_ms > 0 else 0
        lat_str = f"{lat_rounded} ms ({hz} Hz)"
        return {
            "latency_ms": lat_rounded,
            "polling_hz": hz,
            "latency_str": lat_str,
            "is_active": is_active,
        }

    def _find_best_event_node(self, port: str, vid: int | None = None, pid: int | None = None) -> str | None:
        """Find the optimal event node for sampling latency (prioritizing continuous motion/sensor packets)."""
        try:
            from core.gamepad.reader import find_joystick_nodes_for_device
            nodes = find_joystick_nodes_for_device(port, is_vhci=True, vid=vid, pid=pid)
        except ImportError:
            import glob
            nodes = glob.glob("/dev/input/event*")

        ev_nodes = [n for n in nodes if "/event" in n]
        if not ev_nodes:
            return None

        motion_node = None
        primary_node = None
        for ev in ev_nodes:
            try:
                sys_name_file = Path(f"/sys/class/input/{os.path.basename(ev)}/device/name")
                if sys_name_file.exists():
                    n_lower = sys_name_file.read_text().strip().lower()
                    if "motion" in n_lower or "sensors" in n_lower:
                        motion_node = ev
                    elif not any(k in n_lower for k in ("touchpad", "headset", "audio")):
                        primary_node = ev
            except Exception:
                pass

        return motion_node or primary_node or ev_nodes[0]

    def _detect_usb_nominal_interval(self, event_node: str) -> float | None:
        """Inspect sysfs endpoint bInterval to obtain hardware nominal interval."""
        try:
            ev_name = os.path.basename(event_node)
            p = Path(f"/sys/class/input/{ev_name}/device").resolve()
            for _ in range(8):
                if p == Path("/") or not p.exists():
                    break
                for ep in p.glob("**/bInterval"):
                    try:
                        raw = ep.read_text().strip()
                        val = int(raw, 16) if (raw.startswith("0x") or any(c in raw for c in "abcdefABCDEF")) else int(raw)
                        if val > 0:
                            if val <= 6:
                                return float(max(1.0, round(2 ** (val - 1) * 0.125, 2)))
                            return float(val)
                    except Exception:
                        pass
                p = p.parent
        except Exception:
            pass
        return 4.0

    def _close_node(self, event_node: str):
        info = self._nodes.pop(event_node, None)
        if info and "fd" in info:
            try:
                os.close(info["fd"])
            except Exception:
                pass

    def cleanup(self):
        """Close all open file descriptors."""
        for node in list(self._nodes.keys()):
            self._close_node(node)
        self._port_to_node.clear()


# Global Singleton Instance
_GLOBAL_LATENCY_TRACKER = ControllerLatencyTracker()


def get_controller_latency_tracker() -> ControllerLatencyTracker:
    return _GLOBAL_LATENCY_TRACKER


def get_controller_latency(port: str, vid: int | None = None, pid: int | None = None) -> dict[str, Any]:
    return _GLOBAL_LATENCY_TRACKER.get_latency_for_port(port, vid, pid)