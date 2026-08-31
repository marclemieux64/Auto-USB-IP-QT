# 🧪 Auto USB/IP Qt — Comprehensive Testing & Validation Guide

This document outlines the complete testing process, automated test framework, and hardware verification protocols for **Auto USB/IP Qt**. It serves as the standard verification procedure to guarantee that every single option, toggle, API endpoint, server daemon feature, and hardware diagnostic function performs exactly as expected.

---

## 🚀 Quickstart: Running the Automated Test Suites

All tests are executed using Python 3.10+ in the client virtual environment (`client/venv`):

### 1. Run Live Interactive & End-to-End System Verifier (Recommended)
```bash
# Run live option toggle cycles, live server daemon queries, and hardware detection
client/venv/bin/python scripts/test-live-system.py

# Run interactive Sony DualSense / Gamepad hardware testing (LEDs, adaptive triggers, rumble)
client/venv/bin/python scripts/test-live-system.py --interactive
```

### 2. Run Full Master Feature Verification Orchestrator
```bash
# Run all 10 modular test categories with pre-flight environment checks
client/venv/bin/python scripts/test-all-features.py

# Run with live hardware probing (connected USBs, controllers, server sockets)
client/venv/bin/python scripts/test-all-features.py --live

# Generate an exportable Markdown test audit report
client/venv/bin/python scripts/test-all-features.py --report test_report.md
```

### 2. Run Direct Pytest Test Suites
```bash
# Run all tests across the entire repository
client/venv/bin/pytest tests/ -v

# Run a specific feature category
client/venv/bin/pytest tests/test_config_and_options.py -v
client/venv/bin/pytest tests/test_all_options_toggle_matrix.py -v
client/venv/bin/pytest tests/test_device_operations_and_routes.py -v
client/venv/bin/pytest tests/test_server_operations_and_routes.py -v
client/venv/bin/pytest tests/test_gamepad_engine_and_routes.py -v
client/venv/bin/pytest tests/test_server_daemon_features.py -v
client/venv/bin/pytest tests/test_console_and_system_services.py -v
```

### 3. Run Automated Security & Vulnerability Audits
```bash
# Runs Bandit SAST, pip-audit CVE scan, TLS protocol fuzzer, and Polkit audit
client/venv/bin/python scripts/test-security.py
```

---

## 🏛️ Test Matrix & Feature Verification Map

The test suite systematically maps to every user option and daemon capability:

### 1. Client Configuration Options (`client/config.py`)

| Feature / Option Key | UI Toggle / Setting | Expected Behavior | Automated Test Assertion |
| :--- | :--- | :--- | :--- |
| `theme` | Dark / Light / System | UI switches theme styling without restart | `test_default_config_schema` |
| `show_notifications` | Enable Desktop Alerts | Sends notifications on device attach/detach | `test_config_load_and_save` |
| `play_sound_cues` | Play Audio Cues | Triggers audio feedback or falls back to system beep | `test_play_sound_cue_when_disabled`, `test_play_sound_cue_fallback_to_beep` |
| `polling_interval` | Polling Frequency (s) | Controls device and server state polling timer | `test_default_config_schema`, `test_client_config_class` |
| `auto_attach` | Auto-Attach Devices | Automatically attaches available devices on discovery | `test_client_config_class` |
| `power_cycle_on_attach`| Power Reset on Attach | Resets port VBUS before attaching to clear stale state | `test_default_config_schema` |
| `remember_detached` | Persist Detached State | Prevents re-attaching devices manually detached by user | `test_default_config_schema` |
| `enable_nicknames` | Custom Device Names | Replaces raw descriptor with custom user nickname | `test_handle_set_nickname` |
| `enable_wol_wake` | Wake-on-LAN Sync | Broadcasts client MAC to servers for auto-wake | `test_wol_sync_to_servers` |
| `enable_web_csrf` | CSRF Validation | Requires Origin/Referer header on mutating POST APIs | `test_web_server_post_csrf_validation` |
| `enable_tls_pinning` | TLS Pinning (TOFU) | Records and checks server certificate SHA-256 fingerprint | `test_server_control.py` / `test_config_and_options.py` |
| `enable_device_class_filter` | BadUSB Device Filter | Master switch for USB class isolation | `test_default_config_schema` |
| `block_mass_storage` | Block Storage (08h) | Prevents mounting untrusted flash drives | `test_client_config_class` |
| `block_network_devices` | Block Network (02h/E0h)| Prevents rogue USB NICs / Wi-Fi adapters | `test_default_config_schema` |
| `block_hid_keyboards` | Block HID Keyboards | Defends against BadUSB keystroke injection | `test_default_config_schema` |
| `blacklisted_devices` | Device Blacklist | Immediately detaches and suppresses blacklisted devices | `test_handle_blacklist_and_unblacklist` |

