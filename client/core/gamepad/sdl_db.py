from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger("auto-usbip-client")


class SDLControllerMapping:
    """Represents a parsed controller mapping entry from SDL_GameControllerDB."""

    def __init__(self, guid: str, name: str, mapping_str: str, platform: str = "Linux"):
        self.guid = guid
        self.name = name
        self.combined_name = name
        self.raw_mapping = mapping_str
        self.platform = platform
        self.bindings: dict[str, str] = {}
        self.family = "generic"
        self.controller_type = "Generic – HID Gamepad"
        self._parse()

    def _parse(self):
        parts = self.raw_mapping.split(",")
        for p in parts:
            p = p.strip()
            if not p or ":" not in p:
                continue
            key, val = p.split(":", 1)
            self.bindings[key.strip()] = val.strip()

        # Classify family & subtype
        n_lower = (self.name or "").lower()
        if any(k in n_lower for k in ("ps5", "dualsense", "playstation 5", "ps4", "dualshock", "ps3", "sixaxis", "sony")):
            self.family = "playstation"
            if "dualsense" in n_lower or "ps5" in n_lower:
                self.controller_type = "PlayStation – DualSense"
            elif "ps4" in n_lower or "dualshock 4" in n_lower:
                self.controller_type = "PlayStation – DualShock 4"
            elif "ps3" in n_lower:
                self.controller_type = "PlayStation – DualShock 3"
            else:
                self.controller_type = "PlayStation – Compatible"
        elif any(k in n_lower for k in ("xbox", "x-box", "microsoft", "xinput")):
            self.family = "xbox"
            if "series" in n_lower:
                self.controller_type = "Xbox – Series X/S"
            elif "one" in n_lower:
                self.controller_type = "Xbox – One"
            elif "360" in n_lower:
                self.controller_type = "Xbox – 360"
            else:
                self.controller_type = "Xbox – Compatible"
        elif any(k in n_lower for k in ("nintendo", "switch", "nes", "snes", "famicom", "gamecube", "wii", "n64", "joy-con", "8bitdo", "retrolink", "tomee", "retro")):
            self.family = "nintendo"
            if "snes" in n_lower or "super" in n_lower:
                self.controller_type = "Nintendo – SNES"
            elif "nes" in n_lower or "famicom" in n_lower or "tomee" in n_lower or "retrolink" in n_lower:
                self.controller_type = "Nintendo – NES"
            elif "switch" in n_lower or "joy-con" in n_lower:
                self.controller_type = "Nintendo – Switch Pro"
            elif "gamecube" in n_lower:
                self.controller_type = "Nintendo – GameCube"
            elif "wii" in n_lower:
                self.controller_type = "Nintendo – Wii"
            elif "n64" in n_lower:
                self.controller_type = "Nintendo – N64"
            else:
                self.controller_type = "Nintendo – Compatible"

    def get_capabilities(self) -> dict[str, bool]:
        """Detect what physical controls are present on the hardware according to SDL DB."""
        has_dp = any(k in self.bindings for k in ("dpup", "dpdown", "dpleft", "dpright")) or True
        has_ls = any(k in self.bindings for k in ("leftx", "lefty", "leftstick"))
        has_rs = any(k in self.bindings for k in ("rightx", "righty", "rightstick"))
        has_tr = any(k in self.bindings for k in ("lefttrigger", "righttrigger"))
        has_tp = "touchpad" in self.bindings or self.family == "playstation"
        has_acc = "accel" in self.bindings or (self.family in ("playstation", "nintendo") and not any(r in (self.name or "").lower() for r in ("nes", "snes", "n64", "gamecube")))
        has_gyr = "gyro" in self.bindings or (self.family in ("playstation", "nintendo") and not any(r in (self.name or "").lower() for r in ("nes", "snes", "n64", "gamecube")))

        return {
            "has_dpad": has_dp,
            "has_left_stick": has_ls,
            "has_right_stick": has_rs,
            "has_triggers": has_tr,
            "has_touchpad": has_tp,
            "has_accel": has_acc,
            "has_gyro": has_gyr,
            "has_motion": has_acc or has_gyr,
        }

    def evaluate_dpad(self, axes: list[float], buttons: list[int]) -> tuple[float, float]:
        """Evaluate D-pad X & Y by honoring axes, buttons, or hat mappings in SDL DB."""
        dp_x, dp_y = 0.0, 0.0

        # D-pad X
        l_bind = self.bindings.get("dpleft", "")
        r_bind = self.bindings.get("dpright", "")
        if l_bind.startswith("-a") and r_bind.startswith("+a"):
            ax_idx = int(l_bind[2:])
            if ax_idx < len(axes):
                dp_x = axes[ax_idx]
        elif l_bind.startswith("b") and r_bind.startswith("b"):
            lb_idx = int(l_bind[1:])
            rb_idx = int(r_bind[1:])
            if rb_idx < len(buttons) and buttons[rb_idx]:
                dp_x = 1.0
            elif lb_idx < len(buttons) and buttons[lb_idx]:
                dp_x = -1.0
        elif "h0." in l_bind and len(axes) > 6:
            dp_x = axes[6]

        # D-pad Y
        u_bind = self.bindings.get("dpup", "")
        d_bind = self.bindings.get("dpdown", "")
        if u_bind.startswith("-a") and d_bind.startswith("+a"):
            ax_idx = int(u_bind[2:])
            if ax_idx < len(axes):
                dp_y = axes[ax_idx]
        elif u_bind.startswith("b") and d_bind.startswith("b"):
            ub_idx = int(u_bind[1:])
            db_idx = int(d_bind[1:])
            if db_idx < len(buttons) and buttons[db_idx]:
                dp_y = 1.0
            elif ub_idx < len(buttons) and buttons[ub_idx]:
                dp_y = -1.0
        elif "h0." in u_bind and len(axes) > 7:
            dp_y = axes[7]

        return round(dp_x, 2), round(dp_y, 2)

    def evaluate_sticks_and_triggers(self, axes: list[float]) -> tuple[float, float, float, float, float, float]:
        """Evaluate analog sticks and triggers according to SDL DB mapping and Linux joydev layout."""
        caps = self.get_capabilities()
        lx, ly = 0.0, 0.0
        rx, ry = 0.0, 0.0
        tl, tr = 0.0, 0.0

        def norm_trigger(val: float) -> float:
            return max(0.0, min(1.0, (val + 1.0) / 2.0))

        if caps["has_left_stick"]:
            lx = axes[0] if len(axes) > 0 else 0.0
            ly = axes[1] if len(axes) > 1 else 0.0

        if caps["has_right_stick"]:
            if len(axes) > 4:
                rx = axes[3]
                ry = axes[4]
            elif len(axes) > 3:
                rx = axes[2]
                ry = axes[3]

        if caps["has_triggers"]:
            if len(axes) > 5:
                tl = norm_trigger(axes[2])
                tr = norm_trigger(axes[5])
            elif len(axes) > 2:
                tl = norm_trigger(axes[2])

        return round(lx, 2), round(ly, 2), round(rx, 2), round(ry, 2), round(tl, 2), round(tr, 2)

    def get_button_labels(self, num_buttons: int = 16) -> list[dict[str, Any]]:
        """Generate accurate, human-readable button labels for ONLY the buttons physically present."""
        btn_to_sdl = {}
        for sdl_key, val in self.bindings.items():
            if val.startswith("b") and val[1:].isdigit():
                btn_idx = int(val[1:])
                btn_to_sdl[btn_idx] = sdl_key

        labels = []
        if self.family == "playstation":
            sdl_to_ps = {
                "a": "Cross (✕)",
                "b": "Circle (◯)",
                "x": "Square (□)",
                "y": "Triangle (△)",
                "leftshoulder": "L1",
                "rightshoulder": "R1",
                "lefttrigger": "L2",
                "righttrigger": "R2",
                "back": "Create / Share",
                "start": "Options",
                "guide": "PS",
                "leftstick": "L3",
                "rightstick": "R3",
                "touchpad": "Touchpad Click",
                "misc1": "Mic Mute",
            }
            for i in range(num_buttons):
                sdl_name = btn_to_sdl.get(i)
                lbl = sdl_to_ps.get(sdl_name) if sdl_name else None
                if not lbl:
                    ps_default = ["Cross (✕)", "Circle (◯)", "Square (□)", "Triangle (△)", "L1", "R1", "L2", "R2", "Create / Share", "Options", "PS", "L3", "R3"]
                    lbl = ps_default[i] if i < len(ps_default) else f"Button {i}"
                labels.append({"index": i, "label": lbl, "alt": f"B{i}"})
            if "dualsense" in self.controller_type.lower():
                labels.append({"index": len(labels), "label": "Mic Mute", "alt": "Mic"})

        elif self.family == "xbox":
            sdl_to_xb = {
                "a": "A",
                "b": "B",
                "x": "X",
                "y": "Y",
                "leftshoulder": "LB",
                "rightshoulder": "RB",
                "lefttrigger": "LT",
                "righttrigger": "RT",
                "back": "View / Back",
                "start": "Menu / Start",
                "guide": "Xbox",
                "leftstick": "LS",
                "rightstick": "RS",
                "misc1": "Share",
            }
            for i in range(num_buttons):
                sdl_name = btn_to_sdl.get(i)
                lbl = sdl_to_xb.get(sdl_name) if sdl_name else None
                if not lbl:
                    xb_default = ["A", "B", "X", "Y", "LB", "RB", "View / Back", "Menu / Start", "Xbox", "LS", "RS", "Share"]
                    lbl = xb_default[i] if i < len(xb_default) else f"Button {i}"
                labels.append({"index": i, "label": lbl, "alt": f"B{i}"})

        elif self.family == "nintendo":
            # SDL2 controller standard defines 'a'=South, 'b'=East, 'x'=West, 'y'=North (Xbox diamond).
            # On physical Nintendo controllers (NES/SNES/Switch), the layout is inverted:
            # South = B, East = A, West = Y, North = X.
            sdl_to_nin = {
                "a": "B",  # South (SDL 'a' -> Nintendo B)
                "b": "A",  # East  (SDL 'b' -> Nintendo A)
                "x": "Y",  # West  (SDL 'x' -> Nintendo Y)
                "y": "X",  # North (SDL 'y' -> Nintendo X)
                "leftshoulder": "L",
                "rightshoulder": "R",
                "lefttrigger": "ZL",
                "righttrigger": "ZR",
                "back": "Select" if ("nes" in self.controller_type.lower() or "snes" in self.controller_type.lower()) else "Minus (-)",
                "start": "Start" if ("nes" in self.controller_type.lower() or "snes" in self.controller_type.lower()) else "Plus (+)",
                "guide": "Home",
                "leftstick": "LS",
                "rightstick": "RS",
                "misc1": "Capture",
            }
            # Only list mapped physical buttons for retro controllers
            if btn_to_sdl:
                for btn_idx in sorted(btn_to_sdl.keys()):
                    sdl_name = btn_to_sdl[btn_idx]
                    lbl = sdl_to_nin.get(sdl_name, sdl_name.capitalize())
                    labels.append({"index": btn_idx, "label": lbl, "alt": f"B{btn_idx}"})
            else:
                for i in range(num_buttons):
                    labels.append({"index": i, "label": f"Button {i}", "alt": f"B{i}"})
        else:
            if btn_to_sdl:
                for btn_idx in sorted(btn_to_sdl.keys()):
                    sdl_name = btn_to_sdl[btn_idx]
                    labels.append({"index": btn_idx, "label": sdl_name.capitalize(), "alt": f"B{btn_idx}"})
            else:
                for i in range(num_buttons):
                    labels.append({"index": i, "label": f"Button {i}", "alt": f"B{i}"})

        return labels


