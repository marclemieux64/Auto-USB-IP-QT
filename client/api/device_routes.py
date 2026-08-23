from __future__ import annotations

import logging
import subprocess
import threading
from typing import Any

logger = logging.getLogger("auto-usbip-client")


def handle_attach(controller: Any, ip: str, busid: str) -> dict:
    """Attach remote USB device."""
    from services.server_connection import AvailableDevice
    dev = next((d for d in controller.scanner.available_devices if d.server_ip == ip and d.busid == busid), None)
    if not dev:
        dev = AvailableDevice(server_ip=ip, busid=busid, description="USB Device")
    controller.attach_single_device(dev)
    return {"status": "ok", "message": f"Attached device {busid} from {ip}"}


def handle_detach(controller: Any, port: str) -> dict:
    """Detach local VHCI port."""
    controller.detach_single_device(port)
    return {"status": "ok", "message": f"Detached port {port}"}


def handle_detach_all(controller: Any) -> dict:
    """Detach all active imported VHCI ports."""
    controller.detach_all_devices()
    return {"status": "ok", "message": "Detached all ports"}


def handle_toggle_device_audio(controller: Any, port: str) -> dict:
    """Toggle audio card driver state for a controller / audio device."""
    norm_p = str(int(port)) if str(port).isdigit() else str(port)
    dev = next((d for d in controller.scanner.imported_devices if (str(d.port) == str(port) or str(getattr(d, "port", "")).lstrip("0") == str(norm_p).lstrip("0"))), None)
    if not dev:
        return {"status": "error", "message": f"Device on port {port} not found"}

    from core.audio_control import toggle_controller_audio
    desc_str = getattr(dev, "raw_desc", getattr(dev, "desc", "USB Device"))
    bus_id_str = getattr(dev, "bus_id", getattr(dev, "port", ""))
    
    vid, pid = 0, 0
    if hasattr(controller, "usb_db"):
        vid, pid = controller.usb_db.parse_vid_pid_from_string(desc_str)
    if not vid or not pid:
        raw_vp = getattr(dev, "vid_pid", "")
        if raw_vp and ":" in raw_vp:
            try:
                parts = raw_vp.replace("(", "").replace(")", "").strip().split(":")
                vid, pid = int(parts[0], 16), int(parts[1], 16)
            except Exception:
                pass

    v_str = f"{vid:04x}" if vid else None
    p_str = f"{pid:04x}" if pid else None

    new_state = toggle_controller_audio(port, bus_id_str, desc_str, vid=v_str, pid=p_str)
    dev.audio_enabled = new_state
    return {
        "status": "ok",
        "port": port,
        "audio_enabled": new_state,
        "message": f"Controller audio {'enabled' if new_state else 'disabled & muted'}"
    }


def handle_toggle_touchpad_mouse(controller: Any, port: str, enabled: bool | None = None) -> dict:
    """Toggle trackpad desktop mouse pointer behavior for PlayStation DualSense / DualShock 4 controllers."""
    from core.touchpad_control import set_touchpad_mouse_enabled, is_touchpad_mouse_enabled
    if enabled is None:
        current = is_touchpad_mouse_enabled(port)
        enabled = not current
    ok = set_touchpad_mouse_enabled(port, enabled)
    current_state = is_touchpad_mouse_enabled(port)
    return {
        "status": "ok" if ok else "error",
        "port": port,
        "touchpad_mouse_enabled": current_state,
        "message": f"Trackpad desktop mouse {'enabled' if current_state else 'disabled (gaming mode)'}"
    }


def handle_powercycle_device(controller: Any, ip: str, busid: str) -> dict:
    """Power cycle / reset a remote physical USB port via server control socket."""
    srv = next((s for s in controller.servers if s.ip == ip), None)
    token = srv.token if srv else ""
    from core.server_control import powercycle_device
    return powercycle_device(ip, busid, token=token)


def handle_recover_zombies(controller: Any) -> dict:
    """Clear zombie USB/IP connections and re-bind remote ports across all servers."""
    def _do_recover():
        import time
        from core.usbip import detach_all_ports
        detach_all_ports()
        if hasattr(controller, "scanner"):
            controller.scanner.ignored_devices.clear()
            controller.scanner.last_devices.clear()
            controller.scanner.last_device_map.clear()

        for s in controller.servers:
            if s.enabled:
                from core.server_control import reset_zombies
                try:
                    reset_zombies(s.ip, token=s.token)
                except Exception as e:
                    logger.debug(f"Error resetting zombies on {s.ip}: {e}")

        time.sleep(1.2)
        if hasattr(controller, "scanner"):
            controller.scanner.trigger_scan()

    threading.Thread(target=_do_recover, daemon=True).start()
    return {"status": "ok", "message": "Zombie connection recovery initiated"}


