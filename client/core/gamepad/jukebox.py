from __future__ import annotations

import logging
import math
import os
import random
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from core.resources import get_resource_path
from .dualsense import find_dualsense_pipewire_sink, unmute_playstation_speaker

logger = logging.getLogger("auto-usbip-client")

_EASTER_EGG_LOCK = threading.Lock()
_ACTIVE_EASTER_EGG_STOP_EVENT: threading.Event | None = None
_ACTIVE_AUDIO_PROC: subprocess.Popen | None = None
_LAST_PLAYED_TRACK: str | None = None



def ensure_audio_file(filename: str, audio_base: Path, download_url: str | None = None) -> str:
    """Ensure audio track is available locally, downloading on-demand if missing."""
    target = audio_base / filename
    if target.exists() and target.stat().st_size > 1024:
        return str(target)
    if download_url:
        try:
            logger.info(f"Auto-downloading audio track '{filename}' on-demand...")
            req = urllib.request.Request(download_url, headers={"User-Agent": "AutoUsbip-Client/2.0"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = resp.read()
                if len(data) > 1024:
                    with open(target, "wb") as f:
                        f.write(data)
                    logger.info(f"Successfully downloaded '{filename}' ({len(data)} bytes).")
                    return str(target)
        except Exception as e:
            logger.warning(f"Could not auto-download {filename}: {e}")
    if target.exists():
        return str(target)
    for existing in audio_base.glob("*.wav"):
        if existing.stat().st_size > 1024:
            return str(existing)
    return str(target)


def stop_active_easter_egg():
    """Cancel any currently playing easter egg audio/lightshow immediately."""
    global _ACTIVE_EASTER_EGG_STOP_EVENT, _ACTIVE_AUDIO_PROC
    if _ACTIVE_EASTER_EGG_STOP_EVENT:
        _ACTIVE_EASTER_EGG_STOP_EVENT.set()
    if _ACTIVE_AUDIO_PROC:
        try:
            _ACTIVE_AUDIO_PROC.terminate()
            _ACTIVE_AUDIO_PROC.kill()
        except Exception:
            pass
        _ACTIVE_AUDIO_PROC = None


def play_konami_easter_egg(track_name: str | None = None, hidraw_path: str | None = None) -> tuple[bool, str]:
    """Play full animated synchronized lightbar, haptic rumble & 4-channel audio easter egg track."""
    global _LAST_PLAYED_TRACK, _ACTIVE_EASTER_EGG_STOP_EVENT, _ACTIVE_AUDIO_PROC

    audio_base = get_resource_path("assets/audio")
    audio_base.mkdir(parents=True, exist_ok=True)
    
    TRACK_METADATA = {
        "bad_apple": {
            "title": "Touhou - Bad Apple!! (Nomico / Alstroemeria Records)",
            "file": "bad_apple_cut.wav",
            "duration": 34.0,
            "light_pattern": "bad_apple"
        },
        "megalovania": {
            "title": "Undertale - MEGALOVANIA (Toby Fox)",
            "file": "megalovania.wav",
            "duration": 26.0,
            "light_pattern": "megalovania"
        },
        "asgore": {
            "title": "Undertale - ASGORE (Toby Fox)",
            "file": "asgore.wav",
            "duration": 30.0,
            "light_pattern": "asgore"
        },
        "sega_normal": {
            "title": "SEGA! (Classic 16-Bit Chime)",
            "file": "sega_normal.wav",
            "duration": 5.0,
            "light_pattern": "sega"
        },
        "sega_scream": {
            "title": "SEEEE-GAAAA! (Sega Genesis Scream)",
            "file": "sega_scream.wav",
            "duration": 6.0,
            "light_pattern": "sega_scream"
        },
        "ps1_opening": {
            "title": "Sony PlayStation 1 BIOS Startup Chime",
            "file": "ps1_opening.wav",
            "duration": 16.0,
            "light_pattern": "ps1"
        },
        "gamecube_opening": {
            "title": "Nintendo GameCube Startup Jingle",
            "file": "gamecube_opening.wav",
            "duration": 6.5,
            "light_pattern": "gamecube"
        },
        "rickroll": {
            "title": "Rick Astley - Never Gonna Give You Up",
            "file": "rickroll.wav",
            "duration": 28.0,
            "light_pattern": "rickroll"
        }
    }

    with _EASTER_EGG_LOCK:
        # 1. Stop any currently active song so two instances NEVER overlap
        stop_active_easter_egg()
        time.sleep(0.08)

        # 2. Prevent the same song from playing twice in a row
        available_keys = list(TRACK_METADATA.keys())
        if _LAST_PLAYED_TRACK in available_keys and len(available_keys) > 1:
            choices = [k for k in available_keys if k != _LAST_PLAYED_TRACK]
        else:
            choices = available_keys

        if not track_name or track_name not in TRACK_METADATA:
            track_name = random.choice(choices)

        _LAST_PLAYED_TRACK = track_name
        track_info = TRACK_METADATA[track_name]
        wav_path = ensure_audio_file(track_info["file"], audio_base, track_info.get("download_url"))

        stop_event = threading.Event()
        _ACTIVE_EASTER_EGG_STOP_EVENT = stop_event

    def worker():
        global _ACTIVE_EASTER_EGG_STOP_EVENT, _ACTIVE_AUDIO_PROC
        dev_node = hidraw_path or "/dev/hidraw15"

        def haptic_and_light_show():
            if not dev_node or not os.path.exists(dev_node):
                return
            try:
                fd = os.open(dev_node, os.O_WRONLY)
            except Exception:
                return

            start_t = time.time()
            ptn = track_info["light_pattern"]
            last_state = None

            try:
                while not stop_event.is_set():
                    elapsed = time.time() - start_t
                    if elapsed > track_info["duration"]:
                        break

                    r, g, b = (0, 0, 0)
                    player = 0x04
                    rl, rr = 0, 0

                    if ptn == "bad_apple":
                        if elapsed < 8.0:
                            p = elapsed / 8.0
                            val = int(255 * (1.0 - math.cos(p * math.pi * 4)) / 2)
                            r, g, b = (val, val, val)
                            player = [0x04, 0x0A, 0x15, 0x1B, 0x1F][int(elapsed * 4) % 5]
                            if (int(elapsed * 2) % 2) == 0:
                                rl, rr = 120, 60
                        elif elapsed < 24.0:
                            beat = int((elapsed - 8.0) / 0.435)
                            is_white = (beat % 2 == 0)
                            r, g, b = (255, 255, 255) if is_white else (10, 10, 10)
                            player = 0x1F if is_white else 0x00
                            rl, rr = (200, 150) if is_white else (0, 0)
                        else:
                            val = max(0, int(255 * (1.0 - (elapsed - 24.0) / 10.0)))
                            r, g, b = (val, val, val)
                            player = 0x04

                    elif ptn == "megalovania":
                        beat = int(elapsed / 0.25)
                        sub_beat = (elapsed % 0.25) / 0.25
                        if elapsed < 2.0:
                            r, g, b = (0, 180, 255)
                            player = 0x04
                            if sub_beat < 0.3:
                                rl, rr = 180, 120
                        else:
                            is_blue = (beat % 2 == 0)
                            r, g, b = (0, 120, 255) if is_blue else (255, 10, 10)
                            player = [0x01, 0x02, 0x04, 0x08, 0x10][beat % 5]
                            if sub_beat < 0.4:
                                rl, rr = (230, 180) if not is_blue else (160, 100)

                    elif ptn == "asgore":
                        r, g, b = (255, 140, 0)
                        player = 0x15
                        if (int(elapsed * 3) % 2) == 0:
                            rl, rr = 140, 80

                    elif ptn == "sega":
                        r, g, b = (0, 100, 255)
                        player = 0x1F
                        if elapsed < 3.0:
                            rl, rr = 200, 150

                    elif ptn == "sega_scream":
                        r, g, b = (255, 0, 0)
                        player = 0x1F
                        rl, rr = 255, 255

                    elif ptn == "ps1":
                        if elapsed < 4.0:
                            r, g, b = (255, 195, 30)
                            player = 0x04
                            rl = 90
                        elif elapsed < 9.0:
                            r, g, b = (255, 255, 255)
                            player = 0x1F
                            rl, rr = 150, 40
                        else:
                            r, g, b = (0, 45, 220)
                            player = 0x0A
                            rl, rr = 60, 0

                    elif ptn == "gamecube":
                        r, g, b = (120, 40, 230)
                        player = 0x04
                        if elapsed < 4.8:
                            tick = (int(elapsed * 6) % 2 == 0)
                            rr = 50 if tick else 0
                        else:
                            rl, rr = 180, 140

                    elif ptn == "rickroll":
                        beat = int(elapsed / 0.265)
                        sub = (elapsed % 0.265) / 0.265
                        disco = [(255, 20, 147), (0, 255, 255), (255, 230, 0), (168, 85, 247), (255, 60, 0), (0, 255, 128)]
                        r, g, b = disco[beat % len(disco)]
                        player = [0x04, 0x0A, 0x15, 0x1B, 0x1F][beat % 5]
                        if sub < 0.35:
                            rl, rr = 130, 90

                    # Deduplicate state to prevent bus flooding
                    state = (r, g, b, player, rl, rr)
                    if state != last_state:
                        last_state = state
                        buf = bytearray(63)
                        buf[0] = 0x02
                        buf[1] = 0x80 | 0x20 | (0x03 if (rl or rr) else 0x00)
                        buf[2] = 0x14 | 0x80
                        buf[3] = rr
                        buf[4] = rl
                        buf[5] = 0x7F
                        buf[6] = 0xFF
                        buf[8] = 0x30
                        buf[38] = 0x02
                        buf[43] = 255
                        buf[44] = player
                        buf[45] = r
                        buf[46] = g
                        buf[47] = b
                        try:
                            os.write(fd, bytes(buf))
                        except Exception:
                            pass

                    time.sleep(0.06)
            finally:
                # Reset to clean idle
                buf = bytearray(63)
                buf[0] = 0x02
                buf[1] = 0x80 | 0x20
                buf[2] = 0x14
                buf[5] = 0x7F
                buf[6] = 0xFF
                buf[8] = 0x30
                buf[43] = 255
                buf[44] = 0x04
                buf[45] = 0
                buf[46] = 100
                buf[47] = 255
                try:
                    os.write(fd, bytes(buf))
                    os.close(fd)
                except Exception:
                    pass

        unmute_playstation_speaker(dev_node)
        lt = threading.Thread(target=haptic_and_light_show, daemon=True)
        lt.start()

        try:
            sink_id = find_dualsense_pipewire_sink()
            played = False
            if sink_id:
                for play_cmd in [
                    ["paplay", f"--device={sink_id}", str(wav_path)],
                    ["pw-play", "--target", str(sink_id), str(wav_path)],
                ]:
                    if stop_event.is_set():
                        break
                    try:
                        proc = subprocess.Popen(play_cmd)
                        with _EASTER_EGG_LOCK:
                            _ACTIVE_AUDIO_PROC = proc
                        while proc.poll() is None:
                            if stop_event.is_set():
                                proc.terminate()
                                proc.kill()
                                break
                            time.sleep(0.05)
                        if proc.returncode == 0:
                            played = True
                            break
                    except Exception:
                        pass

            if not played and not stop_event.is_set():
                try:
                    proc = subprocess.Popen(["aplay", "-D", "plughw:CARD=Controller,DEV=0", "-q", str(wav_path)])
                    with _EASTER_EGG_LOCK:
                        _ACTIVE_AUDIO_PROC = proc
                    while proc.poll() is None:
                        if stop_event.is_set():
                            proc.terminate()
                            proc.kill()
                            break
                        time.sleep(0.05)
                except Exception:
                    pass
        finally:
            stop_event.set()
            with _EASTER_EGG_LOCK:
                if _ACTIVE_EASTER_EGG_STOP_EVENT is stop_event:
                    _ACTIVE_EASTER_EGG_STOP_EVENT = None
                    _ACTIVE_AUDIO_PROC = None

    threading.Thread(target=worker, daemon=True).start()
    return True, track_info["title"]


def play_bad_apple_easter_egg(hidraw_path: str | None = None) -> bool:
    """Compatibility alias for play_konami_easter_egg."""
    res, _ = play_konami_easter_egg(track_name=None, hidraw_path=hidraw_path)
    return res
