from __future__ import annotations

import socket

def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

import json
import logging
import os
import sys
import threading
import time
from typing import Any

logger = logging.getLogger("auto-usbip-client")


def handle_status(controller: Any) -> dict:
    """Return JSON representation of the entire client state."""
    servers_data = []
    for s in controller.servers:
        servers_data.append({
            "ip": s.ip,
            "port": s.port,
            "name": s.name,
            "token": s.token,
            "enabled": s.enabled,
            "is_alive": s.is_alive,
            "latency_ms": getattr(s, "latency_ms", None),
            "tls": getattr(s, "tls", True),
        })

    attached_data = []
    from core.usbip import get_port_to_bus_map, get_locally_attached_vid_pids
    port_map = get_port_to_bus_map()

    enabled_ips = {s.ip.strip().lower() for s in controller.servers if s.enabled}
    imported_list = controller.scanner.imported_devices if enabled_ips else []

    for d in imported_list:
        desc_str = getattr(d, "desc", getattr(d, "description", "USB Device"))
        raw_desc_str = getattr(d, "raw_desc", desc_str)
        port_str = getattr(d, "port", "")
        s_ip, b_id = port_map.get(port_str, ("", getattr(d, "bus_id", "")))
        bus_id_str = b_id or getattr(d, "bus_id", port_str)

        clean_name = controller.usb_db.get_device_name(bus_id_str, desc_str)
        icon_alias = controller.usb_db.get_device_icon_name(bus_id_str, desc_str)
        is_ctrl = getattr(d, "is_controller", False) or controller.usb_db.is_gamepad_device(bus_id_str, desc_str)
        is_stor = controller.usb_db.is_storage_device(bus_id_str, desc_str)
        vid, pid = controller.usb_db.parse_vid_pid_from_string(raw_desc_str or desc_str)
        has_aud = controller.usb_db.is_audio_device(bus_id_str, raw_desc_str or desc_str)
        has_vp = (vid != 0 and pid != 0)
        id_key = f"{vid:04x}:{pid:04x}" if has_vp else port_str
        if controller.config.enable_nicknames and id_key in controller.config.nicknames:
            clean_name = controller.config.nicknames[id_key]

        bat_desc = None
        lat_desc = None
        lat_ms = None
        poll_hz = None
        has_tp = False
        tp_mouse_enabled = True
        if is_ctrl:
            from core.gamepad import get_gamepad_battery_info, get_controller_latency, lookup_sdl_gamepad_mapping
            from core.audio_control import is_device_audio_enabled
            sdl_m = lookup_sdl_gamepad_mapping(vid=vid if has_vp else None, pid=pid if has_vp else None, dev_name=desc_str or clean_name)
            if sdl_m and getattr(sdl_m, "combined_name", sdl_m.name):
                clean_name = getattr(sdl_m, "combined_name", sdl_m.name)
            b_info = get_gamepad_battery_info(vid if has_vp else None, pid if has_vp else None)
            if b_info:
                bat_desc = b_info[1]
            lat_info = get_controller_latency(port_str, vid if has_vp else None, pid if has_vp else None)
            lat_desc = lat_info.get("latency_str")
            lat_ms = lat_info.get("latency_ms")
            poll_hz = lat_info.get("polling_hz")

            d_lower = (desc_str + " " + raw_desc_str + " " + clean_name).lower()
            if vid == 0x054C or "dualsense" in d_lower or "ps5" in d_lower or "ps4" in d_lower or "dualshock" in d_lower:
                has_tp = True
                from core.touchpad_control import is_touchpad_mouse_enabled
                tp_mouse_enabled = is_touchpad_mouse_enabled(port_str)

        attached_data.append({
            "port": port_str,
            "desc": clean_name if controller.config.enable_nicknames else desc_str,
            "raw_desc": raw_desc_str,
            "clean_name": clean_name,
            "speed": getattr(d, "speed", ""),
            "vid_pid": f"{vid:04x}:{pid:04x}" if has_vp else "",
            "identifier_key": id_key,
            "is_controller": is_ctrl,
            "is_storage": is_stor,
            "has_audio": has_aud,
            "audio_enabled": (is_device_audio_enabled(f"{vid:04x}", f"{pid:04x}") if has_vp else getattr(d, "audio_enabled", True)),
            "has_touchpad": has_tp,
            "touchpad_mouse_enabled": tp_mouse_enabled,
            "battery": bat_desc,
            "latency_ms": lat_ms,
            "latency_str": lat_desc,
            "polling_hz": poll_hz,
            "server_ip": s_ip,
            "bus_id": b_id,
            "icon_alias": icon_alias,
        })

    # Collect currently attached hardware identifiers to prevent duplicates in available list
    attached_bus_keys = set()
    from core.usbip import get_port_to_bus_map, get_locally_attached_vid_pids
    port_map = get_port_to_bus_map()
    for p, (s_ip, b_id) in port_map.items():
        attached_bus_keys.add((s_ip.strip().lower(), b_id.strip()))
        attached_bus_keys.add(b_id.strip())

    attached_vids_pids = set(get_locally_attached_vid_pids())
    for d in controller.scanner.imported_devices:
        raw_desc = getattr(d, "raw_desc", getattr(d, "desc", ""))
        v, p_id = controller.usb_db.parse_vid_pid_from_string(raw_desc)
        if v != 0 and p_id != 0:
            attached_vids_pids.add(f"{v:04x}:{p_id:04x}".lower())

    configured_enabled_ips = {s.ip.strip().lower() for s in controller.servers if s.ip and s.enabled}
    available_data = []
    for d in controller.scanner.available_devices:
        desc_str = getattr(d, "desc", getattr(d, "description", "USB Device"))
        bus_id_str = getattr(d, "bus_id", getattr(d, "busid", ""))
        server_ip_str = getattr(d, "server_ip", "")

        # Only display available devices from servers the user has explicitly added and enabled!
        if server_ip_str and server_ip_str.strip().lower() not in configured_enabled_ips:
            continue

        vid, pid = controller.usb_db.parse_vid_pid_from_string(desc_str)
        has_vp = (vid != 0 and pid != 0)
        vp_key = f"{vid:04x}:{pid:04x}".lower() if has_vp else ""

        # Filter out any device that is ALREADY attached on this client!
        if (server_ip_str.strip().lower(), bus_id_str.strip()) in attached_bus_keys or bus_id_str.strip() in attached_bus_keys:
            continue
        if has_vp and vp_key in attached_vids_pids:
            continue

        clean_name = controller.usb_db.get_device_name(bus_id_str, desc_str)
        icon_alias = controller.usb_db.get_device_icon_name(bus_id_str, desc_str)
        is_ctrl = controller.usb_db.is_gamepad_device(bus_id_str, desc_str)
        is_stor = controller.usb_db.is_storage_device(bus_id_str, desc_str)
        has_aud = controller.usb_db.is_audio_device(bus_id_str, desc_str)

        vid, pid = controller.usb_db.parse_vid_pid_from_string(desc_str)
        has_vp = (vid != 0 and pid != 0)
        id_key = f"{vid:04x}:{pid:04x}" if has_vp else bus_id_str
        if controller.config.enable_nicknames and id_key in controller.config.nicknames:
            clean_name = controller.config.nicknames[id_key]

        available_data.append({
            "server_ip": server_ip_str,
            "bus_id": bus_id_str,
            "desc": clean_name if controller.config.enable_nicknames else desc_str,
            "clean_name": clean_name,
            "vid_pid": f"{vid:04x}:{pid:04x}" if has_vp else "",
            "identifier_key": id_key,
            "is_controller": is_ctrl,
            "is_storage": is_stor,
            "has_audio": has_aud,
            "icon_alias": icon_alias,
        })

    # Filter out servers that are ALREADY in the configured servers list
    configured_ips = {s.ip.strip().lower() for s in controller.servers if s.ip}
    configured_names = {s.name.strip().lower() for s in controller.servers if s.name}

    discovered_data = []
    for d in getattr(controller, "discovered_servers", []):
        d_ip = d.get("ip", "").strip().lower()
        d_name = d.get("name", "").strip().lower()
        if d_ip in configured_ips or (d_name and (d_name in configured_ips or d_name in configured_names)):
            continue
        
        auth_req = bool(d.get("auth_required", False))
        if not auth_req and d.get("ip"):
            try:
                from core.server_control import ServerControlClient
                probe = ServerControlClient(d.get("ip", ""), port=3241, token="", timeout=0.3, use_tls=True).get_devices()
                if probe and probe.get("status") == "error" and "Unauthorized" in probe.get("message", ""):
                    auth_req = True
                    d["auth_required"] = True
            except Exception:
                pass

        discovered_data.append({
            "name": d.get("name", ""),
            "ip": d.get("ip", ""),
            "port": d.get("port", 3240),
            "auth_required": auth_req,
        })

    cfg_dict = {
        "auto_attach": controller.config.auto_attach,
        "remember_detached_devices": controller.config.remember_detached_devices,
        "show_notifications": controller.config.show_notifications,
        "auto_discover": controller.config.auto_discover,
        "enable_nicknames": controller.config.enable_nicknames,
        "enable_wol_wake": getattr(controller.config, "enable_wol_wake", False),
        "client_mac": getattr(controller.config, "client_mac", ""),
        "polling_interval": getattr(controller.config, "polling_interval", 1.0),
        "show_port": controller.config.show_port,
        "show_speed": controller.config.show_speed,
        "show_vid_pid": controller.config.show_vid_pid,
        "show_battery": controller.config.show_battery,
        "show_latency": controller.config.show_latency,
        "show_server_temp": getattr(controller.config, "show_server_temp", True),
        "show_server_ram": getattr(controller.config, "show_server_ram", True),
        "show_server_uptime": getattr(controller.config, "show_server_uptime", True),
        "enable_web_ui": getattr(controller.config, "enable_web_ui", True),
        "allow_lan_access": getattr(controller.config, "allow_lan_access", True),
        "play_sound_cues": getattr(controller.config, "play_sound_cues", True),
        "power_cycle_on_attach": getattr(controller.config, "power_cycle_on_attach", True),
        "nicknames": controller.config.nicknames,
    }

    return {
        "status": "ok",
        "local_ip": get_local_ip(),
        "web_port": 3242,
        "servers": servers_data,
        "attached_devices": attached_data,
        "available_devices": available_data,
        "discovered_servers": discovered_data,
        "blacklisted_devices": [
            {
                "identifier": item.get("identifier", ""),
                "name": item.get("name", item.get("identifier", "")),
                "vid_pid": item.get("vid_pid", ""),
                "bus_id": item.get("bus_id", ""),
                "icon_alias": item.get("icon_alias") or (controller.usb_db.get_device_icon_name(item.get("bus_id", ""), item.get("name", "")) if hasattr(controller, "usb_db") else "generic-usb"),
                "is_controller": item.get("is_controller", False) or ("gamepad" in str(item.get("icon_alias", "")) or "controller" in str(item.get("name", "")).lower() or "dualsense" in str(item.get("name", "")).lower())
            } if isinstance(item, dict) else {
                "identifier": str(item),
                "name": str(item),
                "vid_pid": "",
                "bus_id": "",
                "icon_alias": controller.usb_db.get_device_icon_name("", str(item)) if hasattr(controller, "usb_db") else "generic-usb",
                "is_controller": "controller" in str(item).lower() or "gamepad" in str(item).lower()
            }
            for item in controller.config.blacklist
        ],
        "config": cfg_dict,
    }


