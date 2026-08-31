import sys
import json
import socket
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "server"))

import autousbip


def test_default_server_config_schema():
    """Verify server default configuration schema and types."""
    cfg = autousbip.DEFAULT_SERVER_CONFIG
    assert isinstance(cfg, dict)
    assert cfg["auto_bind"] is True
    assert cfg["startup_power_cycle"] is True
    assert isinstance(cfg["vbus_off_delay"], (int, float))
    assert cfg["enable_auth"] is False
    assert cfg["auth_token"] == ""
    assert cfg["enable_subnet_filter"] is False
    assert cfg["enable_discovery"] is True
    assert cfg["enable_wake_on_lan"] is False
    assert isinstance(cfg["wol_target_macs"], list)
    assert cfg["enable_tls"] is True


def test_server_config_load_and_save(tmp_path):
    """Verify loading, updating, and saving server daemon config to disk."""
    fake_config_path = tmp_path / "server_config.json"
    with patch("autousbip.SERVER_CONFIG_PATH", fake_config_path), \
         patch("autousbip._CACHED_CONFIG", None):
        
        # Load default
        cfg = autousbip.load_server_config()
        assert cfg["enable_auth"] is False

        # Save new configuration
        cfg["enable_auth"] = True
        cfg["auth_token"] = "pi_secret_99"
        cfg["blacklist"] = ["1234:5678"]
        ok = autousbip.save_server_config(cfg)
        assert ok is True
        assert fake_config_path.exists()

        # Reload and verify
        reloaded = autousbip.load_server_config()
        assert reloaded["enable_auth"] is True
        assert reloaded["auth_token"] == "pi_secret_99"
        assert "1234:5678" in autousbip.BLACKLIST_VID_PID


def test_parse_proc_ip():
    """Verify _parse_proc_ip decodes kernel /proc/net/tcp hex IPs into standard dot notation."""
    # 0100007F -> 127.0.0.1 (little endian)
    assert autousbip._parse_proc_ip("0100007F") == "127.0.0.1"
    # 6401A8C0 -> 192.168.1.100
    assert autousbip._parse_proc_ip("6401A8C0") == "192.168.1.100"
    # 00000000 -> 0.0.0.0
    assert autousbip._parse_proc_ip("00000000") == "0.0.0.0"


def test_system_metrics_collector():
    """Verify get_system_metrics reports CPU temp, RAM, and Uptime."""
    with patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.read_text", return_value="48500\n"):
        
        metrics = autousbip.get_system_metrics()
        assert isinstance(metrics, dict)
        assert "cpu_temp" in metrics
        assert metrics["cpu_temp"] == "48.5°C"
        assert "ram_usage" in metrics
        assert "uptime" in metrics


def test_send_wake_on_lan():
    """Verify send_wake_on_lan constructs valid magic packet and broadcasts over UDP."""
    mac = "aa:bb:cc:dd:ee:ff"
    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock_cls.return_value.__enter__.return_value = mock_sock

        ok = autousbip.send_wake_on_lan(mac, broadcast_ip="192.168.1.255", port=9)
        assert ok is True
        mock_sock.sendto.assert_called_once()
        payload, addr = mock_sock.sendto.call_args[0]
        
        # Magic packet must be exactly 102 bytes (6x 0xFF + 16x 6-byte MAC)
        assert len(payload) == 102
        assert payload[:6] == b"\xff" * 6
        expected_mac_bytes = bytes.fromhex("aabbccddeeff") * 16
        assert payload[6:] == expected_mac_bytes
        assert addr == ("192.168.1.255", 9)


def test_default_blacklist_hardware():
    """Verify internal Raspberry Pi Ethernet chips and USB root hubs are in default blacklist."""
    # SMSC LAN9512/LAN9514 (Pi Ethernet)
    assert "0424:ec00" in autousbip.DEFAULT_BLACKLIST_VID_PID
    # Microchip LAN7800 (Pi 3B+)
    assert "0424:7800" in autousbip.DEFAULT_BLACKLIST_VID_PID
    # Linux Foundation Root Hubs
    assert "1d6b:0002" in autousbip.DEFAULT_BLACKLIST_VID_PID
    assert "1d6b:0003" in autousbip.DEFAULT_BLACKLIST_VID_PID
    # VIA Labs Hub (Pi 4)
    assert "2109:3431" in autousbip.DEFAULT_BLACKLIST_VID_PID


def test_vbus_power_cycle_command_generation():
    """Verify power_cycle_vbus_ports invokes uhubctl with expected arguments."""
    with patch("autousbip.get_uhubctl_path", return_value="/usr/sbin/uhubctl"), \
         patch("time.sleep"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Power cycle completed"
        
        autousbip.power_cycle_vbus_ports("2,3,4")
        assert mock_run.call_count == 2
        cmd_off = mock_run.call_args_list[0][0][0]
        assert cmd_off == ["/usr/sbin/uhubctl", "-a", "off", "-p", "2,3,4"]
        cmd_on = mock_run.call_args_list[1][0][0]
        assert cmd_on == ["/usr/sbin/uhubctl", "-a", "on", "-p", "2,3,4"]
