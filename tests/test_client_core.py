import pytest
import os
import sys
import json
from pathlib import Path

# Add client to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "client"))

from config import load_config, save_config, get_default_config, is_valid_server_address
from core.usbip import list_imported_ports, ImportedPort, _get_usbip_cmd


def test_config_defaults_and_structure():
    default_cfg = get_default_config()
    assert "polling_interval" in default_cfg
    assert "allow_lan_access" in default_cfg
    assert "enable_web_csrf" in default_cfg
    assert "show_notifications" in default_cfg
    assert "enable_device_class_filter" in default_cfg


def test_is_valid_server_address_sanitization():
    # Valid targets
    assert is_valid_server_address("192.168.2.123") is True
    assert is_valid_server_address("10.0.0.1") is True
    assert is_valid_server_address("raspberrypi.local") is True
    assert is_valid_server_address("usbip-server") is True

    # Malicious injection targets
    assert is_valid_server_address("; rm -rf / ;") is False
    assert is_valid_server_address("../../../../etc/passwd") is False
    assert is_valid_server_address("-oProxyCommand=calc.exe") is False
    assert is_valid_server_address("") is False
    assert is_valid_server_address(None) is False


def test_imported_port_dataclass():
    port = ImportedPort(
        port="00",
        status="Port in Use",
        speed="High Speed(480Mbps)",
        devid="054c:0ce6",
        busid="1-1.2",
        uri="192.168.2.123:3240",
        device_name="Sony Interactive Entertainment Wireless Controller"
    )
    assert port.port == "00"
    assert port.busid == "1-1.2"
    assert port.devid == "054c:0ce6"


def test_get_usbip_cmd_structure():
    cmd = _get_usbip_cmd(["port"])
    assert isinstance(cmd, list)
    assert len(cmd) >= 2
    assert "port" in cmd
