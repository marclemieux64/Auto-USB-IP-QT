from __future__ import annotations

import logging
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from config import load_config, save_config

logger = logging.getLogger("auto-usbip-client")

# Known audio-capable gamepads (Sony DualSense & DualShock 4 with Linux UAC audio support)
AUDIO_GAMEPAD_IDS = {
    "054c:0ce6",  # Sony DualSense (PS5)
    "054c:0df2",  # Sony DualSense Edge
    "054c:05c4",  # Sony DualShock 4 (v1)
    "054c:09cc",  # Sony DualShock 4 (v2)
    "054c:0ba0",  # Sony DualShock 4 Wireless USB Adapter
}

_CARDS_CACHE: tuple[float, list[dict]] = (0.0, [])


def _normalize_hex(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, int):
        return f"{val:04x}".lower()
    v = str(val).strip().strip('"\'').lower().replace("0x", "")
    return v.zfill(4)


def get_audio_cards(force_refresh: bool = False) -> list[dict]:
    """Query PulseAudio / PipeWire ALSA audio cards with short TTL caching to prevent subprocess churn."""
    global _CARDS_CACHE
    now = time.time()
    if not force_refresh and (now - _CARDS_CACHE[0]) < 1.5:
        return _CARDS_CACHE[1]

    cards: list[dict] = []
    try:
        p = subprocess.run(["pactl", "list", "cards"], capture_output=True, text=True, timeout=1.5)
        if p.returncode != 0:
            _CARDS_CACHE = (now, cards)
            return cards

        current_card: dict = {}
        for line in p.stdout.splitlines():
            line_str = line.strip()
            if line.startswith("Card #"):
                if current_card:
                    cards.append(current_card)
                current_card = {"id": line.split("#")[1].strip(), "profiles": []}
            elif line_str.startswith("Name: "):
                current_card["name"] = line_str.split("Name: ", 1)[1].strip()
            elif line_str.startswith("Active Profile: "):
                current_card["active_profile"] = line_str.split("Active Profile: ", 1)[1].strip()
            elif "device.vendor.id = " in line_str:
                raw = line_str.split("=", 1)[1].strip().strip('"\'').lower().replace("0x", "")
                current_card["vid"] = raw.zfill(4)
            elif "device.product.id = " in line_str:
                raw = line_str.split("=", 1)[1].strip().strip('"\'').lower().replace("0x", "")
                current_card["pid"] = raw.zfill(4)
            elif line_str.endswith("available: yes)") or line_str.endswith("available: no)"):
                prof_name = line_str.split(":", 1)[0].strip()
                if prof_name and prof_name not in current_card.get("profiles", []):
                    current_card.setdefault("profiles", []).append(prof_name)
        if current_card:
            cards.append(current_card)
    except Exception as e:
        logger.debug(f"Error querying pactl cards: {e}")

    _CARDS_CACHE = (now, cards)
    return cards


def is_audio_capable(vid: Any, pid: Any, desc: str = "") -> bool:
    if vid is None or pid is None:
        return False
    v_clean = _normalize_hex(vid)
    p_clean = _normalize_hex(pid)
    if not v_clean or not p_clean:
        return False

    dev_key = f"{v_clean}:{p_clean}"
    if dev_key in AUDIO_GAMEPAD_IDS:
        return True

    # 1. Check if PulseAudio / PipeWire registered an ALSA card for this exact VID:PID
    for card in get_audio_cards():
        if card.get("vid") == v_clean and card.get("pid") == p_clean:
            return True

    # 2. Check local sysfs for USB Audio Class interface (bInterfaceClass == 01)
    usb_dir = Path("/sys/bus/usb/devices")
    if usb_dir.exists():
        try:
            for dev in usb_dir.iterdir():
                v_file = dev / "idVendor"
                p_file = dev / "idProduct"
                if v_file.exists() and p_file.exists():
                    try:
                        v = v_file.read_text().strip().strip('"\'').lower().zfill(4)
                        p = p_file.read_text().strip().strip('"\'').lower().zfill(4)
                        if v == v_clean and p == p_clean:
                            for iface in dev.iterdir():
                                class_file = iface / "bInterfaceClass"
                                if class_file.exists():
                                    if class_file.read_text().strip().zfill(2) == "01":
                                        return True
                    except Exception:
                        pass
        except Exception:
            pass

    return False