def handle_save_options(controller: Any, data: dict) -> dict:
    """Update user configuration options."""
    for k, v in data.items():
        if hasattr(controller.config, k):
            setattr(controller.config, k, v)
    
    # If Wake-on-LAN wake is enabled, automatically activate WoL on the client NIC and sync to servers
    if controller.config.enable_wol_wake:
        from core.wol import enable_client_wake_on_lan, sync_client_wol_to_servers, get_primary_mac_address
        enable_client_wake_on_lan()
        controller.config.client_mac = get_primary_mac_address() or ""
        sync_client_wol_to_servers(controller)
    else:
        from core.wol import sync_client_wol_to_servers
        sync_client_wol_to_servers(controller)

    controller.config.save()
    if hasattr(controller, "scanner") and hasattr(controller.config, "polling_interval"):
        try:
            controller.scanner.polling_interval = float(controller.config.polling_interval)
        except Exception:
            pass
    return {"status": "ok", "message": "Options saved successfully"}


def handle_export_client_config(controller: Any) -> dict:
    """Export complete client configuration backup."""
    return {
        "status": "ok",
        "config": {
            "auto_attach": controller.config.auto_attach,
            "remember_detached_devices": controller.config.remember_detached_devices,
            "show_notifications": controller.config.show_notifications,
            "auto_discover": controller.config.auto_discover,
            "enable_nicknames": controller.config.enable_nicknames,
            "show_port": controller.config.show_port,
            "show_speed": controller.config.show_speed,
            "show_vid_pid": controller.config.show_vid_pid,
            "show_battery": controller.config.show_battery,
            "show_latency": controller.config.show_latency,
            "blacklist": controller.config.blacklist,
            "allow_lan_access": getattr(controller.config, "allow_lan_access", True),
        "nicknames": controller.config.nicknames,
            "servers": [
                {"ip": s.ip, "port": s.port, "name": s.name, "token": s.token, "enabled": s.enabled}
                for s in controller.servers
            ]
        }
    }


