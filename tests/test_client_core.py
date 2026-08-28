import pytest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath('client'))

from core.usbip import detach_device, detach_port, REMOTE_DEVICE_IN_USE_CACHE
from core.console import _ping_host
from core.wol import get_primary_mac_address
from core.gamepad.dualsense import play_sound_test_chime
from core.usb_ids import get_device_icon_from_desc, UsbIdsDatabase
from services.power_manager import PowerManager


def test_remote_device_in_use_cache():
    assert isinstance(REMOTE_DEVICE_IN_USE_CACHE, dict)
    REMOTE_DEVICE_IN_USE_CACHE[("192.168.2.123", "1-1.2")] = {"client_ip": "192.168.2.50"}
    assert REMOTE_DEVICE_IN_USE_CACHE[("192.168.2.123", "1-1.2")]["client_ip"] == "192.168.2.50"


def test_detach_device_polymorphism():
    with patch("core.usbip.detach_port", return_value=(True, "Port 0 detached")) as mock_detach_port:
        # Single argument port call
        ok, msg = detach_device("0")
        assert ok is True
        mock_detach_port.assert_called_with("0")

    with patch("core.usbip.list_imported_ports") as mock_list, patch("core.usbip.detach_port", return_value=(True, "Port 1 detached")) as mock_detach_port:
        mock_port = MagicMock()
        mock_port.busid = "1-1.2"
        mock_port.uri = "192.168.2.123"
        mock_port.port = "1"
        mock_list.return_value = [mock_port]

        # Two argument (host, busid) call
        ok, msg = detach_device("192.168.2.123", "1-1.2")
        assert ok is True
        mock_detach_port.assert_called_with("1")


def test_ping_host_cross_platform():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "64 bytes from 127.0.0.1"
        mock_run.return_value.stderr = ""
        res = _ping_host("127.0.0.1")
        assert "64 bytes" in res
        args = mock_run.call_args[0][0]
        if sys.platform == "win32":
            assert "-n" in args
        else:
            assert "-c" in args


def test_power_manager_instantiation():
    cb = MagicMock()
    pm = PowerManager(on_resume_callback=cb)
    assert pm.on_resume_callback == cb


def test_wol_mac_address():
    mac = get_primary_mac_address()
    if mac is not None:
        assert isinstance(mac, str)
        assert len(mac) == 17
        assert ":" in mac


def test_dualsense_chime_fallback():
    with patch("shutil.which", return_value=None):
        # When audio tools are absent, should return False gracefully without raising exceptions
        assert play_sound_test_chime(None) is False


def test_usb_ids_database():
    db = UsbIdsDatabase()
    assert db.get_device_icon_name("1-1", "Sony Interactive Entertainment DualSense Wireless Controller (054c:0ce6)") == "gamepad"
    assert db.is_gamepad_device("1-1", "DualSense Controller") is True
    assert db.is_storage_device("1-1", "SanDisk Ultra Flash Drive") is True


def test_handle_import_client_config():
    from api.status_routes import handle_import_client_config
    mock_controller = MagicMock()
    mock_controller.servers = []
    mock_controller.config = MagicMock()
    
    payload = {
        "config": {
            "auto_attach": False,
            "servers": [{"ip": "192.168.2.200", "port": 3240, "name": "Backup Server", "token": "sec123", "enabled": True}]
        }
    }
    
    res = handle_import_client_config(mock_controller, payload)
    assert res["status"] == "ok"
    assert len(mock_controller.servers) == 1
    assert mock_controller.servers[0].ip == "192.168.2.200"
    mock_controller.save_servers_to_config.assert_called_once()
    mock_controller.scanner.set_servers.assert_called_once()
    mock_controller.scanner.trigger_scan.assert_called_once()


def test_wol_enable_windows_safe():
    from core.wol import enable_client_wake_on_lan
    with patch("sys.platform", "win32"), patch("core.wol.get_primary_mac_address", return_value="aa:bb:cc:dd:ee:ff"):
        ok, msg = enable_client_wake_on_lan()
        assert ok is True
        assert "aa:bb:cc:dd:ee:ff" in msg


def test_usbip_cmd_read_vs_write():
    from core.usbip import _get_usbip_cmd, _find_usbip_bin

    # Read-only commands on Linux should never require elevation
    with patch("sys.platform", "linux"):
        port_cmd = _get_usbip_cmd(["port"])
        assert port_cmd[0] == _find_usbip_bin()
        assert port_cmd[1] == "port"

        list_cmd = _get_usbip_cmd(["list", "-r", "192.168.1.100"])
        assert list_cmd[0] == _find_usbip_bin()

        # Modifying commands when unprivileged should invoke pkexec on Linux
        with patch("core.usbip._can_write_vhci", return_value=False), \
             patch("os.geteuid", return_value=1000), \
             patch("core.usbip._find_usbip_bin", return_value="/usr/bin/usbip"), \
             patch("shutil.which", side_effect=lambda x: f"/usr/bin/{x}"), \
             patch("core.usbip._CAN_RUN_USBIP_DIRECT", None), \
             patch("core.usbip._HAS_PKEXEC", True):
            attach_cmd = _get_usbip_cmd(["attach", "-r", "192.168.1.100", "-b", "1-1.2"])
            assert attach_cmd[0] == "pkexec"
            assert "--disable-internal-agent" in attach_cmd
            assert attach_cmd[-2:] == ["-b", "1-1.2"]

        # When direct write is available on Linux, should run directly
        with patch("core.usbip._can_write_vhci", return_value=True), \
             patch("core.usbip._CAN_RUN_USBIP_DIRECT", None):
            attach_direct = _get_usbip_cmd(["attach", "-r", "192.168.1.100", "-b", "1-1.2"])
            assert attach_direct[0] == _find_usbip_bin()

    # Windows should use usbip.exe
    with patch("sys.platform", "win32"):
        win_cmd = _get_usbip_cmd(["attach", "-r", "192.168.1.100", "-b", "1-1.2"])
        assert win_cmd[0].endswith("usbip.exe")
        assert win_cmd[1] == "attach" 
