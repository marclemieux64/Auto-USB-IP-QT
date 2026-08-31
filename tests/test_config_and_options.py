import os
import sys
import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "client"))

from config import (
    get_default_config,
    load_config,
    save_config,
    ClientConfig,
    is_valid_server_address,
    play_sound_cue,
    get_config_path,
    POLLING_TIME,
)


def test_default_config_schema():
    """Verify that all default configuration keys, types, and values are correct."""
    cfg = get_default_config()
    assert isinstance(cfg, dict)

    # Core UI & Behaviour
    assert cfg["theme"] in ("system", "dark", "light")
    assert cfg["show_notifications"] is True
    assert cfg["play_sound_cues"] is True
    assert cfg["polling_interval"] == POLLING_TIME
    assert cfg["auto_attach"] is False
    assert cfg["power_cycle_on_attach"] is True
    assert cfg["remember_detached"] is True
    assert cfg["enable_nicknames"] is True
    assert cfg["enable_wol_wake"] is False
    assert cfg["client_mac"] == ""

    # Telemetry Badge Flags
    assert cfg["show_port"] is False
    assert cfg["show_speed"] is False
    assert cfg["show_vid_pid"] is False
    assert cfg["show_battery"] is True
    assert cfg["show_latency"] is False
    assert cfg["show_server_temp"] is True
    assert cfg["show_server_ram"] is True
    assert cfg["show_server_uptime"] is True

    # Network & Web UI
    assert cfg["auto_discover"] is True
    assert cfg["enable_web_ui"] is True
    assert cfg["allow_lan_access"] is True
    assert cfg["enable_web_csrf"] is False
    assert cfg["enable_tls_pinning"] is False
    assert isinstance(cfg["pinned_certificates"], dict)

    # BadUSB / Device Class Filters
    assert cfg["enable_device_class_filter"] is False
    assert cfg["block_mass_storage"] is False
    assert cfg["block_network_devices"] is False
    assert cfg["block_hid_keyboards"] is False

    # Collections
    assert isinstance(cfg["servers"], list)
    assert isinstance(cfg["nicknames"], dict)
    assert isinstance(cfg["blacklisted_devices"], list)
    assert isinstance(cfg["ignored_devices"], dict)


def test_server_address_validator():
    """Verify is_valid_server_address accepts valid hosts/IPs and blocks invalid/unsafe inputs."""
    valid_addresses = [
        "192.168.1.100",
        "10.0.0.1",
        "127.0.0.1",
        "raspberrypi.local",
        "usb-server.lan",
        "my-server-01",
        "::1",
        "2001:db8::1",
    ]
    for addr in valid_addresses:
        assert is_valid_server_address(addr) is True, f"Expected {addr} to be valid"

    invalid_addresses = [
        "",
        "   ",
        None,
        "-option",
        "%invalid",
        "path/traversal",
        "path\\traversal",
        "rm -rf /",
        "192.168.1.1; ls",
    ]
    for addr in invalid_addresses:
        assert is_valid_server_address(addr) is False, f"Expected {addr} to be invalid"


def test_config_load_and_save(tmp_path):
    """Verify loading, updating, and saving configuration to disk."""
    fake_config_file = tmp_path / "test_config.json"

    with patch("config.CONFIG_PATH", fake_config_file):
        # 1. Loading with no file should yield defaults
        cfg = load_config()
        assert cfg["show_notifications"] is True
        assert cfg["polling_interval"] == POLLING_TIME

        # 2. Modify and save
        cfg["show_notifications"] = False
        cfg["polling_interval"] = 5.0
        cfg["nicknames"]["054c:0ce6"] = "My DualSense"
        cfg["servers"].append({"ip": "192.168.1.50", "port": 3240, "name": "Pi Hub", "token": "sec", "enabled": True})
        save_config(cfg)

        assert fake_config_file.exists()

        # 3. Reload and verify persistence
        reloaded = load_config()
        assert reloaded["show_notifications"] is False
        assert reloaded["polling_interval"] == 5.0
        assert reloaded["nicknames"]["054c:0ce6"] == "My DualSense"
        assert len(reloaded["servers"]) == 1
        assert reloaded["servers"][0]["ip"] == "192.168.1.50"


def test_config_load_sanitizes_servers(tmp_path):
    """Verify that load_config filters out invalid server entries."""
    fake_config_file = tmp_path / "test_config.json"
    corrupt_data = {
        "servers": [
            {"ip": "192.168.1.100", "port": 3240},
            {"ip": "invalid/path", "port": 3240},
            {"ip": "-malicious", "port": 3240},
            "not a dict",
        ]
    }
    fake_config_file.write_text(json.dumps(corrupt_data), encoding="utf-8")

    with patch("config.CONFIG_PATH", fake_config_file):
        loaded = load_config()
        assert len(loaded["servers"]) == 1
        assert loaded["servers"][0]["ip"] == "192.168.1.100"


def test_client_config_class(tmp_path):
    """Verify ClientConfig class loads attributes, modifies them, and saves cleanly."""
    fake_config_file = tmp_path / "test_config.json"
    with patch("config.CONFIG_PATH", fake_config_file):
        cc = ClientConfig()
        assert cc.show_notifications is True
        assert cc.auto_attach is False

        cc.show_notifications = False
        cc.auto_attach = True
        cc.block_mass_storage = True
        cc.nicknames["046d:c52b"] = "Logitech Unifying Receiver"
        cc.save()

        # Create fresh instance to verify persisted values
        cc2 = ClientConfig()
        assert cc2.show_notifications is False
        assert cc2.auto_attach is True
        assert cc2.block_mass_storage is True
        assert cc2.nicknames.get("046d:c52b") == "Logitech Unifying Receiver"


def test_play_sound_cue_when_disabled():
    """Verify play_sound_cue exits early if play_sound_cues is False."""
    with patch("config.load_config", return_value={"play_sound_cues": False}), \
         patch("subprocess.Popen") as mock_popen, \
         patch("PyQt6.QtWidgets.QApplication.beep") as mock_beep:
        play_sound_cue("device-added")
        mock_popen.assert_not_called()
        mock_beep.assert_not_called()


def test_play_sound_cue_fallback_to_beep():
    """Verify play_sound_cue calls QApplication.beep() when no audio files or players exist."""
    with patch("config.load_config", return_value={"play_sound_cues": True}), \
         patch("os.path.exists", return_value=False), \
         patch("PyQt6.QtWidgets.QApplication.beep") as mock_beep:
        play_sound_cue("device-added")
        mock_beep.assert_called_once()
