from __future__ import annotations

import logging
import math
import os
import shutil
import struct
import subprocess
import tempfile
import time
from pathlib import Path

logger = logging.getLogger("auto-usbip-client")

# Pre-allocated output report buffer (63 bytes for USB report 0x02)
_OUTPUT_REPORT_BUF = bytearray(63)
_CACHED_CHIME_WAV: bytes | None = None
_CACHED_SINK_INFO: tuple[float, str | None] = (0.0, None)
DS_INPUT_FDS: dict[str, int] = {}


def build_dualsense_trigger_effect(
    mode: str = "off",
    force: int = 255,
    start_pos: int = 32,
    end_pos: int = 224,
    freq: int = 15,
) -> dict:
    """Construct DualSense adaptive trigger motor effect payload for L2/R2."""
    m_lower = str(mode).lower()
    if m_lower in ("bow", "archery"):
        return {"mode": 0x01, "p1": 0x00, "p2": max(0, min(255, force))}
    elif m_lower in ("gun", "weapon", "wall", "sniper", "section"):
        s = max(0, min(255, start_pos if start_pos > 0 else 60))
        e = max(s + 20, min(255, end_pos if end_pos > s else 220))
        return {"mode": 0x02, "p1": s, "p2": e, "p3": max(0, min(255, force))}
    elif m_lower in ("machine_gun", "automatic", "rifle", "kickback", "rapid", "vibrate"):
        s = max(0, min(255, start_pos if start_pos > 0 else 30))
        return {"mode": 0x06, "p1": s, "p2": max(0, min(255, force)), "p3": max(5, min(40, freq))}
    elif m_lower in ("abs", "brakes", "pulse", "stutter"):
        s = max(0, min(255, start_pos if start_pos > 0 else 120))
        return {"mode": 0x06, "p1": s, "p2": max(0, min(255, force)), "p3": 28}
    elif m_lower in ("heavy", "resistance", "hydraulic", "lever", "continuous"):
        return {"mode": 0x01, "p1": max(0, min(255, start_pos)), "p2": max(0, min(255, force))}
    else:  # "off" / normal smooth travel
        return {"mode": 0x00, "p1": 0, "p2": 0, "p3": 0}


