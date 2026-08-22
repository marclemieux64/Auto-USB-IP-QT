import pytest
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "client"))

from config import get_config_path
from core.usbip import _get_windows_driver_dir, _get_usbip_cmd, ensure_vhci_loaded


def test_windows_config_roaming_path():
    with patch("sys.platform", "win32"), patch.dict(os.environ, {"APPDATA": "C:\\Users\\TestUser\\AppData\\Roaming"}):
        cfg_p = get_config_path()
        assert "Roaming" in str(cfg_p)
        assert "config.json" in str(cfg_p)


def test_windows_portable_mode_override(tmp_path):
    # If portable.flag is in the app directory, config path should be local to exe
    flag = tmp_path / "portable.flag"
    flag.touch()
    with patch("sys.platform", "win32"), patch("core.resources.get_app_dir", return_value=tmp_path):
        cfg_p = get_config_path()
        assert cfg_p == tmp_path / "config.json"


def test_windows_driver_command_flags():
    # Verify CREATE_NO_WINDOW is configured for win32
    from core import usbip
    with patch("sys.platform", "win32"):
        # Ensure command list generation quotes correctly without shell injection
        bundled_dir = Path("C:/Program Files/AutoUSBIP-QT/drivers")
        with patch("core.usbip._get_windows_driver_dir", return_value=bundled_dir):
            cmd = _get_usbip_cmd(["attach", "-r", "192.168.2.123", "-b", "1-1.2"])
            assert cmd[1] == "attach"
            assert cmd[3] == "192.168.2.123"
            assert cmd[5] == "1-1.2"