def handle_set_nickname(controller: Any, data: dict) -> dict:
    """Save custom device nickname."""
    key = data.get("key", "").strip()
    nick = data.get("nickname", "").strip()
    if key:
        if nick:
            controller.config.nicknames[key] = nick
        elif key in controller.config.nicknames:
            del controller.config.nicknames[key]
        controller.config.save()
    return {"status": "ok", "message": "Nickname updated"}


def handle_blacklist_device(controller: Any, data: Any) -> dict:
    """Add device to blacklist and detach it immediately."""
    if isinstance(data, str):
        identifier = data.strip()
        name = ""
        port = ""
        vid_pid = ""
        bus_id = ""
        icon_alias = ""
        is_controller = False
    elif isinstance(data, dict):
        identifier = (data.get("identifier") or data.get("vid_pid") or data.get("bus_id") or data.get("port") or "").strip()
        name = data.get("name", "").strip()
        port = data.get("port", "").strip()
        vid_pid = data.get("vid_pid", "").strip()
        bus_id = data.get("bus_id", "").strip()
        icon_alias = data.get("icon_alias", "").strip()
        is_controller = bool(data.get("is_controller", False))
    else:
        return {"status": "error", "message": "Invalid blacklist payload"}

    if not identifier and port:
        identifier = port

    if not identifier:
        return {"status": "error", "message": "No device identifier provided"}

    # Find name / vid_pid / icon_alias from currently attached or available devices if missing
    if hasattr(controller, "scanner"):
        for d in controller.scanner.imported_devices:
            if (port and str(d.port) == str(port)) or (vid_pid and getattr(d, 'vid_pid', '') == vid_pid) or (bus_id and getattr(d, 'busid', '') == bus_id):
                if not name:
                    name = getattr(d, 'clean_name', '') or d.description
                if not vid_pid:
                    vid_pid = getattr(d, 'vid_pid', '')
                if not bus_id:
                    bus_id = getattr(d, 'busid', '')
                if not port:
                    port = str(d.port)
                if not icon_alias and hasattr(controller, "usb_db"):
                    icon_alias = controller.usb_db.get_device_icon_name(bus_id, name)
                if not is_controller:
                    is_controller = getattr(d, 'is_controller', False)

    if not icon_alias and hasattr(controller, "usb_db"):
        icon_alias = controller.usb_db.get_device_icon_name(bus_id, name)

    # Normalize entry
    entry = {
        "identifier": identifier,
        "name": name or identifier,
        "vid_pid": vid_pid,
        "bus_id": bus_id,
        "icon_alias": icon_alias or "generic-usb",
        "is_controller": is_controller,
    }

    # Check if already blacklisted
    existing = False
    for item in controller.config.blacklist:
        if isinstance(item, dict):
            if item.get("identifier") == identifier or (vid_pid and item.get("vid_pid") == vid_pid):
                existing = True
                break
        elif str(item) == identifier:
            existing = True
            break

    if not existing:
        controller.config.blacklist.append(entry)
        controller.config.save()

    # Force immediate detach of matching ports
    from core.usbip import detach_device
    if port:
        detach_port(str(port))
    if hasattr(controller, "scanner"):
        for d in controller.scanner.imported_devices:
            if (
                str(d.port) == str(port)
                or (vid_pid and getattr(d, 'vid_pid', '') == vid_pid)
                or (bus_id and getattr(d, 'busid', '') == bus_id)
                or (name and d.description == name)
            ):
                detach_port(str(d.port))
        controller.scanner.trigger_scan()

    return {"status": "ok", "message": f"Blacklisted {name or identifier}"}


def handle_unblacklist_device(controller: Any, data: Any) -> dict:
    """Remove device from blacklist."""
    if isinstance(data, str):
        identifier = data.strip()
    elif isinstance(data, dict):
        identifier = (data.get("identifier") or data.get("vid_pid") or data.get("name") or "").strip()
    else:
        return {"status": "error", "message": "Invalid unblacklist payload"}

    controller.config.blacklist = [
        item for item in controller.config.blacklist
        if (item.get("identifier") if isinstance(item, dict) else str(item)) != identifier
        and (item.get("vid_pid") if isinstance(item, dict) else str(item)) != identifier
        and (item.get("name") if isinstance(item, dict) else str(item)) != identifier
    ]
    controller.config.save()
    if hasattr(controller, "scanner"):
        controller.scanner.trigger_scan()
    return {"status": "ok", "message": f"Unblacklisted {identifier}"}


def handle_open_storage(controller: Any, port: str) -> dict:
    """Open desktop file manager on mounted storage partition."""
    dev = next((d for d in controller.scanner.imported_devices if str(d.port) == str(port)), None)
    if not dev:
        return {"status": "error", "message": "Device not found"}
    
    mount_point = controller.find_storage_mount_point(port)
    if mount_point:
        subprocess.Popen(["xdg-open", mount_point])
        return {"status": "ok", "mount_point": mount_point}
    else:
        return {"status": "error", "message": "Could not locate mounted partition"}
