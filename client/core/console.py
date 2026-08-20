from __future__ import annotations

import collections
import datetime
import json
import logging
import os
import platform
import subprocess
import threading
import time
from typing import Any

logger = logging.getLogger("auto-usbip-client")


class ConsoleLogRecord:
    __slots__ = ("id", "timestamp", "level", "name", "message", "time_epoch")

    def __init__(self, record_id: int, timestamp: str, level: str, name: str, message: str):
        self.id = record_id
        self.timestamp = timestamp
        self.level = level
        self.name = name
        self.message = message
        self.time_epoch = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "level": self.level,
            "name": self.name,
            "message": self.message,
        }


class ClientLogHandler(logging.Handler):
    """Ring buffer logging handler that feeds the live client web console."""

    def __init__(self, maxlen: int = 1500):
        super().__init__()
        self._lock = threading.Lock()
        self._counter = 0
        self._records: collections.deque[ConsoleLogRecord] = collections.deque(maxlen=maxlen)
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            now_str = datetime.datetime.fromtimestamp(record.created).strftime("%H:%M:%S.%f")[:-3]
            with self._lock:
                self._counter += 1
                rec = ConsoleLogRecord(
                    record_id=self._counter,
                    timestamp=now_str,
                    level=record.levelname,
                    name=record.name,
                    message=msg,
                )
                self._records.append(rec)
        except Exception:
            self.handleError(record)

    def get_logs(self, since_id: int = 0, limit: int = 250, level: str | None = None, search: str | None = None) -> tuple[list[dict[str, Any]], int]:
        with self._lock:
            all_records = list(self._records)
            latest_id = self._counter

        if since_id > 0:
            filtered = [r for r in all_records if r.id > since_id]
        else:
            filtered = all_records[-limit:]

        if level and level.upper() != "ALL":
            lvl_upper = level.upper()
            filtered = [r for r in filtered if r.level == lvl_upper]

        if search:
            q = search.lower()
            filtered = [r for r in filtered if q in r.message.lower() or q in r.name.lower()]

        return [r.to_dict() for r in filtered[-limit:]], latest_id

    def clear(self):
        with self._lock:
            self._records.clear()

    def add_custom_log(self, level: str, name: str, message: str) -> dict[str, Any]:
        now_str = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        with self._lock:
            self._counter += 1
            rec = ConsoleLogRecord(
                record_id=self._counter,
                timestamp=now_str,
                level=level.upper(),
                name=name,
                message=message,
            )
            self._records.append(rec)
            return rec.to_dict()


_GLOBAL_LOG_HANDLER = ClientLogHandler(maxlen=1500)
_INITIALIZED = False


def init_client_console():
    """Hook the ring buffer log handler into Python root and client loggers."""
    global _INITIALIZED
    if _INITIALIZED:
        return
    _GLOBAL_LOG_HANDLER.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(_GLOBAL_LOG_HANDLER)
    logging.getLogger("auto-usbip-client").addHandler(_GLOBAL_LOG_HANDLER)
    _INITIALIZED = True
    _GLOBAL_LOG_HANDLER.add_custom_log("INFO", "system", "Auto USB/IP Client Console Initialized")


def get_console_logs(since_id: int = 0, limit: int = 250, level: str | None = None, search: str | None = None) -> tuple[list[dict[str, Any]], int]:
    return _GLOBAL_LOG_HANDLER.get_logs(since_id=since_id, limit=limit, level=level, search=search)


def clear_console_logs():
    _GLOBAL_LOG_HANDLER.clear()


def log_console_event(level: str, name: str, message: str):
    return _GLOBAL_LOG_HANDLER.add_custom_log(level, name, message)