---

### 2. Device & Routing APIs (`client/api/device_routes.py`)

| API Route | HTTP Method | Action & Verification | Automated Test Case |
| :--- | :--- | :--- | :--- |
| `/api/attach` | POST | Attaches remote USB device to local VHCI port | `test_handle_attach`, `test_handle_attach_unlisted_fallback` |
| `/api/detach` | POST | Detaches specific local VHCI port | `test_handle_detach` |
| `/api/detach_all` | POST | Detaches all imported local VHCI ports | `test_handle_detach_all` |
| `/api/powercycle_device` | POST | Sends physical VBUS reboot command to server | `test_handle_powercycle_device` |
| `/api/recover_zombies` | POST | Detaches local ports, sends server resets, triggers rescan | `test_handle_recover_zombies` |
| `/api/blacklist` | POST | Adds device to blacklist and detaches matching ports | `test_handle_blacklist_and_unblacklist` |
| `/api/unblacklist` | POST | Removes device from blacklist and triggers rescan | `test_handle_blacklist_and_unblacklist` |
| `/api/nickname` | POST | Updates custom nickname in config and refreshes UI | `test_handle_set_nickname` |
| `/api/toggle_device_audio` | POST | Mutes or unmutes controller audio via PipeWire/ALSA | `test_handle_toggle_device_audio` |
| `/api/toggle_touchpad_mouse` | POST | Toggles DualSense trackpad desktop mouse grab | `test_handle_toggle_touchpad_mouse` |
| `/api/open_storage` | POST | Resolves mount point and launches desktop file manager | `test_handle_open_storage` |

---

### 3. Server Management & Daemons (`server/autousbip.py` & `client/api/server_routes.py`)

| Feature / Setting | Scope | Expected Behavior | Automated Test Case |
| :--- | :--- | :--- | :--- |
| Subnet Filtering | Server | Restricts control & usbip sockets to private LANs | `test_default_server_config_schema` |
| Token Authentication | Server / Client | Requires shared secret for control socket commands | `test_handle_add_server_auth_failed`, `test_server_config_load_and_save` |
| TLS 1.3/1.2 Socket | Server / Client | Encrypts all telemetry, metrics, and command streams | `test_default_server_config_schema` |
| Hardware Blacklist | Server | Excludes internal Pi Ethernet and USB root hubs | `test_default_blacklist_hardware` |
| VBUS Power Cycling | Server | Controls physical 5V USB power via uhubctl | `test_vbus_power_cycle_command_generation` |
| System Metrics | Server | Reads real CPU temp, RAM usage, loadavg, and uptime | `test_system_metrics_collector` |
| Dynamic Rebind | Server | Rebinds all physical USB devices to usbip-host | `test_execute_console_command_server_subcommands` |
| Remote Service Restart | Server | Gracefully restarts autousbip background daemon | `test_handle_restart_and_reboot` |
| Remote Host Reboot | Server | Reboots host Linux system | `test_handle_restart_and_reboot` |
| Subnet IP Scanner | Client | Multi-threaded discovery of unadvertised servers | `test_handle_scan_subnet` |

---

### 4. Gamepad Tester & Sony DualSense Engine (`client/core/gamepad/`)

