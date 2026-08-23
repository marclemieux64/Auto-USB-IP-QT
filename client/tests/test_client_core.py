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