def _resolve_server_target(controller: Any, ip_arg: str | None = None) -> tuple[str | None, str]:
    """Resolve target server IP and auth token."""
    target_ip = ip_arg.strip() if ip_arg else None
    if not target_ip:
        if controller.servers:
            # Pick first active or configured server
            for s in controller.servers:
                if s.enabled:
                    target_ip = s.ip
                    break
            if not target_ip:
                target_ip = controller.servers[0].ip

    if not target_ip:
        return None, ""

    token = ""
    for s in controller.servers:
        if s.ip == target_ip:
            token = getattr(s, "token", "") or ""
            break
    return target_ip, token


def execute_server_console_command(args: list[str], controller: Any) -> str:
    """Execute rich control commands directly against a remote USB/IP server daemon."""
    from core.server_control import ServerControlClient

    if not args or args[0].lower() in ("help", "?"):
        return (
            "=== Remote USB/IP Server Commands ===\n"
            "  server status [ip]               - Get remote server hardware, metrics, and bound devices\n"
            "  server metrics [ip]              - Print remote CPU temp, memory, uptime, kernel version\n"
            "  server devices [ip]              - List physical USB hardware and active exported bus IDs\n"
            "  server logs [ip] [lines]         - Retrieve remote daemon journalctl log stream\n"
            "  server powercycle <busid> [ip]   - Cut and restore physical +5V VBUS power to port\n"
            "  server rebind [ip]               - Unbind and rebind all USB devices (clears zombies)\n"
            "  server restart [ip]              - Soft restart the remote autousbip daemon\n"
            "  server reboot [ip]               - Cold reboot the remote server system hardware\n"
            "  server config [ip]               - View remote server daemon settings\n"
            "  server blacklist [ip]            - View or manage server hardware blacklist\n"
            "  server blacklist add <vid:pid>   - Blacklist a hardware device on server\n"
            "  server blacklist remove <vid:pid>- Unblock a hardware device on server\n"
            "  server ping [ip]                 - Measure round-trip ping latency to server"
        )

    sub = args[0].lower()
    sub_args = args[1:]

    # Parse optional IP at end or beginning
    ip_arg = None
    if sub_args:
        # Check if last or first arg is an IP address
        if "." in sub_args[0] and not ":" in sub_args[0]:
            ip_arg = sub_args[0]
            sub_args = sub_args[1:]
        elif "." in sub_args[-1] and not ":" in sub_args[-1]:
            ip_arg = sub_args[-1]
            sub_args = sub_args[:-1]

    server_ip, token = _resolve_server_target(controller, ip_arg)
    if not server_ip:
        return "Error: No remote USB/IP servers configured or specified."

    client = ServerControlClient(server_ip, token=token)

    if sub in ("status", "info"):
        res = client.get_status()
        if not res or res.get("status") != "ok":
            return f"Failed to connect to server at {server_ip}:3241"
        m = res.get("metrics", {})
        devs = res.get("devices", {})
        bound = res.get("currently_bound", [])
        bl = res.get("blacklist", [])
        cfg = res.get("config", {})
        return (
            f"=== Server: {server_ip} ===\n"
            f"  CPU Temp: {m.get('cpu_temp', 'N/A')}\n"
            f"  RAM Usage: {m.get('ram_usage', 'N/A')}\n"
            f"  Uptime: {m.get('uptime', 'N/A')}\n"
            f"  Kernel: {m.get('kernel', 'N/A')}\n"
            f"  Daemon Version: {m.get('version', 'N/A')}\n"
            f"  mDNS Discovery: {'Enabled' if cfg.get('enable_discovery', True) else 'Disabled'}\n"
            f"  Exported Ports: {', '.join(bound) if bound else '(None)'}\n"
            f"  Connected USBs: {len(devs)} devices detected\n"
            f"  Blacklist: {len(bl)} items active"
        )

    if sub == "metrics":
        res = client.get_status()
        if not res or res.get("status") != "ok":
            return f"Failed to connect to server at {server_ip}:3241"
        m = res.get("metrics", {})
        return (
            f"=== Server Metrics: {server_ip} ===\n"
            f"  CPU Temp: {m.get('cpu_temp', 'N/A')}\n"
            f"  RAM Usage: {m.get('ram_usage', 'N/A')}\n"
            f"  Uptime: {m.get('uptime', 'N/A')}\n"
            f"  Kernel: {m.get('kernel', 'N/A')}"
        )

    if sub in ("devices", "ls", "list"):
        res = client.get_status()
        if not res or res.get("status") != "ok":
            return f"Failed to connect to server at {server_ip}:3241"
        devs = res.get("devices", {})
        bound = set(res.get("currently_bound", []))
        lines = [f"=== Physical USB Devices on {server_ip} ==="]
        for b_id, title in devs.items():
            status_tag = "[EXPORTED / BOUND]" if b_id in bound else "[UNBOUND / IDLE]"
            lines.append(f"  {b_id}: {title} {status_tag}")
        if not devs:
            lines.append("  (No devices detected in sysfs)")
        return "\n".join(lines)

    if sub in ("logs", "log"):
        lines_cnt = 40
        if sub_args and sub_args[0].isdigit():
            lines_cnt = int(sub_args[0])
        res = client.get_logs(lines=lines_cnt)
        if not res or res.get("status") != "ok":
            return f"Failed to retrieve logs from server {server_ip} (Daemon response error)"
        log_lines = res.get("logs", [])
        return "\n".join(log_lines) if log_lines else "(No logs returned from server)"

    if sub in ("powercycle", "cycle", "power", "reset-power"):
        if not sub_args:
            return "Usage: server powercycle <bus_id> [ip] (e.g. 'server powercycle 1-1.2')"
        bus_or_port = sub_args[0]
        res = client.reset_power(busid=bus_or_port)
        return f"Power cycle on {server_ip} ({bus_or_port}): {res.get('message', res) if res else 'No response'}"

    if sub in ("rebind", "recover", "reset-zombies", "clear-zombies"):
        res = client.reset_zombies()
        return f"Rebind response from {server_ip}: {res.get('message', res) if res else 'No response'}"

    if sub == "restart":
        res = client.restart_daemon()
        return f"Restart response from {server_ip}: {res.get('message', res) if res else 'No response'}"

    if sub == "reboot":
        res = client.reboot_system()
        return f"Reboot response from {server_ip}: {res.get('message', res) if res else 'No response'}"

    if sub in ("config", "cfg"):
        res = client.get_config()
        if not res or res.get("status") != "ok":
            return f"Failed to load config from {server_ip}"
        cfg = res.get("config", {})
        return f"=== Server Config ({server_ip}) ===\n" + json.dumps(cfg, indent=2)

    if sub == "blacklist":
        if not sub_args:
            res = client.get_status()
            bl = res.get("blacklist", []) if res else []
            return f"=== Server Blacklist ({server_ip}) ===\n" + ("\n".join(f"  - {x}" for x in bl) if bl else "  (Empty)")
        bl_action = sub_args[0].lower()
        if bl_action == "add" and len(sub_args) > 1:
            res = client.add_blacklist(sub_args[1])
            return f"Blacklist add on {server_ip}: {res.get('message', res) if res else 'Failed'}"
        elif bl_action in ("remove", "del", "rm") and len(sub_args) > 1:
            res = client.remove_blacklist(sub_args[1])
            return f"Blacklist remove on {server_ip}: {res.get('message', res) if res else 'Failed'}"
        return "Usage: server blacklist [add|remove <vid:pid>]"

    if sub == "ping":
        try:
            p = subprocess.run(["ping", "-c", "3", "-W", "2", server_ip], capture_output=True, text=True, timeout=7.0)
            return p.stdout.strip() or p.stderr.strip()
        except Exception as e:
            return f"Ping to {server_ip} failed: {e}"

    return f"Unknown server subcommand: '{sub}'. Type 'server help' for command list."