def send_playstation_output_report(
    hidraw_path: str,
    r: int = 0,
    g: int = 100,
    b: int = 255,
    player: int = 1,
    rumble_l: int = 0,
    rumble_r: int = 0,
    mic_mute: bool = False,
    brightness: int = 255,
    trigger_r: dict | None = None,
    trigger_l: dict | None = None,
) -> bool:
    """Send DualSense / DualShock 4 HID Output Report (0x02 over USB) to configure LEDs, haptics & adaptive triggers."""
    if not hidraw_path or not os.path.exists(hidraw_path):
        return False
    try:
        player_map = {1: 0x04, 2: 0x0A, 3: 0x15, 4: 0x1B, 5: 0x1F}
        player_mask = player_map.get(player, player if isinstance(player, int) else 0x04)

        buf = _OUTPUT_REPORT_BUF
        for i in range(63):
            buf[i] = 0

        buf[0] = 0x02  # report_id USB
        
        valid_flag0 = 0x80 | 0x20  # Keep audio DAC flags & speaker volume unmuted
        if rumble_l > 0 or rumble_r > 0:
            valid_flag0 |= 0x03  # Vibration motors enable
        if trigger_r is not None:
            valid_flag0 |= 0x04  # Right trigger motor enable
        if trigger_l is not None:
            valid_flag0 |= 0x08  # Left trigger motor enable
            
        buf[1] = valid_flag0
        buf[2] = 0x14 | 0x20 | 0x01  # valid_flag1: 0x01=mic led, 0x04=lightbar setup, 0x10=player leds, 0x20=lightbar color
        buf[3] = max(0, min(255, rumble_r))  # fast motor (right)
        buf[4] = max(0, min(255, rumble_l))  # heavy motor (left)
        buf[5] = 0x7F  # headphone volume (100%)
        buf[6] = 0xFF  # speaker volume (100%)
        buf[8] = 0x30  # Audio routing / control
        buf[9] = 1 if mic_mute else 0  # 1 = Solid Amber LED (Muted), 0 = OFF (Unmuted)

        # Right Adaptive Trigger (R2) parameters (Bytes 11 to 21)
        if trigger_r is not None:
            buf[11] = trigger_r.get("mode", 0) & 0xFF
            buf[12] = trigger_r.get("p1", 0) & 0xFF
            buf[13] = trigger_r.get("p2", 0) & 0xFF
            buf[14] = trigger_r.get("p3", 0) & 0xFF
            buf[15] = trigger_r.get("p4", 0) & 0xFF
            buf[16] = trigger_r.get("p5", 0) & 0xFF
            buf[17] = trigger_r.get("p6", 0) & 0xFF
            buf[18] = trigger_r.get("p7", 0) & 0xFF

        # Left Adaptive Trigger (L2) parameters (Bytes 22 to 32)
        if trigger_l is not None:
            buf[22] = trigger_l.get("mode", 0) & 0xFF
            buf[23] = trigger_l.get("p1", 0) & 0xFF
            buf[24] = trigger_l.get("p2", 0) & 0xFF
            buf[25] = trigger_l.get("p3", 0) & 0xFF
            buf[26] = trigger_l.get("p4", 0) & 0xFF
            buf[27] = trigger_l.get("p5", 0) & 0xFF
            buf[28] = trigger_l.get("p6", 0) & 0xFF
            buf[29] = trigger_l.get("p7", 0) & 0xFF

        buf[38] = 0x02  # Lightbar setup
        buf[43] = max(0, min(255, brightness))  # Lightbar brightness
        buf[44] = player_mask  # Player LEDs
        buf[45] = max(0, min(255, r))  # Red
        buf[46] = max(0, min(255, g))  # Green
        buf[47] = max(0, min(255, b))  # Blue

        fd = os.open(hidraw_path, os.O_WRONLY)
        try:
            os.write(fd, bytes(buf))
        finally:
            os.close(fd)
        return True
    except Exception as e:
        logger.debug(f"Failed to send PlayStation HID report to {hidraw_path}: {e}")
        return False


def unmute_playstation_speaker(hidraw_path: str) -> bool:
    """Send output report unmute packet and max out internal DAC speaker volume registers."""
    if not hidraw_path or not os.path.exists(hidraw_path):
        return False
    try:
        buf = bytearray(63)
        buf[0] = 0x02
        buf[1] = 0x80 | 0x20  # Keep audio DAC flags & speaker volume unmuted
        buf[2] = 0x14
        buf[5] = 0x7F  # headphone 100%
        buf[6] = 0xFF  # speaker 100%
        buf[8] = 0x30  # Enable speaker / internal DAC
        buf[43] = 255
        buf[44] = 0x04
        buf[45] = 0
        buf[46] = 100
        buf[47] = 255
        fd = os.open(hidraw_path, os.O_WRONLY)
        try:
            os.write(fd, bytes(buf))
        finally:
            os.close(fd)
        return True
    except Exception:
        return False


def find_dualsense_pipewire_sink(force_refresh: bool = False) -> str | None:
    """Search PipeWire / PulseAudio for the DualSense Audio Sink with caching."""
    global _CACHED_SINK_INFO
    now = time.time()
    if not force_refresh and (now - _CACHED_SINK_INFO[0]) < 3.0:
        return _CACHED_SINK_INFO[1]

    sink_name = None
    if shutil.which("pactl"):
        try:
            res = subprocess.run(["pactl", "list", "sinks", "short"], capture_output=True, text=True, timeout=1.5)
            if res.returncode == 0:
                for line in res.stdout.strip().splitlines():
                    if not line.strip():
                        continue
                    parts = line.split()
                    if len(parts) >= 2:
                        name_candidate = parts[1]
                        name_l = name_candidate.lower()
                        if any(k in name_l for k in ("wireless_controller", "dualsense", "controller", "sony")):
                            sink_name = name_candidate
                            break
        except Exception:
            pass

    _CACHED_SINK_INFO = (now, sink_name)
    return sink_name


