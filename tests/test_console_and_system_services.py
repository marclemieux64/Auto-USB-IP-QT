import sys
import logging
import pytest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "client"))

from config import ClientConfig
from core.console import (
    ClientLogHandler,
    ConsoleLogRecord,
    execute_console_command,
    execute_server_console_command,
    clear_console_logs,
)
from core.wol import (
    get_primary_mac_address,
    enable_client_wake_on_lan,
    sync_client_wol_to_servers,
)
from services.power_manager import PowerManager


def test_client_log_handler_ring_buffer():
    """Verify ClientLogHandler maintains records, filters by level, paginates, and searches."""
    handler = ClientLogHandler(maxlen=10)
    test_logger = logging.getLogger("test_console_logger")
    test_logger.addHandler(handler)
    test_logger.setLevel(logging.DEBUG)

    # Emit records
    test_logger.info("Connecting to server 192.168.1.100")
    test_logger.warning("High latency detected on port 1")
    test_logger.error("Authentication rejected by daemon")

    # 1. Fetch all logs
    logs, last_id = handler.get_logs()
    assert len(logs) == 3
    assert last_id == 3
    assert logs[0]["level"] == "INFO"
    assert logs[1]["level"] == "WARNING"
    assert logs[2]["level"] == "ERROR"

    # 2. Filter by level
    err_logs, _ = handler.get_logs(level="ERROR")
    assert len(err_logs) == 1
    assert err_logs[0]["message"] == "Authentication rejected by daemon"

    # 3. Search query
    search_logs, _ = handler.get_logs(search="latency")
    assert len(search_logs) == 1
    assert "High latency" in search_logs[0]["message"]

    # 4. Pagination via since_id
    new_logs, _ = handler.get_logs(since_id=2)
    assert len(new_logs) == 1
    assert new_logs[0]["id"] == 3

    # 5. Clear buffer
    handler.clear()
    cleared_logs, new_last_id = handler.get_logs()
    assert len(cleared_logs) == 0


def test_execute_console_command_client_commands():
    """Verify execute_console_command executes local client commands."""
    mock_ctrl = MagicMock()
    mock_ctrl.config = ClientConfig()
    mock_ctrl.servers = [
        SimpleNamespace(ip="192.168.1.100", port=3240, name="Pi Hub", token="tok123", enabled=True, is_alive=True)
    ]
    mock_ctrl.scanner.imported_devices = [
        SimpleNamespace(port="1", description="DualSense Gamepad", speed="480Mbps")
    ]
    mock_ctrl.scanner.available_devices = [
        SimpleNamespace(server_ip="192.168.1.100", busid="1-1.2", description="USB Flash Drive")
    ]
    mock_ctrl.usb_db.parse_vid_pid_from_string.return_value = (0, 0)
    mock_ctrl.usb_db.get_device_name.return_value = "USB Device"
    mock_ctrl.usb_db.get_device_icon_name.return_value = "generic-usb"
    mock_ctrl.usb_db.is_gamepad_device.return_value = False
    mock_ctrl.usb_db.is_storage_device.return_value = False
    mock_ctrl.usb_db.is_audio_device.return_value = False
    mock_ctrl.usb_db.is_isochronous_or_high_bandwidth.return_value = False
    mock_ctrl.usb_db.is_compound_hub_child.return_value = False

    # Command: help
    help_out = execute_console_command("help", mock_ctrl)
    assert "Client Console Commands" in help_out
    assert "status" in help_out

    # Command: status
    with patch("core.usbip.get_port_to_bus_map", return_value={"1": ("192.168.1.100", "1-1.2")}), \
         patch("core.usbip.get_locally_attached_vid_pids", return_value=[]):
        status_out = execute_console_command("status", mock_ctrl)
        assert "Client Status: OK" in status_out
        assert "Servers: 1 configured" in status_out

    # Command: devices
    dev_out = execute_console_command("devices", mock_ctrl)
    assert "Port 1: USB Device" in dev_out
    assert "USB Flash Drive" in dev_out

    # Command: servers
    srv_out = execute_console_command("servers", mock_ctrl)
    assert "192.168.1.100:3240" in srv_out
    assert "Pi Hub" in srv_out

    # Command: version
    ver_out = execute_console_command("version", mock_ctrl)
    assert "Auto USB/IP Client" in ver_out

    # Command: ping
    with patch("core.console._ping_host", return_value="3 packets transmitted, 3 received, 0% packet loss"):
        ping_out = execute_console_command("ping 127.0.0.1", mock_ctrl)
        assert "0% packet loss" in ping_out

    # Command: scan
    scan_out = execute_console_command("scan", mock_ctrl)
    assert "Triggered instant background device scan" in scan_out
    mock_ctrl.scanner.trigger_scan.assert_called()