| Diagnostic Feature | Controller Target | Expected Behavior | Automated Test Case |
| :--- | :--- | :--- | :--- |
| SDL Controller DB Lookup | PlayStation, Xbox, Switch | Resolves standard button labels and families | `test_sdl_controller_mapping_lookup` |
| DualSense Trigger: Off | PS5 DualSense / Edge | Returns Mode `0x00` (free travel) | `test_dualsense_trigger_effect_builder` |
| DualSense Trigger: Bow | PS5 DualSense / Edge | Returns Mode `0x01` (progressive tension) | `test_dualsense_trigger_effect_builder` |
| DualSense Trigger: Gun | PS5 DualSense / Edge | Returns Mode `0x02` (tactile weapon break stop) | `test_dualsense_trigger_effect_builder` |
| DualSense Trigger: Vibrate | PS5 DualSense / Edge | Returns Mode `0x06` (rapid motor vibration) | `test_dualsense_trigger_effect_builder` |
| DualSense HID Report 0x02 | PS5 DualSense / Edge | Validates 63-byte output packet (LEDs, haptics, triggers) | `test_dualsense_output_report_generation` |
| Input Latency & Polling Hz | Any Controller | Samples Linux evdev input event timestamps | `test_controller_latency_tracker_struct` |
| Hardware Output Report API | Controllers | Dispatches rumble, LED color, and trigger effects | `test_handle_gamepad_control_dispatch` |

---

### 5. Diagnostics, System Lifecycle & WoL (`client/core/`)

| Feature | Component | Expected Behavior | Automated Test Case |
| :--- | :--- | :--- | :--- |
| Live Ring-Buffer Logger | Client Console | Thread-safe logging, level filters, pagination, search | `test_client_log_handler_ring_buffer` |
| Interactive Developer CLI | Client Console | Executes local commands (`status`, `devices`, `ping`) | `test_execute_console_command_client_commands` |
| Server Remote CLI Shell | Client Console | Executes server subcommands (`server status`, `reboot`) | `test_execute_console_command_server_subcommands` |
| Sleep & Resume Recovery | PowerManager | Listens to systemd `login1` D-Bus wake and clears zombies | `test_power_manager_lifecycle` |
| Wake-on-LAN Engine | WoL | Builds 102-byte magic packet and broadcasts over UDP | `test_send_wake_on_lan`, `test_wol_sync_to_servers` |

---

## 🎮 Manual & Hardware End-to-End Test Protocols

For testing physical USB devices, server hardware (Raspberry Pi), and Sony DualSense controllers:

### Protocol 1: Physical USB Device Pass-Through
1. Plug a USB flash drive or gamepad into the remote server.
2. Verify the device appears under **Available Devices** in the Client Dashboard.
3. Click **Attach**. Verify:
   - Status transitions to **Imported / Attached**.
   - USB port number and transfer speed badge display correctly.
   - On Linux client, `lsusb` lists the newly forwarded device.
4. Click **Detach**. Verify the port is released and the device returns to the available list.

### Protocol 2: Sony DualSense Haptics & Adaptive Triggers
1. Attach a DualSense controller (USB or USB/IP).
2. Open the **Gamepad Diagnostics** tab in the Web Dashboard (`http://localhost:3242/`).
3. **RGB Lightbar Test**: Move the color sliders. Verify the LED bar changes color instantly.
4. **Adaptive Trigger Test**: Select **Weapon / Gun Mode** for R2 and pull the trigger. Verify tactile resistance at the defined threshold.
5. **Rumble Test**: Click **Test Rumble Motors**. Verify left (heavy) and right (light) motors pulse.
6. **Trackpad Test**: Slide a finger on the trackpad. Verify the coordinate visualizer tracks touch position in real-time.

### Protocol 3: Sleep / Wake Zombie Recovery
1. Attach a USB device from a remote server.
2. Put the client system to sleep (`systemctl suspend`).
3. Wake the client system.
4. Verify within 2 seconds:
   - PowerManager detects system resume via D-Bus / monotonic watchdog.
   - Zombie connections are cleared.
   - Device auto-attaches cleanly without requiring a manual reconnect.

---

## 🔄 CI/CD & Automated Verification Pipeline

To integrate this test suite into CI/CD pipelines (e.g. GitHub Actions):

```yaml
name: Test Suite
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r client/requirements.txt
          pip install pytest pytest-asyncio
      - name: Run Master Feature Test Suite
        run: python scripts/test-all-features.py
      - name: Run Security & SAST Audit
        run: python scripts/test-security.py
```
