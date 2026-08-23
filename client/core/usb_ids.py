from __future__ import annotations

import os
import re
import subprocess
from functools import lru_cache
from pathlib import Path
try:
    from PyQt6.QtGui import QIcon
except ImportError:
    QIcon = None

USB_IDS_PATHS = [
    "/usr/share/hwdata/usb.ids",
    "/var/lib/usbutils/usb.ids",
    "/usr/share/misc/usb.ids",
]

RESOLVED_NAMES_CACHE: dict[str, str] = {}


def get_device_icon_from_desc(desc: str):
    if QIcon is None:
        return None
    desc_lower = desc.lower()
    if any(w in desc_lower for w in ("controller", "gamepad", "joystick", "xbox", "playstation", "nintendo", "steam", "dualshock", "dualsense", "pad", "8bitdo")):
        return QIcon.fromTheme("preferences-desktop-gaming", QIcon.fromTheme("games-config"))
    if any(w in desc_lower for w in ("keyboard", "keypad")):
        return QIcon.fromTheme("input-keyboard")
    if any(w in desc_lower for w in ("mouse", "trackball", "touchpad")):
        return QIcon.fromTheme("input-mouse")
    if any(w in desc_lower for w in ("storage", "flash", "drive", "disk", "usb mass")):
        return QIcon.fromTheme("drive-removable-media")
    if any(w in desc_lower for w in ("audio", "headset", "headphone", "sound", "dac", "mic", "microphone", "speaker")):
        return QIcon.fromTheme("audio-card")
    if any(w in desc_lower for w in ("camera", "webcam", "video")):
        return QIcon.fromTheme("camera-web")
    if any(w in desc_lower for w in ("bluetooth", "bt adapter", "dongle")):
        return QIcon.fromTheme("preferences-system-bluetooth")
    return QIcon.fromTheme("system-run", QIcon.fromTheme("preferences-other"))


