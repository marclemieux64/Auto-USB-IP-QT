import sys
import struct
import tempfile
import pytest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "client"))

from config import ClientConfig
from core.gamepad.dualsense import (
    build_dualsense_trigger_effect,
    send_playstation_output_report,
    _OUTPUT_REPORT_BUF,
)
from core.gamepad.sdl_db import (
    lookup_sdl_gamepad_mapping,
    SDLControllerMapping,
)
from core.gamepad.reader import detect_gamepad_family
from core.gamepad.latency import (
    ControllerLatencyTracker,
    EVENT_FORMAT,
    EVENT_SIZE,
)
from api.gamepad_routes import (
    handle_gamepad_state,
    handle_gamepad_control,
)


def test_sdl_controller_mapping_lookup():
    """Verify lookup_sdl_gamepad_mapping recognizes known controllers from SDL GameControllerDB."""
    # Sony DualSense (054c:0ce6)
    mapping = lookup_sdl_gamepad_mapping(vid=0x054C, pid=0x0CE6, dev_name="Sony DualSense")
    assert mapping is not None
    assert mapping.family == "playstation"
    assert "PS5" in mapping.name or "DualSense" in mapping.name or "PlayStation" in mapping.name
    labels = mapping.get_button_labels(16)
    assert any("Cross" in (l.get("label") if isinstance(l, dict) else str(l)) for l in labels)

    # Xbox 360 / One Controller (045e:028e)
    xbox_mapping = lookup_sdl_gamepad_mapping(vid=0x045E, pid=0x028E, dev_name="Xbox 360 Controller")
    assert xbox_mapping is not None
    assert xbox_mapping.family == "xbox"
    xbox_labels = xbox_mapping.get_button_labels(16)
    assert any("A" in (l.get("label") if isinstance(l, dict) else str(l)) for l in xbox_labels)

    # Nintendo Switch Pro Controller (057e:2009)
    switch_mapping = lookup_sdl_gamepad_mapping(vid=0x057E, pid=0x2009, dev_name="Nintendo Switch Pro Controller")
    assert switch_mapping is not None
    assert switch_mapping.family == "nintendo"


def test_detect_gamepad_family_fallback():
    """Verify detect_gamepad_family identifies families from names and VID/PID."""
    fam, title, ctype = detect_gamepad_family("Sony Interactive Entertainment DualSense", vid=0x054C, pid=0x0CE6)
    assert fam == "playstation"
    assert "PS5" in title or "DualSense" in title or "PlayStation" in title

    fam_x, title_x, ctype_x = detect_gamepad_family("Microsoft Xbox Controller", vid=0x045E, pid=0x02EA)
    assert fam_x == "xbox"


def test_dualsense_trigger_effect_builder():
    """Verify build_dualsense_trigger_effect generates valid motor payloads and clamps values."""
    # 1. Mode OFF
    off_eff = build_dualsense_trigger_effect("off")
    assert off_eff["mode"] == 0x00

    # 2. Mode BOW / Archery
    bow_eff = build_dualsense_trigger_effect("bow", force=200)
    assert bow_eff["mode"] == 0x01
    assert bow_eff["p2"] == 200

    # 3. Mode GUN / Weapon Section
    gun_eff = build_dualsense_trigger_effect("gun", force=255, start_pos=50, end_pos=210)
    assert gun_eff["mode"] == 0x02
    assert gun_eff["p1"] == 50
    assert gun_eff["p2"] == 210
    assert gun_eff["p3"] == 255

    # 4. Mode MACHINE_GUN / Rapid vibration
    vibe_eff = build_dualsense_trigger_effect("vibrate", force=180, freq=25)
    assert vibe_eff["mode"] == 0x06
    assert vibe_eff["p2"] == 180
    assert vibe_eff["p3"] == 25

    # 5. Mode ABS / Brakes
    abs_eff = build_dualsense_trigger_effect("abs", force=220)
    assert abs_eff["mode"] == 0x06
    assert abs_eff["p3"] == 28

    # 6. Mode HEAVY / Resistance
    heavy_eff = build_dualsense_trigger_effect("heavy", force=150, start_pos=30)
    assert heavy_eff["mode"] == 0x01
    assert heavy_eff["p1"] == 30
    assert heavy_eff["p2"] == 150

    # 7. Clamping: force > 255 clamped to 255, negative clamped to 0
    clamped = build_dualsense_trigger_effect("bow", force=999)
    assert clamped["p2"] == 255
    clamped_neg = build_dualsense_trigger_effect("bow", force=-50)
    assert clamped_neg["p2"] == 0