def is_device_audio_enabled(vid: Any, pid: Any) -> bool:
    if vid is None or pid is None:
        return True
    v_clean = _normalize_hex(vid)
    p_clean = _normalize_hex(pid)
    if not v_clean or not p_clean:
        return True

    for card in get_audio_cards():
        if card.get("vid") == v_clean and card.get("pid") == p_clean:
            active_prof = card.get("active_profile", "off")
            return active_prof != "off" and active_prof != ""

    cfg = load_config()
    disabled_list = cfg.get("disabled_audio_devices", [])
    return f"{v_clean}:{p_clean}" not in disabled_list


def set_device_audio_state(vid: Any, pid: Any, enable: bool) -> bool:
    if vid is None or pid is None:
        return False
    v_clean = _normalize_hex(vid)
    p_clean = _normalize_hex(pid)
    if not v_clean or not p_clean:
        return False
    key = f"{v_clean}:{p_clean}"

    cfg = load_config()
    disabled_list = list(cfg.get("disabled_audio_devices", []))
    if not enable and key not in disabled_list:
        disabled_list.append(key)
    elif enable and key in disabled_list:
        disabled_list.remove(key)
    cfg["disabled_audio_devices"] = disabled_list
    save_config(cfg)

    success = False
    for card in get_audio_cards(force_refresh=True):
        if card.get("vid") == v_clean and card.get("pid") == p_clean:
            card_name = card.get("name") or card.get("id")
            if card_name:
                if enable:
                    profiles = card.get("profiles", [])
                    target_profile = "pro-audio"
                    for preferred in (
                        "Direct",
                        "Default (Mic, Speaker)",
                        "pro-audio",
                        "output:analog-stereo+input:analog-stereo",
                        "output:analog-stereo+input:analog-mono",
                        "output:analog-stereo",
                    ):
                        if preferred in profiles:
                            target_profile = preferred
                            break
                else:
                    target_profile = "off"

                cmd = ["pactl", "set-card-profile", str(card_name), target_profile]
                try:
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=2.0)
                    if res.returncode == 0:
                        success = True
                    elif enable:
                        subprocess.run(["pactl", "set-card-profile", str(card_name), "pro-audio"], capture_output=True)
                        success = True
                except Exception as e:
                    logger.warning(f"Failed to set audio profile: {e}")
    return success


def toggle_controller_audio(port: str, bus_id: str = "", desc: str = "", vid: str | None = None, pid: str | None = None) -> bool:
    """Toggle audio enabled/disabled for a USB device."""
    if not vid or not pid:
        raw_to_search = f"{desc} {bus_id}"
        m = re.search(r"([0-9a-fA-F]{4}):([0-9a-fA-F]{4})", raw_to_search)
        if m:
            vid, pid = m.group(1), m.group(2)
        else:
            return True

    cur_enabled = is_device_audio_enabled(vid, pid)
    new_enabled = not cur_enabled
    set_device_audio_state(vid, pid, new_enabled)
    return new_enabled


def apply_audio_policy_for_device(vid: str | None, pid: str | None):
    """Enforce user preference whenever a controller attaches."""
    if not vid or not pid:
        return
    v_clean = _normalize_hex(vid)
    p_clean = _normalize_hex(pid)
    key = f"{v_clean}:{p_clean}"
    cfg = load_config()
    disabled_list = cfg.get("disabled_audio_devices", [])
    if key in disabled_list:
        set_device_audio_state(vid, pid, False)