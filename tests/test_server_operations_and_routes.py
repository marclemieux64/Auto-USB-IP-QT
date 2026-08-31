import sys
import pytest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "client"))

from config import ClientConfig
from services.server_connection import ServerConnection
from api.server_routes import (
    handle_add_server,
    handle_remove_server,
    handle_toggle_server,
    handle_server_status,
    handle_server_logs,
    handle_save_server_config,
    handle_restart_server_daemon,
    handle_reboot_server_system,
    handle_scan_subnet,
)


@pytest.fixture
def mock_controller(tmp_path):
    fake_config_file = tmp_path / "config.json"
    with patch("config.CONFIG_PATH", fake_config_file):
        ctrl = MagicMock()
        ctrl.config = ClientConfig()
        ctrl.servers = [
            ServerConnection("192.168.1.100", 3240, name="Living Room Pi", token="tok123", enabled=True),
            ServerConnection("192.168.1.200", 3240, name="Office Host", token="", enabled=False),
        ]
        ctrl.save_servers_to_config = MagicMock()
        ctrl.scanner = SimpleNamespace(
            set_servers=MagicMock(),
            trigger_scan=MagicMock(),
            last_device_map={},
            available_devices=[],
            ignored_devices={},
        )
        return ctrl


def test_handle_add_server_success(mock_controller):
    """Verify handle_add_server adds a new server connection and triggers scanner."""
    payload = {
        "ip": "192.168.1.150",
        "port": 3240,
        "name": "Basement Hub",
        "token": "sec456",
        "enabled": True,
    }
    with patch("core.server_control.ServerControlClient.get_devices", return_value={"status": "ok"}):
        res = handle_add_server(mock_controller, payload)
        assert res["status"] == "ok"
        assert len(mock_controller.servers) == 3
        added = next((s for s in mock_controller.servers if s.ip == "192.168.1.150"), None)
        assert added is not None
        assert added.name == "Basement Hub"
        assert added.token == "sec456"
        mock_controller.save_servers_to_config.assert_called_once()
        mock_controller.scanner.set_servers.assert_called_once()
        mock_controller.scanner.trigger_scan.assert_called_once()


def test_handle_add_server_invalid_address(mock_controller):
    """Verify handle_add_server rejects invalid IP / hostname."""
    payload = {"ip": "invalid/path; injected", "port": 3240, "name": "Bad Server"}
    res = handle_add_server(mock_controller, payload)
    assert res["status"] == "error"
    assert "Invalid server IP" in res["message"]


def test_handle_add_server_auth_failed(mock_controller):
    """Verify handle_add_server alerts when server requires token and rejected auth."""
    payload = {"ip": "192.168.1.150", "port": 3240, "name": "Protected Pi", "token": ""}
    with patch("core.server_control.ServerControlClient.get_devices", return_value={"status": "error", "message": "Unauthorized: Token missing"}):
        res = handle_add_server(mock_controller, payload)
        assert res["status"] == "error"
        assert "Authentication failed" in res["message"]


def test_handle_add_server_update_existing(mock_controller):
    """Verify handle_add_server updates existing server in place."""
    payload = {
        "ip": "192.168.1.100",
        "port": 3240,
        "name": "Renamed Pi",
        "token": "new_tok",
        "enabled": False,
    }
    with patch("core.server_control.ServerControlClient.get_devices", return_value={"status": "ok"}):
        res = handle_add_server(mock_controller, payload)
        assert res["status"] == "ok"
        assert len(mock_controller.servers) == 2
        existing = next(s for s in mock_controller.servers if s.ip == "192.168.1.100")
        assert existing.name == "Renamed Pi"
        assert existing.token == "new_tok"
        assert existing.enabled is False


