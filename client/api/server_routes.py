from __future__ import annotations

import logging
from typing import Any
from services.server_connection import ServerConnection

logger = logging.getLogger("auto-usbip-client")


def handle_add_server(controller: Any, data: dict) -> dict:
    """Add a new server or update an existing server configuration."""
    from config import is_valid_server_address
    ip = data.get("ip", "").strip()
    port = int(data.get("port", 3240))
    name = data.get("name", "").strip()
    token = data.get("token", "").strip()
    enabled = bool(data.get("enabled", True))

    if not ip or not is_valid_server_address(ip):
        return {"status": "error", "message": f"Invalid server IP address or hostname: {ip}"}

    # Verify authentication with server control socket if reachable
    from core.server_control import ServerControlClient
    try:
        test_client = ServerControlClient(ip, port=3241, token=token, timeout=2.5, use_tls=True)
        resp = test_client.get_devices()
        if resp is not None and resp.get("status") == "error" and "Unauthorized" in resp.get("message", ""):
            logger.warning(f"[Security Alert] Cannot add server {ip}: Server rejected connection due to invalid/missing token.")
            return {
                "status": "error",
                "message": "Authentication failed! The server is protected with a security token. Please enter the valid token to connect."
            }
    except Exception as e:
        logger.debug(f"Auth pre-verification warning for {ip}: {e}")

    existing = next((s for s in controller.servers if s.ip == ip and s.port == port), None)
    if existing:
        existing.name = name
        existing.token = token
        existing.enabled = enabled
    else:
        srv = ServerConnection(ip, port, name=name, token=token, enabled=enabled)
        controller.servers.append(srv)

    controller.save_servers_to_config()
    controller.scanner.set_servers(controller.servers)
    controller.scanner.trigger_scan()
    return {"status": "ok", "message": f"Server {ip}:{port} configured successfully"}


def handle_remove_server(controller: Any, ip: str, port: int) -> dict:
    """Remove a server connection and detach all its imported devices."""
    from core.usbip import get_port_to_bus_map, detach_port, get_imported_devices
    port_map = get_port_to_bus_map()
    clean_ip = str(ip).strip().lower()
    port = int(port)
    
    remaining_servers = [
        s for s in controller.servers
        if not (s.ip.strip().lower() == clean_ip and int(s.port) == port)
    ]
    
    # 1. Update controller server state and save immediately so status calls see it removed instantly
    controller.servers = remaining_servers
    controller.save_servers_to_config()
    
    if hasattr(controller, "scanner"):
        controller.scanner.set_servers(controller.servers)
        if not remaining_servers:
            if hasattr(controller.scanner, "last_device_map"):
                controller.scanner.last_device_map.clear()
            if hasattr(controller.scanner, "available_devices"):
                controller.scanner.available_devices.clear()
        else:
            if hasattr(controller.scanner, "last_device_map"):
                controller.scanner.last_device_map = {
                    k: d for k, d in controller.scanner.last_device_map.items()
                    if getattr(d, "server_ip", "").strip().lower() != clean_ip
                }
            if hasattr(controller.scanner, "available_devices"):
                controller.scanner.available_devices = [
                    d for d in controller.scanner.available_devices
                    if getattr(d, "server_ip", "").strip().lower() != clean_ip
                ]

        keys_to_del = [
            k for k in list(controller.scanner.ignored_devices.keys())
            if (isinstance(k, tuple) and len(k) > 0 and str(k[0]).strip().lower() == clean_ip)
            or (isinstance(k, str) and clean_ip in k.lower())
        ]
        for k in keys_to_del:
            controller.scanner.ignored_devices.pop(k, None)

    # 2. Detach any devices originating from this removed server
    for d in get_imported_devices():
        d_s_ip = getattr(d, "server_ip", "").strip().lower()
        d_port = getattr(d, "port", "")
        pair = port_map.get(str(d_port))
        if d_s_ip == clean_ip or (pair and pair[0].strip().lower() == clean_ip) or not remaining_servers:
            detach_port(str(d_port))

    if hasattr(controller, "scanner"):
        controller.scanner.trigger_scan()

    return {"status": "ok", "message": f"Server {ip}:{port} removed and devices detached"}


def handle_toggle_server(controller: Any, ip: str) -> dict:
    """Enable or disable a configured server."""
    new_state = False
    for s in controller.servers:
        if s.ip == ip:
            s.enabled = not s.enabled
            new_state = s.enabled

    if not new_state:
        from core.usbip import get_port_to_bus_map, detach_port, get_imported_devices
        port_map = get_port_to_bus_map()
        active_servers = [s for s in controller.servers if s.enabled]
        for d in get_imported_devices():
            d_s_ip = getattr(d, "server_ip", "")
            d_port = getattr(d, "port", "")
            pair = port_map.get(str(d_port))
            if d_s_ip == ip or (pair and pair[0] == ip) or not active_servers:
                detach_port(str(d_port))

    controller.save_servers_to_config()
    controller.scanner.set_servers(controller.servers)
    controller.scanner.trigger_scan()
    return {"status": "ok", "message": f"Toggled server {ip} (enabled: {new_state})"}


def handle_server_status(controller: Any, ip: str) -> dict:
    """Query remote server daemon metrics and system info over control socket."""
    srv = next((s for s in controller.servers if s.ip == ip), None)
    token = srv.token if srv else ""
    from core.server_control import get_server_status
    return get_server_status(ip, token=token)


def handle_server_logs(controller: Any, ip: str, lines: int = 80) -> dict:
    """Fetch live streaming logs from remote server daemon."""
    srv = next((s for s in controller.servers if s.ip == ip), None)
    token = srv.token if srv else ""
    from core.server_control import get_server_logs
    return get_server_logs(ip, lines=lines, token=token)


def handle_save_server_config(controller: Any, data: dict) -> dict:
    """Save remote server daemon configuration."""
    ip = data.get("ip", "")
    cfg = data.get("config", {})
    srv = next((s for s in controller.servers if s.ip == ip), None)
    token = srv.token if srv else ""
    from core.server_control import set_server_config
    return set_server_config(ip, cfg, token=token)


def handle_restart_server_daemon(controller: Any, ip: str) -> dict:
    """Restart the remote server daemon process."""
    srv = next((s for s in controller.servers if s.ip == ip), None)
    token = srv.token if srv else ""
    from core.server_control import restart_server_daemon
    return restart_server_daemon(ip, token=token)


def handle_reboot_server_system(controller: Any, ip: str) -> dict:
    """Trigger a full system reboot on remote host."""
    srv = next((s for s in controller.servers if s.ip == ip), None)
    token = srv.token if srv else ""
    from core.server_control import reboot_server_system
    return reboot_server_system(ip, token=token)