class SDLGameControllerDB:
    """
    Parser and lookup engine for the community-standard SDL_GameControllerDB.
    Combines Linux, Windows, and Mac database entries to generate rich friendly titles.
    """

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = Path(__file__).resolve().parent / "gamecontrollerdb.txt"
        self.db_path = Path(db_path)
        self.entries_by_guid: dict[str, SDLControllerMapping] = {}
        self.entries_by_vid_pid: dict[tuple[int, int], list[SDLControllerMapping]] = {}
        self.entries_by_name: list[tuple[str, SDLControllerMapping]] = []
        self._load()

    def _load(self):
        if not self.db_path.exists():
            logger.warning(f"SDL_GameControllerDB file not found at {self.db_path}")
            return
        try:
            with open(self.db_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split(",", 2)
                    if len(parts) < 3:
                        continue
                    guid = parts[0].strip()
                    name = parts[1].strip()
                    mapping_str = parts[2].strip()

                    platform = "Linux"
                    if "platform:" in mapping_str:
                        for token in mapping_str.split(","):
                            if token.startswith("platform:"):
                                platform = token.split(":", 1)[1].strip()

                    mapping = SDLControllerMapping(guid, name, mapping_str, platform)
                    self.entries_by_guid[guid.lower()] = mapping

                    # Extract VID:PID from standard SDL Linux / Windows GUID
                    if len(guid) >= 20 and (guid.startswith("03000000") or guid.startswith("05000000")):
                        try:
                            v_hex = guid[8:12]
                            p_hex = guid[16:20]
                            vid = int(v_hex[2:4] + v_hex[0:2], 16)
                            pid = int(p_hex[2:4] + p_hex[0:2], 16)
                            if vid > 0 and pid > 0:
                                vp_key = (vid, pid)
                                if vp_key not in self.entries_by_vid_pid:
                                    self.entries_by_vid_pid[vp_key] = []
                                self.entries_by_vid_pid[vp_key].append(mapping)
                        except Exception:
                            pass

                    self.entries_by_name.append((name.lower(), mapping))
            logger.info(f"Loaded {len(self.entries_by_guid)} mappings from SDL_GameControllerDB")
        except Exception as e:
            logger.error(f"Failed to load SDL_GameControllerDB: {e}")

    def synthesize_db_name(self, vid: int | None = None, pid: int | None = None, fallback_name: str = "") -> str:
        """Combine Windows, Linux, and Mac database entry names for the controller."""
        entries = self.entries_by_vid_pid.get((vid, pid), []) if (vid and pid) else []
        db_names: list[str] = []
        for m in entries:
            clean = m.name.strip()
            if clean and clean not in db_names and clean not in ("Gamepad", "USB Device"):
                db_names.append(clean)

        if not db_names:
            return fallback_name or "Gamepad"

        if len(db_names) == 1:
            return db_names[0]

        all_lower = " ".join(db_names).lower()

        # 1. PlayStation Family
        if "dualsense" in all_lower or "ps5" in all_lower:
            return "Sony DualSense (PS5) Wireless Controller"
        if "dualshock 4" in all_lower or "ps4" in all_lower:
            return "Sony DualShock 4 (PS4) Wireless Controller"
        if "dualshock 3" in all_lower or "ps3" in all_lower or "sixaxis" in all_lower:
            return "Sony DualShock 3 (PS3) Controller"

        # 2. Retrolink / Tomee / Retro Clones
        if "tomee" in all_lower and "retrolink" in all_lower:
            if "snes" in all_lower:
                return "Retrolink / Tomee SNES Controller"
            if "nes" in all_lower:
                return "Retrolink / Tomee NES Controller"
            return "Retrolink / Tomee Retro Controller"

        # 3. Nintendo Family
        if "switch pro" in all_lower:
            return "Nintendo Switch Pro Controller"
        if "joy-con" in all_lower:
            return "Nintendo Switch Joy-Con"

        # 4. Xbox Family
        if "xbox series" in all_lower or "series x" in all_lower:
            return "Xbox Series X/S Wireless Controller"
        if "xbox one" in all_lower:
            return "Xbox One Wireless Controller"
        if "xbox 360" in all_lower:
            return "Xbox 360 Controller"

        if len(db_names) == 2:
            n1, n2 = db_names[0], db_names[1]
            if n1.lower() in n2.lower():
                return n2
            if n2.lower() in n1.lower():
                return n1
            parts1 = n1.split()
            parts2 = n2.split()
            if len(parts1) == len(parts2) and len(parts1) <= 3:
                return f"{n1} / {n2}"

        return max(db_names, key=len)

    def find_mapping(
        self,
        vid: int | None = None,
        pid: int | None = None,
        dev_name: str = "",
        guid: str = "",
    ) -> SDLControllerMapping | None:
        """Look up standard controller mapping from SDL_GameControllerDB with priority ordering."""
        mapping: SDLControllerMapping | None = None

        if guid and guid.lower() in self.entries_by_guid:
            mapping = self.entries_by_guid[guid.lower()]
        elif vid and pid and (vid, pid) in self.entries_by_vid_pid:
            candidates = self.entries_by_vid_pid[(vid, pid)]
            linux_match = next((c for c in candidates if c.platform.lower() == "linux"), None)
            mapping = linux_match or candidates[0]
        elif dev_name:
            dn_clean = dev_name.lower().strip()
            for n_entry, m in self.entries_by_name:
                if m.platform.lower() == "linux" and (n_entry in dn_clean or dn_clean in n_entry):
                    mapping = m
                    break

        if mapping:
            mapping.combined_name = self.synthesize_db_name(vid=vid, pid=pid, fallback_name=mapping.name)

        return mapping


# Global Singleton Instance
_GLOBAL_SDL_DB = SDLGameControllerDB()


def get_sdl_controller_db() -> SDLGameControllerDB:
    return _GLOBAL_SDL_DB


def lookup_sdl_gamepad_mapping(
    vid: int | None = None,
    pid: int | None = None,
    dev_name: str = "",
    guid: str = "",
) -> SDLControllerMapping | None:
    return _GLOBAL_SDL_DB.find_mapping(vid=vid, pid=pid, dev_name=dev_name, guid=guid)


def get_synthesized_controller_name(vid: int | None = None, pid: int | None = None, dev_name: str = "") -> str:
    return _GLOBAL_SDL_DB.synthesize_db_name(vid=vid, pid=pid, fallback_name=dev_name)
