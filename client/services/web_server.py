from __future__ import annotations

import json
import logging
import mimetypes
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from PyQt6.QtCore import QBuffer, QIODevice, QSize
from PyQt6.QtGui import QIcon

import api

logger = logging.getLogger("auto-usbip-client")

_ICON_CACHE: dict[str, bytes] = {}
_STATIC_CACHE: dict[str, tuple[bytes, str]] = {}


class FastThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def server_bind(self):
        super().server_bind()
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)


class WebDashboardHandler(BaseHTTPRequestHandler):
    controller: Any = None
    web_root: Path = Path(__file__).resolve().parent.parent / "web"
    assets_root: Path = Path(__file__).resolve().parent.parent / "assets"


    def is_csrf_valid(self) -> bool:
        from config import load_config
        cfg = load_config()
        if not cfg.get("enable_web_csrf", False):
            return True

        origin = self.headers.get("Origin") or self.headers.get("Referer")
        if not origin:
            return True

        try:
            parsed_origin = urlparse(origin)
            origin_host = parsed_origin.hostname or ""
            if origin_host in ("localhost", "127.0.0.1", "::1"):
                return True
            
            if cfg.get("allow_lan_access", True):
                if origin_host.startswith("192.168.") or origin_host.startswith("10.") or origin_host.startswith("172."):
                    return True
        except Exception:
            pass

        logger.warning(f"[Security Alert] Blocked suspected CSRF request from origin: {origin} to {self.path}")
        return False

    def setup(self):
        super().setup()
        try:
            self.request.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass

    def log_message(self, format, *args):
        msg = format % args
        if "/api/status" in msg or "/api/gamepad_state" in msg or "/icons/" in msg:
            return
        logger.debug(f"[WebAPI] {msg}")

    def send_json_response(self, data: Any, status: int = 200):
        try:
            body = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def serve_static_file(self, file_path: Path):
        file_key = str(file_path.resolve())
        if file_key in _STATIC_CACHE:
            content, mime_type = _STATIC_CACHE[file_key]
        else:
            if not file_path.exists() or not file_path.is_file():
                self.send_error(404, "File Not Found")
                return
            
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if mime_type is None:
                mime_type = "application/octet-stream"
                
            content = file_path.read_bytes()
            _STATIC_CACHE[file_key] = (content, mime_type)

        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(content)

    def serve_icon(self, icon_name: str):
        if icon_name in _ICON_CACHE:
            png_data = _ICON_CACHE[icon_name]
        else:
            png_data = self.render_system_icon(icon_name)
            if png_data:
                _ICON_CACHE[icon_name] = png_data

        if png_data:
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(png_data)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self.wfile.write(png_data)
        else:
            self.send_error(404, "Icon Not Found")

    def render_system_icon(self, icon_name: str) -> bytes | None:
        custom_map = {
            "systray-logo": self.assets_root / "branding" / "systray-logo.png",
        }
        if icon_name in custom_map and custom_map[icon_name].exists():
            return custom_map[icon_name].read_bytes()

        theme_map = {
            "add-server": ["list-add-symbolic", "list-add", "document-new", "network-server"],
            "badge-tls": ["security-high-symbolic", "security-high", "channel-secure-symbolic", "dialog-password", "lock"],
            "server-card": ["network-server-symbolic", "network-server", "computer", "server-database"],
            "discovered-server": ["network-wireless-symbolic", "network-wireless", "network-server"],
            "gamepad": ["input-gaming-symbolic", "input-gaming", "input-gamepad", "applications-games", "preferences-desktop-gaming"],
            "generic-usb": ["drive-removable-media-usb-symbolic", "drive-removable-media-usb", "drive-removable-media", "media-removable", "network-wired"],
            "input-keyboard": ["input-keyboard-symbolic", "input-keyboard"],
            "input-mouse": ["input-mouse-symbolic", "input-mouse"],
            "camera-web": ["camera-web-symbolic", "camera-web"],
            "storage": ["drive-harddisk-usb-symbolic", "drive-harddisk-usb", "drive-removable-media-usb", "drive-harddisk", "media-flash"],
            "drive-harddisk": ["drive-harddisk-usb-symbolic", "drive-harddisk-usb", "drive-harddisk"],
            "network-connect": ["network-connect", "list-add-symbolic", "list-add", "media-playback-start"],
            "network-disconnect": ["network-disconnect", "list-remove-symbolic", "list-remove", "media-playback-pause"],
            "power-cycle": ["system-reboot-symbolic", "system-reboot", "view-refresh-symbolic", "view-refresh", "system-restart"],
            "settings": ["preferences-system-symbolic", "preferences-system", "configure", "preferences-other"],
            "configure": ["configure", "preferences-system-symbolic", "preferences-system"],
            "detach-all": ["list-remove-all-symbolic", "edit-delete-symbolic", "edit-delete", "process-stop", "window-close"],
            "detach-btn": ["list-remove-symbolic", "list-remove", "window-close", "edit-delete"],
            "rename": ["document-edit-symbolic", "document-edit", "edit-rename", "accessories-text-editor"],
            "blacklist": ["dialog-cancel-symbolic", "dialog-cancel", "action-unavailable", "security-medium"],
            "refresh": ["view-refresh-symbolic", "view-refresh", "reload"],
            "document-save": ["document-save-symbolic", "document-save", "document-export"],
            "document-open": ["document-open-symbolic", "document-open", "document-import"],
            "audio-card": ["audio-card-symbolic", "audio-card", "audio-speakers", "audio-volume-high"],
            "audio-volume-muted": ["audio-volume-muted-symbolic", "audio-volume-muted", "audio-volume-off"],
            "utilities-terminal": ["utilities-terminal-symbolic", "utilities-terminal", "terminal"],
            "attached-header": ["network-wired-symbolic", "network-wired", "network-connect"],
            "available-header": ["network-workgroup-symbolic", "network-workgroup", "network-server"],
            "badge-port": ["network-wired-symbolic", "network-wired", "drive-removable-media-usb"],
            "badge-speed": ["speedometer", "emblem-speed", "utilities-system-monitor-symbolic", "utilities-system-monitor"],
            "badge-vidpid": ["dialog-information-symbolic", "dialog-information", "help-about"],
            "badge-server": ["network-server-symbolic", "network-server", "computer"],
            "badge-battery": ["battery-good-symbolic", "battery-good", "battery-full", "battery"],
            "badge-latency": ["utilities-system-monitor-symbolic", "utilities-system-monitor", "view-refresh"]
        }

        names = theme_map.get(icon_name, [icon_name])
        icon = QIcon()
        for n in names:
            icon = QIcon.fromTheme(n)
            if not icon.isNull():
                break

        # If desktop theme icon was found, render it into PNG
        if not icon.isNull():
            pix = icon.pixmap(QSize(48, 48))
            if not pix.isNull():
                buf = QBuffer()
                buf.open(QIODevice.OpenModeFlag.WriteOnly)
                pix.save(buf, "PNG")
                return bytes(buf.data())

        # Fallback to bundled asset if headless / theme icon missing
        fallback_png = self.assets_root / "icons" / f"{icon_name}.png"
        if fallback_png.exists():
            return fallback_png.read_bytes()

        fallback_svg = self.assets_root / "icons" / f"{icon_name}.svg"
        if fallback_svg.exists():
            from PyQt6.QtSvg import QSvgRenderer
            from PyQt6.QtGui import QPainter, QColor, QImage
            renderer = QSvgRenderer(str(fallback_svg))
            img = QImage(48, 48, QImage.Format.Format_ARGB32_Premultiplied)
            img.fill(QColor(0, 0, 0, 0))
            painter = QPainter(img)
            renderer.render(painter)
            painter.end()
            buf = QBuffer()
            buf.open(QIODevice.OpenModeFlag.WriteOnly)
            img.save(buf, "PNG")
            return bytes(buf.data())

        return None

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)

            # 1. Dynamic Desktop Theme Icons (/icons/<name>.png) - Highest priority to reflect system theme!
            if path.startswith("/icons/"):
                icon_name = path[len("/icons/"):].replace(".png", "").replace(".svg", "")
                self.serve_icon(icon_name)
                return

            # 2. Root & Static Files
            if path == "/" or path == "/index.html":
                index_path = self.web_root / "index.html"
                self.serve_static_file(index_path)
                return

            if path.startswith("/assets/"):
                import urllib.parse
                rel_path = urllib.parse.unquote(path[len("/assets/"):].lstrip("/"))
                file_path = self.assets_root / rel_path
                if file_path.exists() and file_path.is_file():
                    self.serve_static_file(file_path)
                    return
                else:
                    self.send_error(404, f"Asset Not Found: {rel_path}")
                    return

            if path.startswith("/css/") or path.startswith("/js/"):
                rel_path = path.lstrip("/")
                file_path = self.web_root / rel_path
                self.serve_static_file(file_path)
                return

            direct_file = self.web_root / path.lstrip("/")
            if direct_file.exists() and direct_file.is_file():
                self.serve_static_file(direct_file)
                return

            parent_file = self.web_root.parent / path.lstrip("/")
            if parent_file.exists() and parent_file.is_file():
                self.serve_static_file(parent_file)
                return

            # 3. REST API Routes
            if path == "/api/status":
                self.send_json_response(api.handle_status(self.controller))
            elif path == "/api/export_client_config":
                self.send_json_response(api.handle_export_client_config(self.controller))
            elif path == "/api/restart_client":
                self.send_json_response(api.handle_restart_client())
            elif path == "/api/remove_server":
                ip = query.get("ip", [""])[0]
                port = int(query.get("port", [3240])[0])
                self.send_json_response(api.handle_remove_server(self.controller, ip, port))
            elif path == "/api/toggle_server":
                ip = query.get("ip", [""])[0]
                self.send_json_response(api.handle_toggle_server(self.controller, ip))
            elif path == "/api/server_status":
                ip = query.get("ip", [""])[0]
                self.send_json_response(api.handle_server_status(self.controller, ip))
            elif path == "/api/server_logs":
                ip = query.get("ip", [""])[0]
                lines = int(query.get("lines", [80])[0])
                self.send_json_response(api.handle_server_logs(self.controller, ip, lines))
            elif path == "/api/restart_server_daemon":
                ip = query.get("ip", [""])[0]
                self.send_json_response(api.handle_restart_server_daemon(self.controller, ip))
            elif path == "/api/reboot_server_system":
                ip = query.get("ip", [""])[0]
                self.send_json_response(api.handle_reboot_server_system(self.controller, ip))
            elif path == "/api/attach":
                ip = query.get("ip", [""])[0]
                busid = query.get("busid", [""])[0]
                self.send_json_response(api.handle_attach(self.controller, ip, busid))
            elif path == "/api/detach":
                port = query.get("port", [""])[0]
                self.send_json_response(api.handle_detach(self.controller, port))
            elif path == "/api/detach_all":
                self.send_json_response(api.handle_detach_all(self.controller))
            elif path == "/api/powercycle_device":
                ip = query.get("ip", [""])[0]
                busid = query.get("busid", [""])[0]
                self.send_json_response(api.handle_powercycle_device(self.controller, ip, busid))
            elif path == "/api/recover_zombies":
                self.send_json_response(api.handle_recover_zombies(self.controller))
            elif path == "/api/console_exec":
                command = query.get("command", [""])[0]
                target_mode = query.get("target", ["client"])[0]
                self.send_json_response(api.handle_exec_console_command(self.controller, command, target_mode=target_mode))
            elif path == "/api/console_clear":
                self.send_json_response(api.handle_clear_console_logs())
            elif path == "/api/open_storage":
                port = query.get("port", [""])[0]
                self.send_json_response(api.handle_open_storage(self.controller, port))
            elif path == "/api/toggle_touchpad_mouse":
                port = query.get("port", [""])[0]
                en_param = query.get("enabled", [None])[0]
                en_val = None if en_param is None else (en_param.lower() in ("true", "1"))
                self.send_json_response(api.handle_toggle_touchpad_mouse(self.controller, port, en_val))
            elif path == "/api/gamepad_state":
                port = query.get("port", [""])[0]
                self.send_json_response(api.handle_gamepad_state(self.controller, port))
            elif path == "/api/gamepad_control":
                self.send_json_response(api.handle_gamepad_control(self.controller, query))
            elif path == "/api/console_logs":
                since_id = int(query.get("since_id", [0])[0])
                limit = int(query.get("limit", [250])[0])
                level = query.get("level", [None])[0]
                search = query.get("search", [None])[0]
                self.send_json_response(api.handle_get_console_logs(since_id, limit, level, search))
            else:
                self.send_error(404, "Endpoint Not Found")
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            logger.error(f"Error handling GET {self.path}: {e}", exc_info=True)
            try:
                self.send_json_response({"status": "error", "message": str(e)}, status=500)
            except Exception:
                pass

    def do_POST(self):
        if not self.is_csrf_valid():
            self.send_json_response({"status": "error", "message": "Forbidden: CSRF / Cross-Origin validation failed."}, status=403)
            return
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            try:
                data = json.loads(body.decode("utf-8")) if body else {}
            except Exception:
                data = {}

            if path == "/api/add_server":
                self.send_json_response(api.handle_add_server(self.controller, data))
            elif path == "/api/save_options":
                self.send_json_response(api.handle_save_options(self.controller, data))
            elif path == "/api/import_client_config":
                self.send_json_response(api.handle_import_client_config(self.controller, data))
            elif path == "/api/save_server_config":
                self.send_json_response(api.handle_save_server_config(self.controller, data))
            elif path == "/api/toggle_device_audio":
                port = data.get("port", "")
                self.send_json_response(api.handle_toggle_device_audio(self.controller, port))
            elif path == "/api/toggle_touchpad_mouse":
                port = data.get("port", "")
                enabled = data.get("enabled", None)
                self.send_json_response(api.handle_toggle_touchpad_mouse(self.controller, port, enabled))
            elif path == "/api/set_nickname":
                self.send_json_response(api.handle_set_nickname(self.controller, data))
            elif path == "/api/blacklist_device":
                self.send_json_response(api.handle_blacklist_device(self.controller, data))
            elif path == "/api/unblacklist_device":
                self.send_json_response(api.handle_unblacklist_device(self.controller, data))
            elif path == "/api/attach":
                ip = data.get("ip", "")
                busid = data.get("busid", "")
                self.send_json_response(api.handle_attach(self.controller, ip, busid))
            elif path == "/api/detach":
                port = data.get("port", "")
                self.send_json_response(api.handle_detach(self.controller, port))
            elif path == "/api/powercycle_device":
                ip = data.get("ip", "")
                busid = data.get("busid", "")
                self.send_json_response(api.handle_powercycle_device(self.controller, ip, busid))
            elif path == "/api/recover_zombies":
                self.send_json_response(api.handle_recover_zombies(self.controller))
            elif path == "/api/console_exec":
                command = data.get("command", "")
                target_mode = data.get("target", "client")
                self.send_json_response(api.handle_exec_console_command(self.controller, command, target_mode=target_mode))
            elif path == "/api/console_clear":
                self.send_json_response(api.handle_clear_console_logs())
            else:
                self.send_error(404, "Endpoint Not Found")
        except Exception as e:
            logger.error(f"Error handling POST {self.path}: {e}", exc_info=True)
            self.send_json_response({"status": "error", "message": str(e)}, status=500)


class WebServerDaemon:
    def __init__(self, controller: Any, port: int = 3242):
        self.controller = controller
        self.port = port
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    def start(self):
        WebDashboardHandler.controller = self.controller
        try:
            from config import load_config
            cfg = load_config()
            bind_host = "0.0.0.0" if cfg.get("allow_lan_access", True) else "127.0.0.1"
            self.server = FastThreadingHTTPServer((bind_host, self.port), WebDashboardHandler)
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            logger.info(f"Web Dashboard Server started on http://{bind_host}:{self.port}/ (LAN access: {'Enabled' if bind_host == '0.0.0.0' else 'Disabled'})")
        except Exception as e:
            logger.error(f"Failed to bind Web Dashboard server on port {self.port}: {e}")

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            logger.info("Web Dashboard Server stopped.")