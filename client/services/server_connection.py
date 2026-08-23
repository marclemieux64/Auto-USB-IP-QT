from __future__ import annotations

import logging
import re
import socket
import time
from PyQt6.QtGui import QIcon
from serial.tools.list_ports_common import ListPortInfo

from config import PORT, SERVER_PING_CHECK
from core.usb_ids import get_device_icon_from_desc, resolve_usb_device_name
from core.gamepad import find_joystick_nodes_for_device

logger = logging.getLogger("auto-usbip-client")


class ImportedDevice:
    BLOCK_REGEX = re.compile(
        r"Port\s+([A-Za-z0-9.\-_]+):\s*<Port in Use>\s*at\s*([^\n]+)\n\s*([^\n]+)",
        re.MULTILINE,
    )
    VID_PID_REGEX = re.compile(r"\(([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\)")
    VID_PID_SUFFIX_REGEX = re.compile(r"\(([0-9a-fA-F]{4}:[0-9a-fA-F]{4})\)$")
    WHITESPACE_REGEX = re.compile(r"\s+")
    SPEED_REGEX = re.compile(r"\(([^)]+)\)")

    KNOWN_CONTROLLER_VIDS = {0x054C, 0x057E, 0x045E, 0x2DC8, 0x0E6F, 0x1532}
    STORAGE_KEYWORDS = (
        "storage", "flash", "drive", "disk", "usb mass",
        "media", "mass_storage", "sandisk", "kingston",
        "samsung", "transcend", "cruzer", "lexar"
    )

    def __init__(
        self, port: str, speed_raw: str, desc_raw: str, serial_connections: list[ListPortInfo]
    ) -> None:
        self.port = port.strip()
        self.speed_raw = speed_raw.strip()
        self.raw_desc = desc_raw.strip()
        self.desc = self.raw_desc
        self.speed: str | None = None
        self._vid: int | None = None
        self._pid: int | None = None
        self._bus_id: str = self.port

        vid_pid_match = self.VID_PID_REGEX.search(self.raw_desc)
        if vid_pid_match:
            vid_str, pid_str = vid_pid_match.groups()
            try:
                self._vid = int(vid_str, 16)
                self._pid = int(pid_str, 16)
                self.desc = resolve_usb_device_name(vid_str, pid_str, self.raw_desc)
            except ValueError:
                pass

        speed_match = self.SPEED_REGEX.search(self.speed_raw)
        self.speed = speed_match.group(1) if speed_match else self.speed_raw

        self._com_port = None
        if self.has_vid_pid:
            for conn in serial_connections:
                if conn.vid == self._vid and conn.pid == self._pid:
                    self._com_port = conn.device
                    break

    @property
    def identifier_key(self) -> str:
        if self._vid is not None and self._pid is not None:
            return f"{self._vid:04x}:{self._pid:04x}"
        return self.desc

    @property
    def is_controller(self) -> bool:
        nodes = find_joystick_nodes_for_device(self.port, is_vhci=True, vid=self._vid, pid=self._pid)
        if any("/js" in n for n in nodes):
            return True
        return self._vid in self.KNOWN_CONTROLLER_VIDS

    @property
    def is_storage(self) -> bool:
        desc_lower = self.desc.lower()
        return any(w in desc_lower for w in self.STORAGE_KEYWORDS)

    @property
    def bus_id(self) -> str:
        return self._bus_id

    @bus_id.setter
    def bus_id(self, val: str) -> None:
        self._bus_id = val

    @property
    def description(self) -> str:
        return self.desc

    @property
    def com_port(self) -> str | None:
        return self._com_port

    @property
    def has_vid_pid(self) -> bool:
        return self._vid is not None and self._pid is not None

    def get_icon(self) -> QIcon:
        return get_device_icon_from_desc(self.desc)

    def detach(self) -> None:
        from core.usbip import detach_port
        detach_port(str(self.port))
        logger.info(f"Detached device {self.desc}")

    def get_clean_name(self, nicknames: dict[str, str] | None = None) -> str:
        base_name = self.desc
        vid_pid_match = self.VID_PID_SUFFIX_REGEX.search(self.desc)
        if vid_pid_match:
            base_name = self.desc[: vid_pid_match.start()].strip()
        base_name = self.WHITESPACE_REGEX.sub(" ", base_name).strip()

        if nicknames:
            candidates = [
                self.identifier_key,
                self.identifier_key.lower(),
                self.identifier_key.upper(),
                self.desc,
                self.raw_desc,
                base_name,
                base_name.lower(),
                str(self.port),
                f"Port {self.port}",
            ]
            for k in candidates:
                if k and k in nicknames and nicknames[k]:
                    return str(nicknames[k]).strip()
        return base_name

    def get_display_name(
        self,
        show_port: bool = True,
        show_speed: bool = True,
        show_vid_pid: bool = True,
        enable_nicknames: bool = True,
        nicknames: dict[str, str] | None = None,
    ) -> str:
        base_name = self.desc
        vid_pid_str = ""
        vid_pid_match = self.VID_PID_SUFFIX_REGEX.search(self.desc)
        if vid_pid_match:
            vid_pid_str = f" ({vid_pid_match.group(1)})"
            base_name = self.desc[: vid_pid_match.start()].strip()

        if enable_nicknames and nicknames:
            clean_nick = self.get_clean_name(nicknames)
            if clean_nick:
                base_name = clean_nick

        parts = []
        if show_port:
            if self._com_port:
                parts.append(f"[{self._com_port}] Port {self.port}")
            else:
                parts.append(f"Port {self.port}")

        if show_speed and self.speed:
            parts.append(f"[{self.speed}]")

        prefix = " ".join(parts)
        if prefix:
            prefix += ": "

        suffix = vid_pid_str if show_vid_pid else ""
        return f"{prefix}{base_name}{suffix}"

    def __str__(self) -> str:
        return self.get_display_name()

    def connection(self) -> str:
        if self._com_port is not None:
            return self._com_port
        return f"Port {self.port}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ImportedDevice):
            return False
        if self.has_vid_pid and other.has_vid_pid:
            return self._vid == other._vid and self._pid == other._pid and self.port == other.port
        return self.port == other.port and self.desc == other.desc

    def __hash__(self) -> int:
        if self.has_vid_pid:
            return hash((self._vid, self._pid, self.port))
        return hash((self.desc, self.port))