def test_execute_console_command_server_subcommands():
    """Verify execute_console_command forwards server subcommands to remote server daemon."""
    mock_ctrl = MagicMock()
    mock_ctrl.config = ClientConfig()
    mock_ctrl.servers = [
        SimpleNamespace(ip="192.168.1.100", port=3240, name="Pi Hub", token="tok123", enabled=True)
    ]

    with patch("core.server_control.ServerControlClient.get_status", return_value={
        "status": "ok",
        "metrics": {"cpu_temp": "45.0C", "ram_usage": "35%", "uptime": "2d 5h"},
        "devices": {"1-1.2": "Sony DualSense"},
        "currently_bound": ["1-1.2"],
        "blacklist": [],
        "config": {"enable_discovery": True},
    }):
        # server status
        res_status = execute_console_command("server status", mock_ctrl)
        assert "Server: 192.168.1.100" in res_status
        assert "45.0C" in res_status

        # server metrics
        res_metrics = execute_console_command("server metrics", mock_ctrl)
        assert "Server Metrics" in res_metrics
        assert "35%" in res_metrics

        # server devices
        res_devs = execute_console_command("server devices", mock_ctrl)
        assert "1-1.2: Sony DualSense [EXPORTED / BOUND]" in res_devs

    with patch("core.server_control.ServerControlClient.reset_zombies", return_value={"status": "ok", "message": "All devices rebound"}):
        res_rebind = execute_console_command("server rebind", mock_ctrl)
        assert "All devices rebound" in res_rebind

    with patch("core.server_control.ServerControlClient.restart_daemon", return_value={"status": "ok", "message": "Daemon restarted"}):
        res_restart = execute_console_command("server restart", mock_ctrl)
        assert "Daemon restarted" in res_restart


def test_power_manager_lifecycle():
    """Verify PowerManager registers resume callback and handles wakeup."""
    cb = MagicMock()
    pm = PowerManager(on_resume_callback=cb)
    assert pm.on_resume_callback == cb

    # Test waking from sleep (sleeping=False)
    pm._on_prepare_for_sleep(sleeping=False)
    cb.assert_called_once()


def test_wol_sync_to_servers():
    """Verify sync_client_wol_to_servers broadcasts client MAC address to all enabled servers."""
    mock_ctrl = MagicMock()
    mock_ctrl.config = ClientConfig()
    mock_ctrl.config.enable_wol_wake = True
    mock_ctrl.servers = [
        SimpleNamespace(ip="192.168.1.100", port=3240, token="tok123", enabled=True),
        SimpleNamespace(ip="192.168.1.200", port=3240, token="", enabled=False),
    ]

    with patch("core.wol.get_primary_mac_address", return_value="11:22:33:44:55:66"), \
         patch("core.server_control.ServerControlClient._send_cmd") as mock_send_cmd:
        
        sync_client_wol_to_servers(mock_ctrl)
        # Should be called only once for the enabled server
        assert mock_send_cmd.call_count == 1
        payload = mock_send_cmd.call_args[0][0]
        assert payload["cmd"] == "REGISTER_WOL_CLIENT"
        assert payload["mac"] == "11:22:33:44:55:66"
        assert payload["enabled"] is True