def _get_or_create_chime_wav() -> bytes:
    """Generate and return cached 48kHz 4-channel chime WAV data."""
    global _CACHED_CHIME_WAV
    if _CACHED_CHIME_WAV is not None:
        return _CACHED_CHIME_WAV

    sample_rate = 48000
    duration = 0.5
    num_samples = int(sample_rate * duration)

    frames = bytearray()
    for i in range(num_samples):
        t = i / sample_rate
        if t < 0.16:
            freq = 523.25
        elif t < 0.32:
            freq = 659.25
        else:
            freq = 783.99
        env = math.sin(math.pi * (t / duration)) ** 0.6
        val = int(32767.0 * 0.85 * env * math.sin(2.0 * math.pi * freq * t))
        frames += struct.pack("<hhhh", val, val, val, val)

    header = bytearray()
    header += b"RIFF"
    header += struct.pack("<I", 36 + len(frames))
    header += b"WAVEfmt "
    header += struct.pack("<IHHIIHH", 16, 1, 4, sample_rate, sample_rate * 8, 8, 16)
    header += b"data"
    header += struct.pack("<I", len(frames))

    _CACHED_CHIME_WAV = bytes(header + frames)
    return _CACHED_CHIME_WAV


def play_sound_test_chime(hidraw_path: str | None = None) -> bool:
    """Generate and play a 48kHz 4-channel 3-tone chime through the controller's speaker."""
    if hidraw_path and os.path.exists(hidraw_path):
        unmute_playstation_speaker(hidraw_path)
    wav_bytes = _get_or_create_chime_wav()

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name
        f.write(wav_bytes)

    played = False
    try:
        sink_id = find_dualsense_pipewire_sink(force_refresh=True)
        if sink_id:
            if shutil.which("paplay"):
                try:
                    res = subprocess.run(["paplay", f"--device={sink_id}", wav_path], timeout=2.0)
                    if res.returncode == 0:
                        played = True
                except Exception:
                    pass

            if not played and shutil.which("pw-play"):
                try:
                    res = subprocess.run(["pw-play", "--target", sink_id, wav_path], timeout=2.0)
                    if res.returncode == 0:
                        played = True
                except Exception:
                    pass

        if not played and shutil.which("aplay"):
            try:
                res = subprocess.run(["aplay", "-D", "plughw:CARD=Controller,DEV=0", "-q", wav_path], timeout=2.0)
                if res.returncode == 0:
                    played = True
            except Exception:
                pass
    finally:
        try:
            os.unlink(wav_path)
        except Exception:
            pass

    return played


def read_dualsense_mic_button(hidraw_path: str) -> int:
    """Read the real-time physical Mic Mute button state from DualSense USB report 0x01 with safe FD management."""
    if not hidraw_path or not os.path.exists(hidraw_path):
        _close_hidraw_fd(hidraw_path)
        return 0

    global DS_INPUT_FDS
    fd = DS_INPUT_FDS.get(hidraw_path)
    if fd is None or fd <= 0:
        try:
            fd = os.open(hidraw_path, os.O_RDONLY | os.O_NONBLOCK)
            DS_INPUT_FDS[hidraw_path] = fd
        except Exception:
            return 0

    mic_pressed = 0
    try:
        while True:
            d = os.read(fd, 64)
            if not d:
                break
            if len(d) >= 11 and d[0] == 0x01:
                # Byte 10 Bit 2 (0x04) is the physical Mic Mute button
                mic_pressed = 1 if (d[10] & 0x04) else 0
    except (BlockingIOError, InterruptedError):
        pass
    except Exception:
        _close_hidraw_fd(hidraw_path)

    return mic_pressed


def _close_hidraw_fd(hidraw_path: str):
    fd = DS_INPUT_FDS.pop(hidraw_path, None)
    if fd is not None:
        try:
            os.close(fd)
        except Exception:
            pass


def cleanup_dualsense_resources():
    """Clean up open file descriptors."""
    for path in list(DS_INPUT_FDS.keys()):
        _close_hidraw_fd(path)