class ServerConnection:
    def __init__(self, ip: str, port: int = PORT, enabled: bool = True, name: str = "", token: str = "", tls: bool = True) -> None:
        self.ip = ip.strip()
        self.port = int(port)
        self.enabled = enabled
        self.name = name.strip()
        self.token = token.strip()
        self.tls = tls
        self.auth_failed = getattr(self, "auth_failed", False)
        self.latency_ms: float | None = None
        self._ping_result: tuple[float, bool] = (0.0, False)

    def _ping(self, timeout: float = 0.2) -> bool:
        if not self.ip:
            self.latency_ms = None
            return False
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            s.settimeout(timeout)
            t0 = time.perf_counter()
            s.connect((self.ip, self.port))
            t1 = time.perf_counter()
            self.latency_ms = round((t1 - t0) * 1000.0, 1)
            s.close()
            return True
        except OSError:
            self.latency_ms = None
            return False

    @property
    def is_alive(self) -> bool:
        if not self.enabled:
            return False
        last_time, status = self._ping_result
        current_time = time.time()
        if current_time - last_time > SERVER_PING_CHECK:
            res = self._ping(timeout=0.2)
            self._ping_result = (current_time, res)
            return res
        return status

    def to_dict(self) -> dict:
        return {"ip": self.ip, "port": self.port, "enabled": self.enabled, "name": self.name, "token": self.token, "tls": self.tls, "auth_failed": bool(getattr(self, "auth_failed", False))}

    @classmethod
    def from_dict(cls, data: dict) -> ServerConnection:
        return cls(data.get("ip", ""), data.get("port", PORT), data.get("enabled", True), data.get("name", ""), data.get("token", ""), data.get("tls", True))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ServerConnection):
            return False
        return self.ip == other.ip and self.port == other.port

    def __hash__(self) -> int:
        return hash((self.ip, self.port))


class AvailableDevice:
    def __init__(self, server_ip: str, busid: str, description: str = "USB Device") -> None:
        self.server_ip = server_ip
        self.busid = busid
        self.bus_id = busid
        self.description = description