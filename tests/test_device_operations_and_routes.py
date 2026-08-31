import sys
import json
import pytest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "client"))

from config import ClientConfig
from api.device_routes import (
    handle_attach,
    handle_detach,
    handle_detach_all,
    handle_toggle_device_audio,
    handle_toggle_touchpad_mouse,
    handle_powercycle_device,
    handle_recover_zombies,
    handle_set_nickname,
    handle_blacklist_device,
    handle_unblacklist_device,
    handle_open_storage,
)


@pytest.fixture
def mock_controller(tmp_path):
    fake_config_file = tmp_path / "config.json"
    with patch("config.CONFIG_PATH", fake_config_file):
        ctrl = MagicMock()
        ctrl.config = ClientConfig()
        ctrl.servers = [
            SimpleNamespace(ip="192.168.1.100", port=3240, token="test_tok", enabled=True),
            SimpleNamespace(ip="192.168.1.200", port=3240, token="", enabled=False),
        ]
        dev1 = SimpleNamespace(
            port="1",
            busid="1-1.2",
            server_ip="192.168.1.100",
            description="Sony Interactive Entertainment DualSense (054c:0ce6)",
            raw_desc="Sony Interactive Entertainment DualSense (054c:0ce6)",
            vid_pid="054c:0ce6",
            audio_enabled=True,
            is_controller=True,
        )
        ctrl.scanner = SimpleNamespace(
            available_devices=[SimpleNamespace(server_ip="192.168.1.100", busid="1-1.2", description="USB Gamepad")],
            imported_devices=[dev1],
            ignored_devices={},
            last_devices=set(),
            last_device_map={},
            trigger_scan=MagicMock(),
        )
        ctrl.usb_db = MagicMock()
        ctrl.usb_db.parse_vid_pid_from_string.return_value = (0x054C, 0x0CE6)
        ctrl.usb_db.get_device_icon_name.return_value = "gamepad"
        return ctrl


def test_handle_attach(mock_controller):
    """Verify handle_attach attaches the matching device from scanner available list."""
    res = handle_attach(mock_controller, "192.168.1.100", "1-1.2")
    assert res["status"] == "ok"
    mock_controller.attach_single_device.assert_called_once()
    attached_dev = mock_controller.attach_single_device.call_args[0][0]
    assert attached_dev.server_ip == "192.168.1.100"
    assert attached_dev.busid == "1-1.2"


def test_handle_attach_unlisted_fallback(mock_controller):
    """Verify handle_attach creates an on-the-fly AvailableDevice when not previously in scanner cache."""
    res = handle_attach(mock_controller, "192.168.1.150", "2-1")
    assert res["status"] == "ok"
    mock_controller.attach_single_device.assert_called_once()
    attached_dev = mock_controller.attach_single_device.call_args[0][0]
    assert attached_dev.server_ip == "192.168.1.150"
    assert attached_dev.busid == "2-1"


def test_handle_detach(mock_controller):
    """Verify handle_detach detaches specific port."""
    res = handle_detach(mock_controller, "1")
    assert res["status"] == "ok"
    mock_controller.detach_single_device.assert_called_once_with("1")


def test_handle_detach_all(mock_controller):
    """Verify handle_detach_all detaches all imported devices."""
    res = handle_detach_all(mock_controller)
    assert res["status"] == "ok"
    mock_controller.detach_all_devices.assert_called_once()


def test_handle_powercycle_device(mock_controller):
    """Verify handle_powercycle_device sends power cycle request with correct server token."""
    with patch("core.server_control.powercycle_device", return_value={"status": "ok", "message": "Power cycled"}) as mock_pcycle:
        res = handle_powercycle_device(mock_controller, "192.168.1.100", "1-1.2")
        assert res["status"] == "ok"
        mock_pcycle.assert_called_once_with("192.168.1.100", "1-1.2", token="test_tok")


def test_handle_recover_zombies(mock_controller):
    """Verify handle_recover_zombies triggers detach_all_ports and resets server zombies."""
    with patch("core.usbip.detach_all_ports") as mock_detach_all, \
         patch("core.server_control.reset_zombies") as mock_reset_zombies:
        res = handle_recover_zombies(mock_controller)
        assert res["status"] == "ok"
        # Since it runs in a thread, wait briefly
        import time
        time.sleep(0.1)
        mock_detach_all.assert_called()


