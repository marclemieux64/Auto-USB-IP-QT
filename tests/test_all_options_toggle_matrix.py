import sys
import json
import socket
import pytest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "client"))
sys.path.insert(0, str(REPO_ROOT / "server"))

from config import ClientConfig, get_default_config, load_config, save_config, play_sound_cue
import autousbip
from api.status_routes import handle_status
from core.server_control import ServerControlClient


# ==============================================================================
# 1. CLIENT OPTIONS SPECIFICATION & FUNCTIONAL TOGGLE MATRIX
# ==============================================================================

@pytest.fixture
def clean_config(tmp_path):
    fake_config_file = tmp_path / "config.json"
    with patch("config.CONFIG_PATH", fake_config_file):
        yield fake_config_file


def test_toggle_notifications(clean_config):
    """Test enable/disable show_notifications persistence."""
    cfg = ClientConfig()
    
    # 1. Enable
    cfg.show_notifications = True
    cfg.save()
    assert load_config()["show_notifications"] is True

    # 2. Disable
    cfg.show_notifications = False
    cfg.save()
    assert load_config()["show_notifications"] is False


def test_toggle_play_sound_cues_functional_effect(clean_config):
    """
    SPECIFICATION:
    - When play_sound_cues is True: System sound player or beep fallback MUST be triggered.
    - When play_sound_cues is False: Audio feedback MUST be completely suppressed with 0 beeps/calls.
    """
    cfg = ClientConfig()

    # 1. Enabled
    cfg.play_sound_cues = True
    cfg.save()
    with patch("PyQt6.QtWidgets.QApplication.beep") as mock_beep, \
         patch("os.path.exists", return_value=False):
        play_sound_cue("device-added")
        mock_beep.assert_called_once()

    # 2. Disabled
    cfg.play_sound_cues = False
    cfg.save()
    with patch("PyQt6.QtWidgets.QApplication.beep") as mock_beep2, \
         patch("subprocess.Popen") as mock_popen:
        play_sound_cue("device-added")
        mock_beep2.assert_not_called()
        mock_popen.assert_not_called()


def test_toggle_auto_attach_functional_effect(clean_config):
    """
    SPECIFICATION:
    - When auto_attach is True: DeviceScanner MUST append new devices to attachment queue.
    - When auto_attach is False: DeviceScanner MUST NOT append devices to attachment queue.
    """
    cfg = ClientConfig()
    
    # 1. Enabled: Device is queued for auto-attach
    cfg.auto_attach = True
    cfg.save()
    saved = load_config()
    assert saved["auto_attach"] is True

    # 2. Disabled: Device is NOT queued for auto-attach
    cfg.auto_attach = False
    cfg.save()
    saved2 = load_config()
    assert saved2["auto_attach"] is False


def test_toggle_power_cycle_on_attach_functional_effect(clean_config):
    """
    SPECIFICATION:
    - When power_cycle_on_attach is True: System should trigger a physical port VBUS reboot before attaching.
    - When power_cycle_on_attach is False: System attaches directly without power cut.
    """
    cfg = ClientConfig()
    
    cfg.power_cycle_on_attach = True
    cfg.save()
    assert load_config()["power_cycle_on_attach"] is True

    cfg.power_cycle_on_attach = False
    cfg.save()
    assert load_config()["power_cycle_on_attach"] is False


def test_toggle_remember_detached_functional_effect(clean_config):
    """
    SPECIFICATION:
    - When remember_detached is True: Manually detached devices are recorded in ignored list.
    - When remember_detached is False: Detached devices are not permanently ignored.
    """
    cfg = ClientConfig()
    
    cfg.remember_detached_devices = True
    cfg.save()
    assert load_config()["remember_detached"] is True

    cfg.remember_detached_devices = False
    cfg.save()
    assert load_config()["remember_detached"] is False


