"""Unified Gamepad Subsystem for Linux Joystick, PlayStation DualSense HID, and Soundboard."""
from .reader import (
    get_gamepad_battery_info,
    find_joystick_nodes_for_device,
    find_touchpad_event_node,
    find_motion_event_node,
    read_touchpad_state,
    read_motion_state,
    detect_gamepad_family,
    read_joystick_state,
    JSIOCGAXES,
    JSIOCGBUTTONS,
    JSIOCGAXMAP,
    JSIOCGBTNMAP,
)
from .dualsense import (
    build_dualsense_trigger_effect,
    send_playstation_output_report,
    unmute_playstation_speaker,
    find_dualsense_pipewire_sink,
    play_sound_test_chime,
)
from .sdl_db import (
    lookup_sdl_gamepad_mapping,
    get_synthesized_controller_name,
    get_sdl_controller_db,
    SDLGameControllerDB,
    SDLControllerMapping,
)
from .latency import (
    get_controller_latency,
    get_controller_latency_tracker,
    ControllerLatencyTracker,
)
from .jukebox import (
    play_konami_easter_egg,
    play_bad_apple_easter_egg,
    stop_active_easter_egg,
)

__all__ = [
    "get_gamepad_battery_info",
    "find_joystick_nodes_for_device",
    "find_touchpad_event_node",
    "find_motion_event_node",
    "read_touchpad_state",
    "read_motion_state",
    "detect_gamepad_family",
    "read_joystick_state",
    "build_dualsense_trigger_effect",
    "send_playstation_output_report",
    "unmute_playstation_speaker",
    "find_dualsense_pipewire_sink",
    "play_sound_test_chime",
    "play_konami_easter_egg",
    "play_bad_apple_easter_egg",
    "stop_active_easter_egg",
    "get_controller_latency",
    "get_controller_latency_tracker",
    "ControllerLatencyTracker",
    "lookup_sdl_gamepad_mapping",
    "get_synthesized_controller_name",
    "get_sdl_controller_db",
    "SDLGameControllerDB",
    "SDLControllerMapping",
    "JSIOCGAXES",
    "JSIOCGBUTTONS",
    "JSIOCGAXMAP",
    "JSIOCGBTNMAP",
]