def handle_import_client_config(controller: Any, data: dict) -> dict:
    """Import and apply client configuration backup."""
    cfg = data.get("config", data)
    for k in ("auto_attach", "remember_detached_devices", "show_notifications", "auto_discover", "enable_nicknames", "show_port", "show_speed", "show_vid_pid", "show_battery", "show_latency", "show_server_temp", "show_server_ram", "show_server_uptime", "blacklist", "nicknames"):
        if k in cfg:
            setattr(controller.config, k, cfg[k])
    
    if "servers" in cfg and isinstance(cfg["servers"], list):
        from services.server_connection import ServerConnection
        new_srvs = []
        for s in cfg["servers"]:
            new_srvs.append(ServerConnection(
                ip=s.get("ip"),
                port=s.get("port", 3240),
                name=s.get("name", ""),
                token=s.get("token", ""),
                enabled=s.get("enabled", True)
            ))
        controller.servers = new_srvs

    controller.config.save()
    return {"status": "ok", "message": "Client configuration imported successfully"}


def handle_restart_client() -> dict:
    """Trigger graceful client application restart."""
    def _restart():
        time.sleep(0.4)
        python = sys.executable
        os.execl(python, python, *sys.argv)
    threading.Thread(target=_restart, daemon=True).start()
    return {"status": "ok", "message": "Restarting client..."}