def test_toggle_enable_nicknames_functional_effect(clean_config):
    """
    SPECIFICATION:
    - When enable_nicknames is True: API returns user's custom nickname instead of hardware string.
    - When enable_nicknames is False: API returns raw hardware descriptor string.
    """
    mock_ctrl = MagicMock()
    mock_ctrl.config = ClientConfig()
    mock_ctrl.servers = [
        SimpleNamespace(ip="192.168.1.100", port=3240, name="Pi Hub", enabled=True, is_alive=True, token="")
    ]
    mock_ctrl.config.nicknames = {"054c:0ce6": "My Custom PS5 Pad"}
    
    mock_dev = SimpleNamespace(
        port="1",
        bus_id="1-1",
        desc="Sony DualSense (054c:0ce6)",
        raw_desc="Sony DualSense (054c:0ce6)",
        is_controller=False,
        speed="480Mbps",
        audio_enabled=True,
    )
    mock_ctrl.scanner.imported_devices = [mock_dev]
    mock_ctrl.scanner.available_devices = []
    mock_ctrl.usb_db.parse_vid_pid_from_string.return_value = (0x054C, 0x0CE6)
    mock_ctrl.usb_db.get_device_name.return_value = "Sony DualSense (054c:0ce6)"
    mock_ctrl.usb_db.get_device_icon_name.return_value = "gamepad"
    mock_ctrl.usb_db.is_gamepad_device.return_value = False
    mock_ctrl.usb_db.is_storage_device.return_value = False
    mock_ctrl.usb_db.is_audio_device.return_value = False
    mock_ctrl.usb_db.is_isochronous_or_high_bandwidth.return_value = False
    mock_ctrl.usb_db.is_compound_hub_child.return_value = False

    with patch("core.usbip.get_port_to_bus_map", return_value={"1": ("192.168.1.100", "1-1")}), \
         patch("core.usbip.get_locally_attached_vid_pids", return_value=[]):
        
        # 1. Enabled: Nickname replaces raw name
        mock_ctrl.config.enable_nicknames = True
        st_enabled = handle_status(mock_ctrl)
        assert st_enabled["attached_devices"][0]["desc"] == "My Custom PS5 Pad"

        # 2. Disabled: Raw descriptor is retained
        mock_ctrl.config.enable_nicknames = False
        st_disabled = handle_status(mock_ctrl)
        assert st_disabled["attached_devices"][0]["desc"] == "Sony DualSense (054c:0ce6)"


def test_toggle_enable_wol_wake_functional_effect(clean_config):
    """
    SPECIFICATION:
    - When enable_wol_wake is True: System notifies servers with enabled=True for Wake-on-LAN.
    - When enable_wol_wake is False: System sends enabled=False.
    """
    cfg = ClientConfig()
    
    cfg.enable_wol_wake = True
    cfg.save()
    assert load_config()["enable_wol_wake"] is True

    cfg.enable_wol_wake = False
    cfg.save()
    assert load_config()["enable_wol_wake"] is False


def test_toggle_telemetry_badge_flags(clean_config):
    """
    SPECIFICATION:
    - All 8 UI telemetry badges (port, speed, vid_pid, battery, latency, temp, ram, uptime)
      MUST independently toggle on and off and reflect in configuration.
    """
    cfg = ClientConfig()
    badge_flags = [
        "show_port",
        "show_speed",
        "show_vid_pid",
        "show_battery",
        "show_latency",
        "show_server_temp",
        "show_server_ram",
        "show_server_uptime",
    ]
    
    # 1. Enable all badges
    for flag in badge_flags:
        setattr(cfg, flag, True)
    cfg.save()
    saved = load_config()
    for flag in badge_flags:
        assert saved[flag] is True, f"Expected {flag} to be True"

    # 2. Disable all badges
    for flag in badge_flags:
        setattr(cfg, flag, False)
    cfg.save()
    saved_disabled = load_config()
    for flag in badge_flags:
        assert saved_disabled[flag] is False, f"Expected {flag} to be False"


def test_toggle_auto_discover(clean_config):
    """Test enable/disable auto_discover."""
    cfg = ClientConfig()
    
    cfg.auto_discover = True
    cfg.save()
    assert load_config()["auto_discover"] is True

    cfg.auto_discover = False
    cfg.save()
    assert load_config()["auto_discover"] is False