def test_dualsense_output_report_generation(tmp_path):
    """Verify send_playstation_output_report structures the 63-byte USB HID report 0x02."""
    fake_hidraw = tmp_path / "hidraw_test"
    fake_hidraw.touch()

    written_payloads = []
    def mock_write(fd, data):
        written_payloads.append(bytes(data))
        return len(data)

    with patch("os.open", return_value=99), \
         patch("os.write", side_effect=mock_write), \
         patch("os.close"):
        
        trigger_right = build_dualsense_trigger_effect("gun", force=200, start_pos=40, end_pos=180)
        ok = send_playstation_output_report(
            str(fake_hidraw),
            r=255, g=50, b=0,
            player=1,
            rumble_l=120, rumble_r=180,
            mic_mute=True,
            trigger_r=trigger_right,
        )
        assert ok is True
        assert len(written_payloads) == 1
        buf = written_payloads[0]

        # Byte 0: Report ID = 0x02
        assert buf[0] == 0x02
        # Byte 1: Valid Flags 0 (Audio + Rumble + Right Trigger)
        assert (buf[1] & 0x03) == 0x03  # Rumble enable
        assert (buf[1] & 0x04) == 0x04  # Right trigger enable
        # Byte 3 & 4: Rumble motors
        assert buf[3] == 180
        assert buf[4] == 120
        # Byte 9: Mic Mute Amber LED (1 = Solid Amber)
        assert buf[9] == 1
        # Bytes 11-14: Right Adaptive Trigger parameters
        assert buf[11] == 0x02  # Gun mode
        assert buf[12] == 40    # Start pos
        assert buf[13] == 180   # End pos
        assert buf[14] == 200   # Force
        # Bytes 45-47: RGB Lightbar
        assert buf[45] == 255   # Red
        assert buf[46] == 50    # Green
        assert buf[47] == 0     # Blue


def test_controller_latency_tracker_struct():
    """Verify ControllerLatencyTracker calculates correct event size and formats."""
    assert EVENT_SIZE in (16, 24)
    tracker = ControllerLatencyTracker()
    assert isinstance(tracker._nodes, dict)
    assert isinstance(tracker._port_to_node, dict)


def test_handle_gamepad_control_dispatch():
    """Verify handle_gamepad_control handles rumble, LEDs, adaptive triggers, and sound chime."""
    mock_ctrl = MagicMock()
    mock_ctrl.config = ClientConfig()
    dev = SimpleNamespace(port="1", bus_id="1-1.2", desc="Sony DualSense", raw_desc="Sony DualSense (054c:0ce6)")
    mock_ctrl.scanner.imported_devices = [dev]
    mock_ctrl.usb_db.parse_vid_pid_from_string.return_value = (0x054C, 0x0CE6)

    # 1. Action: set_led + trigger effect
    query_led = {
        "port": ["1"],
        "action": ["set_led"],
        "r": ["10"],
        "g": ["200"],
        "b": ["255"],
        "player": ["2"],
        "mic_mute": ["1"],
        "trigger_mode": ["gun"],
        "trigger_target": ["r2"],
        "force": ["220"],
    }
    with patch("api.gamepad_routes.find_joystick_nodes_for_device", return_value=["/dev/input/js0", "/dev/hidraw0"]), \
         patch("api.gamepad_routes.send_playstation_output_report", return_value=True) as mock_send_report:
        
        res = handle_gamepad_control(mock_ctrl, query_led)
        assert res["status"] == "ok"
        mock_send_report.assert_called_once()
        kwargs = mock_send_report.call_args[1]
        assert kwargs["r"] == 10
        assert kwargs["g"] == 200
        assert kwargs["b"] == 255
        assert kwargs["player"] == 2
        assert kwargs["mic_mute"] is True
        assert kwargs["trigger_r"]["mode"] == 0x02

    # 2. Action: rumble_pulse
    query_rumble = {"port": ["1"], "action": ["rumble_pulse"]}
    with patch("api.gamepad_routes.find_joystick_nodes_for_device", return_value=["/dev/input/js0", "/dev/hidraw0"]), \
         patch("api.gamepad_routes.send_playstation_output_report", return_value=True):
        res_r = handle_gamepad_control(mock_ctrl, query_rumble)
        assert res_r["status"] == "ok"
        assert "Rumble pulse" in res_r["message"]

    # 3. Action: sound_test
    query_sound = {"port": ["1"], "action": ["sound_test"]}
    with patch("api.gamepad_routes.find_joystick_nodes_for_device", return_value=["/dev/input/js0", "/dev/hidraw0"]), \
         patch("api.gamepad_routes.play_sound_test_chime", return_value=True):
        res_s = handle_gamepad_control(mock_ctrl, query_sound)
        assert res_s["status"] == "ok"
        assert res_s["played"] is True