def test_handle_remove_server(mock_controller):
    """Verify handle_remove_server removes server and detaches imported devices."""
    mock_dev = SimpleNamespace(server_ip="192.168.1.100", port="1")
    with patch("core.usbip.get_port_to_bus_map", return_value={"1": ("192.168.1.100", "1-1.2")}), \
         patch("core.usbip.get_imported_devices", return_value=[mock_dev]), \
         patch("core.usbip.detach_port") as mock_detach_port:
        
        res = handle_remove_server(mock_controller, "192.168.1.100", 3240)
        assert res["status"] == "ok"
        assert len(mock_controller.servers) == 1
        assert mock_controller.servers[0].ip == "192.168.1.200"
        mock_detach_port.assert_called_with("1")
        mock_controller.save_servers_to_config.assert_called()


def test_handle_toggle_server(mock_controller):
    """Verify handle_toggle_server enables/disables server and cleans up devices when disabled."""
    mock_dev = SimpleNamespace(server_ip="192.168.1.100", port="2")
    with patch("core.usbip.get_port_to_bus_map", return_value={"2": ("192.168.1.100", "1-2")}), \
         patch("core.usbip.get_imported_devices", return_value=[mock_dev]), \
         patch("core.usbip.detach_port") as mock_detach_port:
        
        # Toggle enabled -> disabled
        res = handle_toggle_server(mock_controller, "192.168.1.100")
        assert res["status"] == "ok"
        srv = next(s for s in mock_controller.servers if s.ip == "192.168.1.100")
        assert srv.enabled is False
        mock_detach_port.assert_called_with("2")


def test_handle_server_status_and_logs(mock_controller):
    """Verify handle_server_status and handle_server_logs query the control socket with server token."""
    with patch("core.server_control.get_server_status", return_value={"status": "ok", "metrics": {"cpu_temp": "42.0C"}}) as mock_status, \
         patch("core.server_control.get_server_logs", return_value={"status": "ok", "logs": ["log line 1"]}) as mock_logs:
        
        st = handle_server_status(mock_controller, "192.168.1.100")
        assert st["status"] == "ok"
        mock_status.assert_called_once_with("192.168.1.100", token="tok123")

        lg = handle_server_logs(mock_controller, "192.168.1.100", lines=50)
        assert lg["status"] == "ok"
        mock_logs.assert_called_once_with("192.168.1.100", lines=50, token="tok123")


def test_handle_save_server_config(mock_controller):
    """Verify handle_save_server_config updates remote server daemon config and stores token."""
    with patch("core.server_control.set_server_config", return_value={"status": "ok"}) as mock_set_cfg:
        res = handle_save_server_config(
            mock_controller,
            {"ip": "192.168.1.100", "config": {"auth_token": "updated_secret", "enable_auth": True}}
        )
        assert res["status"] == "ok"
        srv = next(s for s in mock_controller.servers if s.ip == "192.168.1.100")
        assert srv.token == "updated_secret"
        mock_controller.save_servers_to_config.assert_called_once()


def test_handle_restart_and_reboot(mock_controller):
    """Verify handle_restart_server_daemon and handle_reboot_server_system dispatch correctly."""
    with patch("core.server_control.restart_server_daemon", return_value={"status": "ok"}) as mock_restart, \
         patch("core.server_control.reboot_server_system", return_value={"status": "ok"}) as mock_reboot:
        
        r1 = handle_restart_server_daemon(mock_controller, "192.168.1.100")
        assert r1["status"] == "ok"
        mock_restart.assert_called_once_with("192.168.1.100", token="tok123")

        r2 = handle_reboot_server_system(mock_controller, "192.168.1.100")
        assert r2["status"] == "ok"
        mock_reboot.assert_called_once_with("192.168.1.100", token="tok123")


def test_handle_scan_subnet(mock_controller):
    """Verify handle_scan_subnet starts SubnetScannerWorker."""
    with patch("services.discovery.SubnetScannerWorker") as mock_worker_cls:
        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = False
        mock_worker_cls.return_value = mock_worker

        res = handle_scan_subnet(mock_controller, "192.168.1.0/24")
        assert res["status"] == "ok"
        mock_worker.start.assert_called_once()

        # Busy check
        mock_worker.isRunning.return_value = True
        res_busy = handle_scan_subnet(mock_controller, "192.168.1.0/24")
        assert res_busy["status"] == "busy"