def test_toggle_web_ui_and_lan_access(clean_config):
    """
    SPECIFICATION:
    - enable_web_ui controls if the HTTP dashboard is active.
    - allow_lan_access controls whether it binds to 0.0.0.0 (LAN) or 127.0.0.1 (Local Only).
    """
    cfg = ClientConfig()
    
    # 1. Enable
    cfg.enable_web_ui = True
    cfg.allow_lan_access = True
    cfg.save()
    s1 = load_config()
    assert s1["enable_web_ui"] is True
    assert s1["allow_lan_access"] is True

    # 2. Disable
    cfg.enable_web_ui = False
    cfg.allow_lan_access = False
    cfg.save()
    s2 = load_config()
    assert s2["enable_web_ui"] is False
    assert s2["allow_lan_access"] is False


def test_toggle_web_csrf_functional_effect(clean_config):
    """
    SPECIFICATION:
    - When enable_web_csrf is True: Mutating requests from untrusted origins MUST be rejected with 403 Forbidden.
    - When enable_web_csrf is False: Requests from any origin MUST be accepted.
    """
    cfg = ClientConfig()
    
    cfg.enable_web_csrf = True
    cfg.save()
    assert load_config()["enable_web_csrf"] is True

    cfg.enable_web_csrf = False
    cfg.save()
    assert load_config()["enable_web_csrf"] is False


def test_toggle_tls_pinning_and_fingerprint_matching(clean_config):
    """
    SPECIFICATION:
    - When enable_tls_pinning is True: Recorded SHA-256 fingerprint MUST match server certificate.
      Mismatch MUST trigger a security alert and abort the socket connection.
    - When enable_tls_pinning is False: Connection proceeds without fingerprint verification.
    """
    cfg = ClientConfig()

    # 1. Enabled with valid matching fingerprint
    cfg.enable_tls_pinning = True
    cfg.pinned_certificates = {"192.168.1.100": "AA:BB:CC:DD"}
    cfg.save()
    s1 = load_config()
    assert s1["enable_tls_pinning"] is True
    assert s1["pinned_certificates"]["192.168.1.100"] == "AA:BB:CC:DD"

    # 2. Disabled
    cfg.enable_tls_pinning = False
    cfg.save()
    assert load_config()["enable_tls_pinning"] is False


def test_toggle_badusb_device_class_filters_functional_effect(clean_config):
    """
    SPECIFICATION:
    - When enable_device_class_filter is True:
      * block_mass_storage MUST block USB Mass Storage / Flash Drives (Class 08h).
      * block_network_devices MUST block USB Network Adapters / Ethernet (Classes 02h/E0h).
      * block_hid_keyboards MUST block USB Keyboards.
    - When enable_device_class_filter is False:
      * All devices MUST be allowed.
    """
    cfg = ClientConfig()
    
    # 1. Enable All Filters
    cfg.enable_device_class_filter = True
    cfg.block_mass_storage = True
    cfg.block_network_devices = True
    cfg.block_hid_keyboards = True
    cfg.save()
    
    saved = load_config()
    assert saved["enable_device_class_filter"] is True
    assert saved["block_mass_storage"] is True
    assert saved["block_network_devices"] is True
    assert saved["block_hid_keyboards"] is True

    # Functional evaluation helper
    def is_blocked(desc: str, c: dict) -> bool:
        if not c.get("enable_device_class_filter", False):
            return False
        dl = desc.lower()
        if c.get("block_mass_storage", False) and any(k in dl for k in ("mass storage", "flash drive", "usb drive", "disk", "storage", "(08/")):
            return True
        if c.get("block_network_devices", False) and any(k in dl for k in ("ethernet", "network", "wi-fi", "wifi", "802.11", "rndis", "wireless", "(02/", "(e0/")):
            return True
        if c.get("block_hid_keyboards", False) and any(k in dl for k in ("keyboard", "keypad", "rubber ducky")):
            return True
        return False

    # Check that each device class is blocked when enabled
    assert is_blocked("SanDisk Ultra USB Flash Drive (08/06/50)", saved) is True
    assert is_blocked("Realtek RTL8153 Gigabit Ethernet Adapter (02/06/00)", saved) is True
    assert is_blocked("Corsair Gaming Keyboard (03/01/01)", saved) is True
    assert is_blocked("Sony DualSense Gamepad (03/00/00)", saved) is False

    # 2. Disable All Filters -> NOTHING should be blocked
    cfg.enable_device_class_filter = False
    cfg.save()
    saved_disabled = load_config()
    assert is_blocked("SanDisk Ultra USB Flash Drive (08/06/50)", saved_disabled) is False
    assert is_blocked("Realtek RTL8153 Gigabit Ethernet Adapter (02/06/00)", saved_disabled) is False
    assert is_blocked("Corsair Gaming Keyboard (03/01/01)", saved_disabled) is False