def execute_console_command(command: str, controller: Any, target_mode: str = "client") -> str:
    """Execute interactive CLI commands from the web client console with target awareness."""
    cmd = command.strip()
    if not cmd:
        return ""

    log_console_event("CMD", "user", f"> {cmd}")
    parts = cmd.split()
    verb = parts[0].lower()
    args = parts[1:]

    # Route explicit 'server' or 'rpi' or 'remote' prefixes
    if verb in ("server", "rpi", "remote"):
        return execute_server_console_command(args, controller)

    # If console is currently targeted directly at the server, route server commands transparently!
    if target_mode and target_mode.startswith("server"):
        server_ip = target_mode.split(":")[1] if ":" in target_mode else None
        # Handle 'client' escape or client-specific commands
        if verb == "client":
            return "Switched back to local client context."
        if verb in ("help", "?"):
            return execute_server_console_command(["help"], controller)
        if verb in ("status", "metrics", "devices", "logs", "powercycle", "cycle", "rebind", "recover", "restart", "reboot", "config", "blacklist", "ping"):
            full_args = [verb] + args
            if server_ip and server_ip not in full_args:
                full_args.append(server_ip)
            return execute_server_console_command(full_args, controller)

    # Standard Client Commands
    if verb in ("help", "?"):
        return (
            "=== Auto USB/IP Client Console Commands ===\n"
            "  help                         - Show this help menu\n"
            "  status                       - Display overall client, server, and device status\n"
            "  scan                         - Force an instant scan of all remote USB/IP servers\n"
            "  devices                      - List all currently imported and available remote USB devices\n"
            "  servers                      - List configured servers, reachability, and ping latency\n"
            "  attach <ip> <busid>          - Attach a remote USB device (e.g. 'attach 192.168.2.123 1-1.2')\n"
            "  detach <port>                - Detach a local VHCI port (e.g. 'detach 00')\n"
            "  detach-all                   - Detach all active local VHCI ports\n"
            "  rebind / recover             - Recover zombie connections and cycle ports\n"
            "  ping <ip>                    - Ping server IP and measure round-trip latency\n"
            "  audio <port>                 - Toggle audio state for controller on port\n"
            "  mouse <port>                 - Toggle trackpad mouse mode for DualSense on port\n"
            "  clear                        - Clear the console log buffer\n"
            "  version                      - Show client version, kernel, and system details\n\n"
            "=== Remote Server Commands (Type 'server help' for more) ===\n"
            "  server status                - Query remote server status, metrics, and hardware\n"
            "  server logs [lines]          - Fetch live journalctl logs from remote server\n"
            "  server powercycle <busid>    - Power cycle physical USB port on remote server\n"
            "  server reboot                - Reboot remote Raspberry Pi / server system\n"
            "  server restart               - Restart remote autousbip server daemon"
        )

    if verb == "status":
        from api.status_routes import handle_status
        st = handle_status(controller)
        srv_count = len(st.get("servers", []))
        att_count = len(st.get("attached_devices", []))
        avl_count = len(st.get("available_devices", []))
        return (
            f"Client Status: OK\n"
            f"Servers: {srv_count} configured\n"
            f"Attached Devices: {att_count}\n"
            f"Available Remote Devices: {avl_count}\n"
            f"Auto-Attach: {st.get('config', {}).get('auto_attach', False)}"
        )

    if verb == "scan":
        if hasattr(controller, "scanner"):
            controller.scanner.trigger_scan()
            return "Triggered instant background device scan."
        return "Scanner instance not available."

    if verb in ("devices", "ls", "list"):
        lines = ["=== Imported (Attached) Devices ==="]
        if hasattr(controller, "scanner"):
            for d in controller.scanner.imported_devices:
                lines.append(f"  Port {getattr(d, 'port', '?')}: {getattr(d, 'clean_name', getattr(d, 'desc', 'USB Device'))} ({getattr(d, 'speed', '?')}) [VID:PID {getattr(d, 'identifier_key', '?')}]")
            if not controller.scanner.imported_devices:
                lines.append("  (None attached)")

            lines.append("\n=== Available Remote Devices ===")
            for a in controller.scanner.available_devices:
                lines.append(f"  {a.server_ip} [{a.busid}]: {getattr(a, 'clean_name', a.description)}")
            if not controller.scanner.available_devices:
                lines.append("  (None available)")
        return "\n".join(lines)

    if verb in ("servers", "srv"):
        lines = ["=== Configured Servers ==="]
        for s in controller.servers:
            state = "Online" if s.is_alive else "Offline"
            lat = f"{getattr(s, 'latency_ms', '?')} ms" if s.is_alive else "N/A"
            lines.append(f"  {s.ip}:{s.port} ({s.name or 'Unnamed'}) - [{state}] Latency: {lat} (Enabled: {s.enabled})")
        if not controller.servers:
            lines.append("  (No servers configured)")
        return "\n".join(lines)

    if verb == "attach":
        if len(args) < 2:
            return "Usage: attach <server_ip> <bus_id> (e.g. 'attach 192.168.2.123 1-1.2')"
        ip, busid = args[0], args[1]
        from api.device_routes import handle_attach
        res = handle_attach(controller, ip, busid)
        return res.get("message", str(res))

    if verb == "detach":
        if len(args) < 1:
            return "Usage: detach <port> (e.g. 'detach 00')"
        port = args[0]
        from api.device_routes import handle_detach
        res = handle_detach(controller, port)
        return res.get("message", str(res))

    if verb in ("detach-all", "detach_all", "detachall"):
        from api.device_routes import handle_detach_all
        res = handle_detach_all(controller)
        return res.get("message", str(res))

    if verb in ("rebind", "recover", "recover-usb"):
        if hasattr(controller, "recover_zombie_connections"):
            controller.recover_zombie_connections()
        return "Initiated zombie connection recovery and port rebind."

    if verb in ("powercycle", "power-cycle", "reset-power"):
        if len(args) == 1:
            # Auto resolve server IP from first configured server
            server_ip, _ = _resolve_server_target(controller)
            if server_ip:
                return execute_server_console_command(["powercycle", args[0], server_ip], controller)
        elif len(args) >= 2:
            return execute_server_console_command(["powercycle", args[1], args[0]], controller)
        return "Usage: powercycle <bus_id> [ip] (e.g. 'powercycle 1-1.2')"

    if verb == "ping":
        target = args[0] if args else (controller.servers[0].ip if controller.servers else "127.0.0.1")
        try:
            p = subprocess.run(["ping", "-c", "3", "-W", "2", target], capture_output=True, text=True, timeout=7.0)
            return p.stdout.strip() or p.stderr.strip()
        except Exception as e:
            return f"Ping failed: {e}"

    if verb == "audio":
        if len(args) < 1:
            return "Usage: audio <port> (e.g. 'audio 00')"
        from api.device_routes import handle_toggle_device_audio
        res = handle_toggle_device_audio(controller, args[0])
        return res.get("message", str(res))

    if verb == "mouse":
        if len(args) < 1:
            return "Usage: mouse <port> (e.g. 'mouse 00')"
        from api.device_routes import handle_toggle_touchpad_mouse
        res = handle_toggle_touchpad_mouse(controller, args[0])
        return res.get("message", str(res))

    if verb in ("clear", "cls"):
        clear_console_logs()
        return "Console logs cleared."

    if verb in ("version", "ver", "about"):
        return (
            f"Auto USB/IP Client v2.3.0\n"
            f"Python: {platform.python_version()}\n"
            f"OS / Kernel: {platform.system()} {platform.release()} ({platform.machine()})\n"
            f"Host: {platform.node()}"
        )

    return f"Unknown command: '{verb}'. Type 'help' for client commands or 'server help' for remote server commands."