def test_handle_set_nickname(mock_controller):
    """Verify handle_set_nickname updates and persists custom device names."""
    with patch.object(mock_controller.config, "save") as mock_save:
        # Add nickname
        res = handle_set_nickname(mock_controller, {"key": "054c:0ce6", "nickname": "Custom PS5 Pad"})
        assert res["status"] == "ok"
        assert mock_controller.config.nicknames["054c:0ce6"] == "Custom PS5 Pad"
        mock_save.assert_called_once()

        # Delete nickname
        mock_save.reset_mock()
        res2 = handle_set_nickname(mock_controller, {"key": "054c:0ce6", "nickname": ""})
        assert res2["status"] == "ok"
        assert "054c:0ce6" not in mock_controller.config.nicknames
        mock_save.assert_called_once()


def test_handle_blacklist_and_unblacklist(mock_controller):
    """Verify handle_blacklist_device forces immediate detach and handle_unblacklist_device cleans up."""
    with patch("core.usbip.detach_port") as mock_detach_port, \
         patch.object(mock_controller.config, "save") as mock_save:
        
        # Blacklist device
        payload = {
            "identifier": "054c:0ce6",
            "name": "Sony DualSense",
            "port": "1",
            "vid_pid": "054c:0ce6",
            "bus_id": "1-1.2",
            "icon_alias": "gamepad",
            "is_controller": True,
        }
        res = handle_blacklist_device(mock_controller, payload)
        assert res["status"] == "ok"
        assert any(
            item.get("identifier") == "054c:0ce6" for item in mock_controller.config.blacklist if isinstance(item, dict)
        )
        mock_detach_port.assert_called_with("1")
        mock_save.assert_called()
        mock_controller.scanner.trigger_scan.assert_called()

        # Unblacklist device
        mock_save.reset_mock()
        mock_controller.scanner.trigger_scan.reset_mock()
        res_un = handle_unblacklist_device(mock_controller, "054c:0ce6")
        assert res_un["status"] == "ok"
        assert not any(
            (item.get("identifier") if isinstance(item, dict) else str(item)) == "054c:0ce6"
            for item in mock_controller.config.blacklist
        )
        mock_save.assert_called()
        mock_controller.scanner.trigger_scan.assert_called()


def test_handle_toggle_device_audio(mock_controller):
    """Verify handle_toggle_device_audio calls toggle_controller_audio and updates device state."""
    with patch("core.audio_control.toggle_controller_audio", return_value=False) as mock_toggle:
        res = handle_toggle_device_audio(mock_controller, "1")
        assert res["status"] == "ok"
        assert res["audio_enabled"] is False
        mock_toggle.assert_called_once()


def test_handle_toggle_touchpad_mouse(mock_controller):
    """Verify handle_toggle_touchpad_mouse switches mouse pointer emulation state."""
    # Test 1: Explicit enabled=True
    with patch("core.touchpad_control.set_touchpad_mouse_enabled", return_value=True) as mock_set, \
         patch("core.touchpad_control.is_touchpad_mouse_enabled", return_value=True):
        res = handle_toggle_touchpad_mouse(mock_controller, "1", enabled=True)
        assert res["status"] == "ok"
        assert res["touchpad_mouse_enabled"] is True
        mock_set.assert_called_once_with("1", True)

    # Test 2: Toggle mode (enabled=None) flips False to True
    with patch("core.touchpad_control.set_touchpad_mouse_enabled", return_value=True) as mock_set, \
         patch("core.touchpad_control.is_touchpad_mouse_enabled", side_effect=[False, True]):
        res2 = handle_toggle_touchpad_mouse(mock_controller, "1", enabled=None)
        assert res2["status"] == "ok"
        assert res2["touchpad_mouse_enabled"] is True
        mock_set.assert_called_once_with("1", True)


def test_handle_open_storage(mock_controller):
    """Verify handle_open_storage discovers mount point and triggers xdg-open."""
    mock_controller.find_storage_mount_point = MagicMock(return_value="/media/user/USB_STICK")
    with patch("subprocess.Popen") as mock_popen:
        res = handle_open_storage(mock_controller, "1")
        assert res["status"] == "ok"
        assert res["mount_point"] == "/media/user/USB_STICK"
        mock_popen.assert_called_once_with(["xdg-open", "/media/user/USB_STICK"])
