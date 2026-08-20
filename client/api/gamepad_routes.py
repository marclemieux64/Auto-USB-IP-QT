from __future__ import annotations

import logging
import threading
import time
from typing import Any
from core.gamepad import (
    get_controller_latency,
    find_joystick_nodes_for_device,
    read_joystick_state,
    detect_gamepad_family,
    get_gamepad_battery_info,
    find_touchpad_event_node,
    read_touchpad_state,
    find_motion_event_node,
    read_motion_state,
    send_playstation_output_report,
    build_dualsense_trigger_effect,
    play_sound_test_chime,
    play_konami_easter_egg,
)

logger = logging.getLogger("auto-usbip-client")


def handle_gamepad_state(controller: Any, port: str) -> dict:
    """Read instant real-time telemetry from gamepad nodes."""
    norm_p = str(int(port)) if str(port).isdigit() else str(port)
    dev = next((d for d in controller.scanner.imported_devices if (str(d.port) == str(port) or (str(d.port).isdigit() and str(int(d.port)) == norm_p))), None)
    
    vid, pid = 0, 0
    clean_name = "Gamepad"
    desc_str = "Gamepad"
    if dev:
        from core.usbip import get_port_to_bus_map
        port_map = get_port_to_bus_map()
        s_ip, b_id = port_map.get(str(dev.port), ("", getattr(dev, "bus_id", "")))
        bus_id_str = b_id or getattr(dev, "bus_id", str(dev.port))
        desc_str = getattr(dev, "description", getattr(dev, "desc", getattr(dev, "raw_desc", "USB Device")))
        raw_desc_str = getattr(dev, "raw_desc", desc_str)

        if hasattr(controller, "usb_db"):
            clean_name = controller.usb_db.get_device_name(bus_id_str, desc_str)
            vid, pid = controller.usb_db.parse_vid_pid_from_string(raw_desc_str or desc_str)
        else:
            clean_name = desc_str

        if (not vid or not pid) and hasattr(dev, "vid_pid"):
            raw_vp = getattr(dev, "vid_pid", "")
            if raw_vp and ":" in raw_vp:
                try:
                    parts = raw_vp.replace("(", "").replace(")", "").strip().split(":")
                    vid, pid = int(parts[0], 16), int(parts[1], 16)
                except Exception:
                    pass

    nodes = find_joystick_nodes_for_device(port, is_vhci=True, vid=vid if vid else None, pid=pid if pid else None)
    js_node = next((n for n in nodes if "/js" in n), None)
    hidraw_node = next((n for n in nodes if "/hidraw" in n), None)

    if not js_node:
        return {"status": "error", "message": "No joystick device node found for this port"}

    js_data = read_joystick_state(js_node)
    if not js_data:
        return {"status": "error", "message": "Failed to read joystick device state"}

    # Priority 1: Query community SDL_GameControllerDB
    from core.gamepad import lookup_sdl_gamepad_mapping
    sdl_m = lookup_sdl_gamepad_mapping(vid=vid, pid=pid, dev_name=desc_str or clean_name)

    if sdl_m:
        family = sdl_m.family
        detected_title = sdl_m.name
        controller_type = sdl_m.controller_type
    else:
        # Priority 2: Fallback dynamic capability scan
        family, detected_title, controller_type = detect_gamepad_family(desc_str if desc_str != "Gamepad" else clean_name, vid, pid)
    
    # Priority for display title:
    # 1. Nickname (if set by user)
    # 2. lsusb hardware name (e.g. "Gembird Generic 4-button NES USB Controller")
    # 3. detected_title / js_data name
    title = clean_name if (clean_name and clean_name not in ("Gamepad", "USB Device", "2Axes 11Keys Game  Pad")) else (desc_str if (desc_str and desc_str not in ("Gamepad", "USB Device", "2Axes 11Keys Game  Pad")) else detected_title)
    
    if dev and controller.config.enable_nicknames:
        id_key = f"{vid:04x}:{pid:04x}" if (vid and pid) else dev.port
        if id_key in controller.config.nicknames:
            title = controller.config.nicknames[id_key]

    has_touchpad = (family == "playstation") or (vid == 0x054C) or "touchpad" in js_data["name"].lower() or "dualsense" in js_data["name"].lower()
    has_motion = (family == "playstation")
    is_dualsense = "dualsense" in title.lower() or (vid == 0x054C and pid in (0x0CE6, 0x0DF2))

    # Button Layout Labels (Priority: SDL_GameControllerDB -> Fallback Dynamic Layout)
    num_btns = js_data["num_buttons"]
    if sdl_m:
        button_labels = sdl_m.get_button_labels(num_btns)
    elif family == "playstation":
        ps_names = ["Cross (✕)", "Circle (◯)", "Square (□)", "Triangle (△)", "L1", "R1", "L2", "R2", "Create / Share", "Options", "PS", "L3", "R3"]
        for i in range(num_btns):
            button_labels.append({"index": i, "label": ps_names[i] if i < len(ps_names) else f"Btn {i}", "alt": f"B{i}"})
        if is_dualsense:
            button_labels.append({"index": len(button_labels), "label": "Mic Mute", "alt": "Mic"})
    elif family == "xbox":
        btn_map = js_data.get("button_map", [])
        evdev_to_name = {
            0x130: "A",                    # BTN_SOUTH / BTN_A
            0x131: "B",                    # BTN_EAST / BTN_B
            0x132: "C",                    # BTN_C
            0x133: "X",                    # BTN_NORTH / BTN_X
            0x134: "Y",                    # BTN_WEST / BTN_Y
            0x135: "Z",                    # BTN_Z
            0x136: "LB",                   # BTN_TL
            0x137: "RB",                   # BTN_TR
            0x138: "LT",                   # BTN_TL2
            0x139: "RT",                   # BTN_TR2
            0x13A: "View / Back",          # BTN_SELECT
            0x13B: "Menu / Start",         # BTN_START
            0x13C: "Xbox",                 # BTN_MODE / Guide
            0x13D: "LS",                   # BTN_THUMBL
            0x13E: "RS",                   # BTN_THUMBR
            0x2C0: "Share",                # BTN_TRIGGER_HAPPY1
        }
        # Standard Linux xpad driver button order:
        # B0=A, B1=B, B2=X, B3=Y, B4=LB, B5=RB, B6=View/Back, B7=Menu/Start, B8=Xbox, B9=LS, B10=RS, B11=Share
        xb_fallback = ["A", "B", "X", "Y", "LB", "RB", "View / Back", "Menu / Start", "Xbox", "LS", "RS", "Share"]
        for i in range(num_btns):
            code = btn_map[i] if i < len(btn_map) else None
            lbl = evdev_to_name.get(code) if code in evdev_to_name else (xb_fallback[i] if i < len(xb_fallback) else f"Btn {i}")
            button_labels.append({"index": i, "label": lbl, "alt": f"B{i}"})
    elif family == "nintendo":
        btn_map = js_data.get("button_map", [])
        evdev_to_name_nintendo = {
            0x130: "B",                    # BTN_SOUTH (B on Nintendo)
            0x131: "A",                    # BTN_EAST (A on Nintendo)
            0x133: "X",                    # BTN_NORTH (X on Nintendo)
            0x134: "Y",                    # BTN_WEST (Y on Nintendo)
            0x136: "L",                    # BTN_TL
            0x137: "R",                    # BTN_TR
            0x138: "ZL",                   # BTN_TL2
            0x139: "ZR",                   # BTN_TR2
            0x13A: "Minus (-)",            # BTN_SELECT
            0x13B: "Plus (+)",             # BTN_START
            0x13C: "Home",                 # BTN_MODE
            0x13D: "LS",                   # BTN_THUMBL
            0x13E: "RS",                   # BTN_THUMBR
            0x2C0: "Capture",              # BTN_TRIGGER_HAPPY1
        }
        if "nes" in title.lower() or vid == 0x12BD or "gembird" in title.lower() or "2axes" in js_data["name"].lower():
            # Standard USB NES/Retro clone IC PCB mapping:
            # B0 = X (Top)
            # B1 = A (Right)
            # B2 = B (Bottom)
            # B3 = Y (Left)
            # B8 = Select
            # B9 = Start
            nes_names = {0: "X", 1: "A", 2: "B", 3: "Y", 8: "Select", 9: "Start"}
            for i in range(num_btns):
                lbl = nes_names.get(i, f"B{i}")
                button_labels.append({"index": i, "label": lbl, "alt": f"B{i}"})
        elif "snes" in title.lower():
            # Standard USB SNES clone IC PCB mapping:
            # B0 = X, B1 = A, B2 = B, B3 = Y, B4 = L, B5 = R, B8 = Select, B9 = Start
            snes_names = {0: "X", 1: "A", 2: "B", 3: "Y", 4: "L", 5: "R", 8: "Select", 9: "Start"}
            for i in range(num_btns):
                lbl = snes_names.get(i, f"B{i}")
                button_labels.append({"index": i, "label": lbl, "alt": f"B{i}"})
        else:
            switch_fallback = ["B", "A", "Y", "X", "L", "R", "ZL", "ZR", "Minus (-)", "Plus (+)", "LS", "RS", "Home", "Capture"]
            for i in range(num_btns):
                code = btn_map[i] if i < len(btn_map) else None
                lbl = evdev_to_name_nintendo.get(code) if code in evdev_to_name_nintendo else (switch_fallback[i] if i < len(switch_fallback) else f"Btn {i}")
                button_labels.append({"index": i, "label": lbl, "alt": f"B{i}"})
    else:
        for i in range(num_btns):
            button_labels.append({"index": i, "label": f"Button {i}", "alt": f"B{i}"})

    axes = js_data["axes"]
    buttons = list(js_data["buttons"])
    if is_dualsense and hidraw_node:
        from core.gamepad.dualsense import read_dualsense_mic_button
        mic_pressed = read_dualsense_mic_button(hidraw_node)
        buttons.append(mic_pressed)

    # Dynamic SDL DB capabilities & axis/dpad evaluation
    if sdl_m:
        caps = sdl_m.get_capabilities()
        has_dpad = caps["has_dpad"]
        has_left_stick = caps["has_left_stick"]
        has_right_stick = caps["has_right_stick"]
        has_triggers = caps["has_triggers"]
        has_touchpad = caps["has_touchpad"]
        has_accel = caps.get("has_accel", False)
        has_gyro = caps.get("has_gyro", False)
        has_motion = caps.get("has_motion", False)

        dpad_x, dpad_y = sdl_m.evaluate_dpad(axes, buttons)
        left_stick_x, left_stick_y, right_stick_x, right_stick_y, trigger_l, trigger_r = sdl_m.evaluate_sticks_and_triggers(axes)
    else:
        has_dpad = True
        has_left_stick = len(axes) >= 2
        has_right_stick = len(axes) >= 4
        has_triggers = len(axes) >= 6
        has_accel = has_motion
        has_gyro = has_motion
        
        # Normalize fallback axes mappings
        left_stick_x = axes[0] if len(axes) > 0 else 0.0
        left_stick_y = axes[1] if len(axes) > 1 else 0.0
        right_stick_x = axes[3] if len(axes) > 3 else (axes[2] if len(axes) > 2 else 0.0)
        right_stick_y = axes[4] if len(axes) > 4 else (axes[3] if len(axes) > 3 else 0.0)

        def norm_trig(val: float) -> float:
            return max(0.0, min(1.0, (val + 1.0) / 2.0))

        trigger_l = norm_trig(axes[2]) if len(axes) > 2 else 0.0
        trigger_r = norm_trig(axes[5]) if len(axes) > 5 else 0.0
        dpad_x = axes[6] if len(axes) > 6 else 0.0
        dpad_y = axes[7] if len(axes) > 7 else 0.0

    # Touchpad read with 2-finger multi-touch
    tp_x, tp_y, tp_active, tp_click = 0.5, 0.5, False, False
    tp_multi = {
        "f1": {"x": 0.5, "y": 0.5, "active": False},
        "f2": {"x": 0.5, "y": 0.5, "active": False},
        "click": False,
        "finger_count": 0,
        "zone": "None",
    }
    if has_touchpad:
        from core.touchpad_control import find_touchpad_node_for_port, read_touchpad_multi_touch
        tp_node = find_touchpad_node_for_port(port, vid, pid) or find_touchpad_event_node(vid, pid, vid != 0)
        if tp_node:
            tp_multi = read_touchpad_multi_touch(tp_node)
            tp_x = tp_multi["f1"]["x"]
            tp_y = tp_multi["f1"]["y"]
            tp_active = (tp_multi["finger_count"] > 0)
            tp_click = tp_multi["click"]

    # Motion sensors read
    motion_values = [0.0] * 6
    if has_motion:
        motion_node = find_motion_event_node(vid, pid, vid != 0)
        if motion_node:
            motion_values = read_motion_state(motion_node)

    lat_info = get_controller_latency(port, vid if vid else None, pid if pid else None)
    bat_desc = None
    b_info = get_gamepad_battery_info(vid if vid else None, pid if pid else None)
    if b_info:
        bat_desc = b_info[1]

    from core.touchpad_control import is_touchpad_mouse_enabled
    tp_mouse_enabled = is_touchpad_mouse_enabled(port) if has_touchpad else True

    return {
        "status": "ok",
        "clean_name": title,
        "controller_type": controller_type,
        "family": family,
        "is_dualsense": is_dualsense,
        "has_dpad": has_dpad,
        "has_left_stick": has_left_stick,
        "has_right_stick": has_right_stick,
        "has_triggers": has_triggers,
        "has_touchpad": has_touchpad,
        "touchpad_mouse_enabled": tp_mouse_enabled,
        "has_motion": has_motion,
        "has_accel": has_accel,
        "has_gyro": has_gyro,
        "has_adaptive_triggers": is_dualsense,
        "has_rgb_led": (is_dualsense or family == "playstation"),
        "has_rumble": True,
        "battery": bat_desc,
        "latency_ms": lat_info.get("latency_ms"),
        "polling_hz": lat_info.get("polling_hz"),
        "latency_str": lat_info.get("latency_str"),
        "button_labels": button_labels,
        "state": {
            "left_stick_x": round(left_stick_x, 2),
            "left_stick_y": round(left_stick_y, 2),
            "right_stick_x": round(right_stick_x, 2),
            "right_stick_y": round(right_stick_y, 2),
            "trigger_l": round(trigger_l, 2),
            "trigger_r": round(trigger_r, 2),
            "dpad_x": round(dpad_x, 2),
            "dpad_y": round(dpad_y, 2),
            "touchpad_x": round(tp_x, 2),
            "touchpad_y": round(tp_y, 2),
            "touchpad_active": tp_active,
            "touchpad_click": tp_click,
            "touchpad_multi": tp_multi,
            "motion": motion_values,
            "buttons": {str(i): buttons[i] for i in range(len(buttons))}
        }
    }