@lru_cache(maxsize=1)
def load_usb_ids_file() -> dict[str, tuple[str, dict[str, str]]]:
    db_path = None
    for path in USB_IDS_PATHS:
        if os.path.isfile(path):
            db_path = path
            break

    if not db_path:
        return {}

    database: dict[str, tuple[str, dict[str, str]]] = {}
    current_vendor_id: str | None = None
    current_vendor_name: str | None = None
    current_products: dict[str, str] = {}

    try:
        with open(db_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if not line or line.startswith("#"):
                    continue

                if not line.startswith("\t"):
                    parts = line.strip().split(maxsplit=1)
                    if len(parts) == 2 and len(parts[0]) == 4:
                        if current_vendor_id:
                            database[current_vendor_id] = (
                                current_vendor_name or "",
                                current_products,
                            )
                        current_vendor_id = parts[0].lower()
                        current_vendor_name = parts[1]
                        current_products = {}
                elif line.startswith("\t") and not line.startswith("\t\t"):
                    parts = line.strip().split(maxsplit=1)
                    if len(parts) == 2 and len(parts[0]) == 4:
                        current_products[parts[0].lower()] = parts[1]

            if current_vendor_id:
                database[current_vendor_id] = (
                    current_vendor_name or "",
                    current_products,
                )
    except Exception:
        pass

    return database


def get_lsusb_device_name(vid_hex: str, pid_hex: str) -> str | None:
    try:
        res = subprocess.run(
            ["lsusb", "-d", f"{vid_hex}:{pid_hex}"],
            capture_output=True,
            text=True,
            timeout=1.0,
        )
        if res.returncode == 0 and res.stdout.strip():
            first_line = res.stdout.strip().splitlines()[0]
            m = re.search(r"ID\s+[0-9a-fA-F]{4}:[0-9a-fA-F]{4}\s+(.*)$", first_line)
            if m:
                name = m.group(1).strip()
                if name and "unknown" not in name.lower():
                    return name
    except Exception:
        pass
    return None


def get_sysfs_usb_name(bus_id: str) -> str | None:
    try:
        sys_path = Path(f"/sys/bus/usb/devices/{bus_id}")
        if not sys_path.exists():
            for p in Path("/sys/bus/usb/devices").glob(f"*{bus_id}*"):
                if p.is_dir():
                    sys_path = p
                    break

        prod_file = sys_path / "product"
        mfg_file = sys_path / "manufacturer"

        prod = prod_file.read_text().strip() if prod_file.exists() else ""
        mfg = mfg_file.read_text().strip() if mfg_file.exists() else ""

        if prod and mfg and mfg.lower() not in prod.lower():
            return f"{mfg} {prod}"
        elif prod:
            return prod
        elif mfg:
            return mfg
    except Exception:
        pass
    return None


def resolve_usb_device_name(vid_hex: str, pid_hex: str, fallback_desc: str = "", bus_id: str | None = None) -> str:
    vid_clean = vid_hex.lower().replace("0x", "").zfill(4)
    pid_clean = pid_hex.lower().replace("0x", "").zfill(4)
    key = f"{vid_clean}:{pid_clean}"

    # 0. Priority 1: Check SDL_GameControllerDB for friendly game controller name
    try:
        from core.gamepad import lookup_sdl_gamepad_mapping
        v_int = int(vid_clean, 16)
        p_int = int(pid_clean, 16)
        sdl_m = lookup_sdl_gamepad_mapping(vid=v_int, pid=p_int, dev_name=fallback_desc)
        if sdl_m and getattr(sdl_m, "combined_name", sdl_m.name):
            comb = getattr(sdl_m, "combined_name", sdl_m.name)
            RESOLVED_NAMES_CACHE[key] = comb
            return comb
    except Exception:
        pass

    # 1. Check local lsusb for exact hardware description
    lsusb_name = get_lsusb_device_name(vid_clean, pid_clean)
    if lsusb_name:
        resolved = re.sub(r"\s*\([0-9a-fA-F]{4}:[0-9a-fA-F]{4}\)$", "", lsusb_name).strip()
        RESOLVED_NAMES_CACHE[key] = resolved
        return resolved

    # 2. Check cache if clean name is stored
    if key in RESOLVED_NAMES_CACHE and not RESOLVED_NAMES_CACHE[key].startswith("USB Device"):
        cached = RESOLVED_NAMES_CACHE[key]
        if len(cached.split()) > 1:
            return cached

    # 3. Dynamically read hardware ROM descriptors from sysfs if bus_id is present
    if bus_id:
        sysfs_name = get_sysfs_usb_name(bus_id)
        if sysfs_name and "unknown" not in sysfs_name.lower():
            resolved = re.sub(r"\s*\([0-9a-fA-F]{4}:[0-9a-fA-F]{4}\)$", "", sysfs_name).strip()
            RESOLVED_NAMES_CACHE[key] = resolved
            return resolved

    # 4. Clean fallback description string
    clean_fallback = fallback_desc.strip()
    if clean_fallback:
        clean_fallback = re.sub(r":\s*unknown\s*product", "", clean_fallback, flags=re.IGNORECASE).strip()
        clean_fallback = re.sub(r"\s*\([0-9a-fA-F]{4}:[0-9a-fA-F]{4}\)$", "", clean_fallback).strip()

    if clean_fallback and "unknown" not in clean_fallback.lower() and not clean_fallback.startswith("USB Device") and len(clean_fallback.split()) > 1:
        RESOLVED_NAMES_CACHE[key] = clean_fallback
        return clean_fallback

    # 5. Query system /usr/share/hwdata/usb.ids database
    db = load_usb_ids_file()
    if vid_clean in db:
        vendor_name, products = db[vid_clean]
        if pid_clean in products:
            resolved = f"{vendor_name} {products[pid_clean]}".strip()
            RESOLVED_NAMES_CACHE[key] = resolved
            return resolved
        elif vendor_name:
            if clean_fallback and "unknown" not in clean_fallback.lower() and len(clean_fallback.split()) > 1:
                RESOLVED_NAMES_CACHE[key] = clean_fallback
                return clean_fallback
            else:
                return vendor_name

    if clean_fallback:
        return clean_fallback

    return "USB Device"


class UsbIdsDatabase:
    def get_device_name(self, busid: str, desc: str) -> str:
        if not desc:
            return "USB Device"
        m = re.search(r"\(([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\)", desc)
        if m:
            return resolve_usb_device_name(m.group(1), m.group(2), fallback_desc=desc, bus_id=busid)
        
        clean = desc.strip()
        clean = re.sub(r":\s*unknown\s*product", "", clean, flags=re.IGNORECASE).strip()
        clean = re.sub(r"\s*\([0-9a-fA-F]{4}:[0-9a-fA-F]{4}\)$", "", clean).strip()
        return clean or "USB Device"

    def get_device_icon_name(self, busid: str, desc: str) -> str:
        d_lower = desc.lower()
        if any(w in d_lower for w in ("controller", "gamepad", "joystick", "xbox", "playstation", "nintendo", "steam", "dualshock", "dualsense", "pad", "8bitdo")):
            return "gamepad"
        if any(w in d_lower for w in ("keyboard", "keypad")):
            return "input-keyboard"
        if any(w in d_lower for w in ("mouse", "trackball", "touchpad")):
            return "input-mouse"
        if any(w in d_lower for w in ("camera", "webcam", "video")):
            return "camera-web"
        if any(w in d_lower for w in ("storage", "flash", "drive", "disk", "usb mass")):
            return "storage"
        if any(w in d_lower for w in ("audio", "headset", "headphone", "sound", "dac", "mic", "microphone", "speaker")):
            return "audio-card"
        return "generic-usb"

    def is_gamepad_device(self, busid: str, desc: str) -> bool:
        d_lower = desc.lower()
        return any(w in d_lower for w in ("controller", "gamepad", "joystick", "xbox", "playstation", "nintendo", "steam", "dualshock", "dualsense", "pad", "8bitdo"))

    def is_storage_device(self, busid: str, desc: str) -> bool:
        d_lower = desc.lower()
        return any(w in d_lower for w in ("storage", "flash", "drive", "disk", "usb mass"))

    def is_audio_device(self, busid: str, desc: str) -> bool:
        vid, pid = self.parse_vid_pid_from_string(desc)
        if vid != 0 and pid != 0:
            from core.audio_control import AUDIO_GAMEPAD_IDS, is_audio_capable
            v_key = f"{vid:04x}:{pid:04x}".lower()
            if v_key in AUDIO_GAMEPAD_IDS:
                return True
            if is_audio_capable(vid, pid, desc):
                return True
            d_lower = desc.lower()
            if any(w in d_lower for w in ("controller", "gamepad", "joystick", "xbox", "nintendo", "nes", "snes", "pad")):
                return False
        d_lower = desc.lower()
        if any(w in d_lower for w in ("controller", "gamepad", "joystick", "xbox", "nintendo", "nes", "snes")):
            return False
        return any(w in d_lower for w in ("audio", "headset", "headphone", "sound", "dac", "mic", "microphone", "speaker"))

    def is_isochronous_or_high_bandwidth(self, busid: str, desc: str) -> bool:
        """Detect if device requires isochronous / high continuous bandwidth (e.g. webcams, capture cards, high-speed audio)."""
        d_lower = (desc or "").lower()
        if any(w in d_lower for w in ("camera", "webcam", "video", "cam", "uvc", "capture", "hdmi", "elgato", "cam link", "broadcast")):
            return True
        if any(w in d_lower for w in ("focusrite", "scarlett", "motu", "behringer", "rme", "soundcard", "audio interface", "multichannel", "quad-capture", "duo-capture")):
            return True
        return False

    def is_compound_hub_child(self, busid: str) -> bool:
        """Check if bus ID represents a device attached to an internal or multi-tier hub (e.g. 1-1.2, 1-1.3.1)."""
        if not busid:
            return False
        # Bus IDs with multiple hierarchy dots like '1-1.2' or '1-1.4.1' are connected through intermediate hubs
        return busid.count(".") >= 1

    def parse_vid_pid_from_string(self, desc: str) -> tuple[int, int]:
        m = re.search(r"\(([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\)", desc)
        if m:
            return int(m.group(1), 16), int(m.group(2), 16)
        return 0, 0
