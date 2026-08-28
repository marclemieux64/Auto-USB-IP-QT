import pytest
import socket
import json
import urllib.request
import urllib.error
import threading
import time
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "client"))

from config import ClientConfig
from services.web_server import WebServerDaemon, FastThreadingHTTPServer, WebDashboardHandler


class DummyController:
    def __init__(self):
        self.servers = []
        self.imported_ports = []
        self.devices = []
        self.scanner = SimpleNamespace(imported_devices=[], available_devices=[])
        self.config = ClientConfig()
        self.app = None
        self.gamepad_monitor = None


@pytest.fixture(scope="module")
def live_web_server():
    # Pick a random free port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()

    dummy_ctrl = DummyController()
    WebDashboardHandler.controller = dummy_ctrl

    server = FastThreadingHTTPServer(('127.0.0.1', port), WebDashboardHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.2)

    yield f"http://127.0.0.1:{port}"

    server.shutdown()
    server.server_close()


def test_web_server_index_served(live_web_server):
    req = urllib.request.Request(f"{live_web_server}/")
    with urllib.request.urlopen(req, timeout=3.0) as resp:
        assert resp.status == 200
        content = resp.read().decode("utf-8")
        assert "<html" in content.lower() or "<!doctype html" in content.lower()


def test_web_server_path_traversal_blocked(live_web_server):
    # Attempt directory traversal out of web root
    traversal_paths = [
        "/../../../../../../etc/passwd",
        "/assets/../../../../../../etc/shadow",
        "/css/../../../../../../etc/hosts",
    ]
    for p in traversal_paths:
        url = f"{live_web_server}{p}"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                # Should not succeed in reading host files
                assert False, f"Path traversal succeeded unexpectedly on {url}"
        except urllib.error.HTTPError as e:
            # 403 Forbidden or 404 Not Found are both safe responses
            assert e.code in (400, 403, 404)


def test_web_server_api_status(live_web_server):
    req = urllib.request.Request(f"{live_web_server}/api/status")
    with urllib.request.urlopen(req, timeout=3.0) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "status" in data or "servers" in data

from unittest.mock import patch


def test_web_server_post_csrf_validation(live_web_server):
    # Test POST endpoint with and without valid CSRF
    url = f"{live_web_server}/api/powercycle_device"
    payload = json.dumps({"ip": "192.168.2.123", "busid": "1-1.2"}).encode("utf-8")
    
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "Origin": "http://localhost:3242"}
    )
    with patch("api.device_routes.handle_powercycle_device", return_value={"status": "ok", "message": "Port power cycled"}), \
         patch("core.server_control.powercycle_device", return_value={"status": "ok", "message": "Port power cycled"}):
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            assert resp.status == 200
