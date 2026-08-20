from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import QApplication

logger = logging.getLogger("auto-usbip-client")

USB_ID_REGEX = re.compile(r"^\s+([A-Za-z0-9.\-_]+)\:.*$")

PORT = 3240
POLLING_TIME = 2
PORT_KEEPALIVE_TIMEOUT = 5
SERVER_PING_CHECK = 5

def get_config_path() -> Path:
    import sys
    from core.resources import get_app_dir
    
    # 1. Portable Mode: Check if config.json or portable.flag exists in the app/exe directory
    app_dir = get_app_dir()
    portable_cfg = app_dir / "config.json"
    portable_flag = app_dir / "portable.flag"
    if portable_cfg.exists() or portable_flag.exists():
        return portable_cfg

    # 2. Standard OS Config Path
    if sys.platform == "win32":
        app_data = os.environ.get("APPDATA")
        base = Path(app_data) if app_data else Path.home() / "AppData" / "Roaming"
        return base / "auto-usbip" / "config.json"

    return Path.home() / ".config" / "auto-usbip" / "config.json"


CONFIG_PATH = get_config_path()


def get_default_config() -> dict:
    return {
        "show_notifications": True,
        "play_sound_cues": True,
        "polling_interval": POLLING_TIME,
        "auto_attach": False,
        "power_cycle_on_attach": True,
        "remember_detached": True,
        "enable_nicknames": True,
        "enable_wol_wake": False,
        "client_mac": "",
        "show_port": False,
        "show_speed": False,
        "show_vid_pid": False,
        "show_battery": True,
        "show_latency": False,
        "auto_discover": True,
        "allow_lan_access": True,
        "enable_web_csrf": False,
        "enable_tls_pinning": False,
        "pinned_certificates": {},
        "enable_device_class_filter": False,
        "block_mass_storage": False,
        "block_network_devices": False,
        "block_hid_keyboards": False,
        "servers": [],
        "nicknames": {},
        "blacklisted_devices": [],
        "ignored_devices": {},
    }


def load_config() -> dict:
    default_config = get_default_config()
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_config.update(data)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
    return default_config



def save_config(config_data: dict) -> None:
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save configuration: {e}")


def play_sound_cue(event_name: str) -> None:
    cfg = load_config()
    if not cfg.get("play_sound_cues", True):
        return

    sound_files = [
        f"/usr/share/sounds/freedesktop/stereo/{event_name}.oga",
        f"/usr/share/sounds/ocean/stereo/{event_name}.oga",
        f"/usr/share/sounds/oxygen/stereo/{event_name}.ogg",
    ]

    target_file = None
    for path in sound_files:
        if os.path.exists(path):
            target_file = path
            break

    if target_file:
        for player in ("pw-play", "paplay", "canberra-gtk-play"):
            try:
                if player == "canberra-gtk-play":
                    subprocess.Popen([player, "-i", event_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    subprocess.Popen([player, target_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except FileNotFoundError:
                continue
            except Exception:
                pass

    QApplication.beep()


class ClientConfig:
    def __init__(self):
        self.load()

    def load(self):
        cfg = load_config()
        self.show_notifications = cfg.get("show_notifications", True)
        self.play_sound_cues = cfg.get("play_sound_cues", True)
        self.polling_interval = cfg.get("polling_interval", POLLING_TIME)
        self.auto_attach = cfg.get("auto_attach", False)
        self.remember_detached_devices = cfg.get("remember_detached", True)
        self.enable_nicknames = cfg.get("enable_nicknames", True)
        self.enable_wol_wake = cfg.get("enable_wol_wake", False)
        self.client_mac = cfg.get("client_mac", "")
        self.show_port = cfg.get("show_port", False)
        self.show_speed = cfg.get("show_speed", False)
        self.show_vid_pid = cfg.get("show_vid_pid", False)
        self.show_battery = cfg.get("show_battery", True)
        self.show_latency = cfg.get("show_latency", False)
        self.auto_discover = cfg.get("auto_discover", True)
        self.allow_lan_access = cfg.get("allow_lan_access", True)
        self.power_cycle_on_attach = cfg.get("power_cycle_on_attach", True)
        self.enable_web_csrf = cfg.get("enable_web_csrf", False)
        self.enable_tls_pinning = cfg.get("enable_tls_pinning", False)
        self.pinned_certificates = cfg.get("pinned_certificates", {})
        self.enable_device_class_filter = cfg.get("enable_device_class_filter", False)
        self.block_mass_storage = cfg.get("block_mass_storage", False)
        self.block_network_devices = cfg.get("block_network_devices", False)
        self.block_hid_keyboards = cfg.get("block_hid_keyboards", False)
        self.blacklist = cfg.get("blacklisted_devices", [])
        self.nicknames = cfg.get("nicknames", {})

    def save(self):
        cfg = {
            "show_notifications": self.show_notifications,
            "play_sound_cues": self.play_sound_cues,
            "polling_interval": self.polling_interval,
            "auto_attach": self.auto_attach,
            "remember_detached": self.remember_detached_devices,
            "enable_nicknames": self.enable_nicknames,
            "enable_wol_wake": self.enable_wol_wake,
            "client_mac": self.client_mac,
            "show_port": self.show_port,
            "show_speed": self.show_speed,
            "show_vid_pid": self.show_vid_pid,
            "show_battery": self.show_battery,
            "show_latency": self.show_latency,
            "auto_discover": self.auto_discover,
            "allow_lan_access": getattr(self, "allow_lan_access", True),
            "power_cycle_on_attach": getattr(self, "power_cycle_on_attach", True),
            "enable_web_csrf": getattr(self, "enable_web_csrf", False),
            "enable_tls_pinning": getattr(self, "enable_tls_pinning", False),
            "pinned_certificates": getattr(self, "pinned_certificates", {}),
            "enable_device_class_filter": getattr(self, "enable_device_class_filter", False),
            "block_mass_storage": getattr(self, "block_mass_storage", False),
            "block_network_devices": getattr(self, "block_network_devices", False),
            "block_hid_keyboards": getattr(self, "block_hid_keyboards", False),
            "blacklisted_devices": self.blacklist,
            "nicknames": self.nicknames,
        }
        old = load_config()
        old.update(cfg)
        save_config(old)