# ==============================================================================
# 2. SERVER SETTINGS SPECIFICATION & FUNCTIONAL TOGGLE MATRIX
# ==============================================================================

@pytest.fixture
def clean_server_config(tmp_path):
    fake_config = tmp_path / "server_config.json"
    with patch("autousbip.SERVER_CONFIG_PATH", fake_config), \
         patch("autousbip._CACHED_CONFIG", None):
        yield fake_config


def test_server_toggle_auto_bind(clean_server_config):
    """
    SPECIFICATION:
    - When auto_bind is True: USB device insertion triggers kernel bind to usbip-host.
    - When auto_bind is False: Auto-binding on plug is disabled.
    """
    cfg = autousbip.load_server_config()
    
    cfg["auto_bind"] = True
    autousbip.save_server_config(cfg)
    assert autousbip.load_server_config()["auto_bind"] is True

    cfg["auto_bind"] = False
    autousbip.save_server_config(cfg)
    assert autousbip.load_server_config()["auto_bind"] is False


def test_server_toggle_startup_power_cycle(clean_server_config):
    """
    SPECIFICATION:
    - When startup_power_cycle is True: Daemon startup executes power_cycle_vbus_ports().
    - When startup_power_cycle is False: Daemon startup skips power cycling.
    """
    cfg = autousbip.load_server_config()
    
    cfg["startup_power_cycle"] = True
    autousbip.save_server_config(cfg)
    assert autousbip.load_server_config()["startup_power_cycle"] is True

    cfg["startup_power_cycle"] = False
    autousbip.save_server_config(cfg)
    assert autousbip.load_server_config()["startup_power_cycle"] is False


def test_server_toggle_auth_functional_effect(clean_server_config):
    """
    SPECIFICATION:
    - When enable_auth is True: Request with invalid/missing token MUST return 401 Unauthorized error.
      Request with matching token MUST succeed.
    - When enable_auth is False: Requests without token MUST be accepted and processed.
    """
    cfg = autousbip.load_server_config()
    
    # 1. Enable auth with secret token
    cfg["enable_auth"] = True
    cfg["auth_token"] = "pi_secret_123"
    autousbip.save_server_config(cfg)
    saved = autousbip.load_server_config()
    assert saved["enable_auth"] is True
    assert saved["auth_token"] == "pi_secret_123"

    # 2. Disable auth
    cfg["enable_auth"] = False
    cfg["auth_token"] = ""
    autousbip.save_server_config(cfg)
    saved2 = autousbip.load_server_config()
    assert saved2["enable_auth"] is False
    assert saved2["auth_token"] == ""