def handle_gamepad_control(controller: Any, query: dict) -> dict:
    """Dispatch hardware commands (LED, player, mute, rumble, sound, adaptive triggers) to gamepad."""
    port = query.get("port", [""])[0]
    action = query.get("action", ["set_led"])[0]
    dev = next((d for d in controller.scanner.imported_devices if str(d.port) == str(port)), None)

    vid, pid = 0, 0
    if dev:
        desc_str = getattr(dev, "desc", getattr(dev, "raw_desc", "USB Device"))
        vid, pid = controller.usb_db.parse_vid_pid_from_string(getattr(dev, "raw_desc", desc_str))

    nodes = find_joystick_nodes_for_device(port, is_vhci=True, vid=vid if vid else None, pid=pid if pid else None)
    hidraw_path = next((n for n in nodes if "/hidraw" in n), "/dev/hidraw15")

    if action == "toggle_touchpad_mouse":
        from core.touchpad_control import set_touchpad_mouse_enabled, is_touchpad_mouse_enabled
        enabled_val = query.get("enabled", [None])[0]
        if enabled_val is None:
            enabled = not is_touchpad_mouse_enabled(port)
        elif isinstance(enabled_val, bool):
            enabled = enabled_val
        elif str(enabled_val).isdigit():
            enabled = bool(int(enabled_val))
        else:
            enabled = str(enabled_val).lower() in ("true", "1", "yes")
        ok = set_touchpad_mouse_enabled(port, enabled)
        current = is_touchpad_mouse_enabled(port)
        return {"status": "ok" if ok else "error", "port": port, "touchpad_mouse_enabled": current}

    elif action == "sound_test":
        played = play_sound_test_chime(hidraw_path)
        return {"status": "ok", "played": played}

    elif action == "konami_egg":
        played, title = play_konami_easter_egg(track_name=None, hidraw_path=hidraw_path)
        return {"status": "ok", "title": title, "played": played}

    r = int(query.get("r", [0])[0])
    g = int(query.get("g", [100])[0])
    b = int(query.get("b", [255])[0])
    player = int(query.get("player", [1])[0])
    mic_mute = bool(int(query.get("mic_mute", [0])[0]))

    trigger_mode = query.get("trigger_mode", [None])[0]
    trigger_target = query.get("trigger_target", ["both"])[0]
    force = int(query.get("force", [255])[0])
    start_pos = int(query.get("start_pos", [32])[0])
    end_pos = int(query.get("end_pos", [224])[0])
    freq = int(query.get("freq", [15])[0])

    trigger_r = None
    trigger_l = None
    if trigger_mode is not None:
        trig_payload = build_dualsense_trigger_effect(trigger_mode, force=force, start_pos=start_pos, end_pos=end_pos, freq=freq)
        if trigger_target in ("both", "r2"):
            trigger_r = trig_payload
        if trigger_target in ("both", "l2"):
            trigger_l = trig_payload

    if action == "rumble_pulse":
        send_playstation_output_report(hidraw_path, r=r, g=g, b=b, player=player, rumble_l=220, rumble_r=220, mic_mute=mic_mute, trigger_r=trigger_r, trigger_l=trigger_l)
        def stop_rumble():
            time.sleep(0.25)
            send_playstation_output_report(hidraw_path, r=r, g=g, b=b, player=player, rumble_l=0, rumble_r=0, mic_mute=mic_mute, trigger_r=trigger_r, trigger_l=trigger_l)
        threading.Thread(target=stop_rumble, daemon=True).start()
        return {"status": "ok", "message": "Rumble pulse triggered"}
    else:
        ok = send_playstation_output_report(
            hidraw_path,
            r=r,
            g=g,
            b=b,
            player=player,
            mic_mute=mic_mute,
            trigger_r=trigger_r,
            trigger_l=trigger_l
        )
        return {"status": "ok" if ok else "warning", "message": "PlayStation report sent"}