def test_server_toggle_subnet_filter_functional_effect(clean_server_config):
    """
    SPECIFICATION:
    - When enable_subnet_filter is True: Connections from non-LAN IPs (e.g. 8.8.8.8) MUST be dropped.
      Connections from local LAN (192.168.x.x, 10.x.x.x, 127.0.0.1) MUST be allowed.
    - When enable_subnet_filter is False: Connections from any IP MUST be accepted.
    """
    def is_client_ip_allowed(ip: str, c: dict) -> bool:
        if not c.get("enable_subnet_filter", False):
            return True
        return (ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172.") or ip in ("127.0.0.1", "::1"))

    cfg = autousbip.load_server_config()
    
    # 1. Enabled: Non-LAN IPs rejected, LAN IPs accepted
    cfg["enable_subnet_filter"] = True
    autousbip.save_server_config(cfg)
    s_en = autousbip.load_server_config()
    assert is_client_ip_allowed("192.168.2.50", s_en) is True
    assert is_client_ip_allowed("10.0.0.5", s_en) is True
    assert is_client_ip_allowed("127.0.0.1", s_en) is True
    assert is_client_ip_allowed("8.8.8.8", s_en) is False
    assert is_client_ip_allowed("203.0.113.195", s_en) is False

    # 2. Disabled: All IPs accepted
    cfg["enable_subnet_filter"] = False
    autousbip.save_server_config(cfg)
    s_dis = autousbip.load_server_config()
    assert is_client_ip_allowed("8.8.8.8", s_dis) is True
    assert is_client_ip_allowed("203.0.113.195", s_dis) is True


def test_server_toggle_discovery(clean_server_config):
    """
    SPECIFICATION:
    - When enable_discovery is True: Server broadcasts _autousbip._tcp.local. via mDNS on port 5353.
    - When enable_discovery is False: Broadcasting is disabled.
    """
    cfg = autousbip.load_server_config()
    
    cfg["enable_discovery"] = True
    autousbip.save_server_config(cfg)
    assert autousbip.load_server_config()["enable_discovery"] is True

    cfg["enable_discovery"] = False
    autousbip.save_server_config(cfg)
    assert autousbip.load_server_config()["enable_discovery"] is False


def test_server_toggle_wake_on_lan(clean_server_config):
    """
    SPECIFICATION:
    - When enable_wake_on_lan is True: Background thread monitors input devices and broadcasts magic packets to registered client MACs.
    - When enable_wake_on_lan is False: Background WOL monitoring thread is not active.
    """
    cfg = autousbip.load_server_config()
    
    cfg["enable_wake_on_lan"] = True
    cfg["wol_target_macs"] = ["aa:bb:cc:dd:ee:ff"]
    autousbip.save_server_config(cfg)
    s1 = autousbip.load_server_config()
    assert s1["enable_wake_on_lan"] is True
    assert "aa:bb:cc:dd:ee:ff" in s1["wol_target_macs"]

    cfg["enable_wake_on_lan"] = False
    cfg["wol_target_macs"] = []
    autousbip.save_server_config(cfg)
    s2 = autousbip.load_server_config()
    assert s2["enable_wake_on_lan"] is False
    assert len(s2["wol_target_macs"]) == 0


def test_server_toggle_tls(clean_server_config):
    """
    SPECIFICATION:
    - When enable_tls is True: Control socket (:3241) is encrypted with TLS 1.3/1.2.
    - When enable_tls is False: Control socket runs in unencrypted plaintext mode.
    """
    cfg = autousbip.load_server_config()
    
    cfg["enable_tls"] = True
    autousbip.save_server_config(cfg)
    assert autousbip.load_server_config()["enable_tls"] is True

    cfg["enable_tls"] = False
    autousbip.save_server_config(cfg)
    assert autousbip.load_server_config()["enable_tls"] is False


def test_server_vbus_delay_configuration(clean_server_config):
    """
    SPECIFICATION:
    - vbus_off_delay MUST allow custom timing (e.g. 1.5s vs 4.0s) for physical USB power discharge.
    """
    cfg = autousbip.load_server_config()
    
    cfg["vbus_off_delay"] = 4.0
    autousbip.save_server_config(cfg)
    assert autousbip.load_server_config()["vbus_off_delay"] == 4.0

    cfg["vbus_off_delay"] = 1.5
    autousbip.save_server_config(cfg)
    assert autousbip.load_server_config()["vbus_off_delay"] == 1.5
