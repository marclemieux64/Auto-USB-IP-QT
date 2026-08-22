<div align="center">

<img src="client/assets/branding/app-logo.svg" alt="Auto USB/IP Qt Banner" width="560">

# Auto USB/IP Qt

**Encrypted USB-over-IP management with ZeroConf discovery, Polkit security, web dashboard, remote server console, and gamepad diagnostics.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green.svg)](https://pypi.org/project/PyQt6/)
[![Security: Polkit & AppArmor](https://img.shields.io/badge/Security-Polkit%20%7C%20AppArmor-red.svg)](client/security/)
[![Packaging: AppImage & Tarball](https://img.shields.io/badge/Packaging-AppImage%20%7C%20Tarball-blueviolet.svg)](dist/)
[![Linux](https://img.shields.io/badge/OS-Linux%20%7C%20Windows-lightgrey.svg)](https://github.com/)

[Key Features](#-key-features) • [Screenshots](#-screenshots--ui-tour) • [Architecture](#-architecture) • [Security & Privileges](#-security--privilege-model) • [Server Setup](#-server-installation-raspberry-pi--linux) • [Client Setup](#-client-distribution--installation) • [Gamepad Diagnostics](#-integrated-gamepad-tester) • [Credits & Licenses](#-credits--licenses) • [AI Disclosure](#-ai-assisted-development-disclosure)

</div>

---

## 🚀 Key Features

* ⚡ **Zero-Configuration Server Discovery**: Uses mDNS (Zeroconf / DNS-SD) to discover remote USB/IP servers on the local network automatically.
* 🔒 **Passwordless Polkit Security**:
  * **Polkit D-Bus Policies**: Replaces `sudoers` with granular PolicyKit actions (`org.autousbip.client.*`).
  * **AppArmor Profiles**: Restricts filesystem and capability boundaries for client and server binaries.
  * **udev Access Rules**: Direct non-root access to USB devices and gamepad telemetry via `uaccess`.
  * **Systemd Ambient Capabilities**: Runs daemons with `CAP_NET_ADMIN`, `CAP_SYS_ADMIN`, and `CAP_SYS_RAWIO` without root privileges.
* 🛡️ **Encrypted Control Socket (TLS 1.3 / 1.2)**: Secures control commands, log streaming, and telemetry sockets using TLS certificates and optional pinning.
* 🖥️ **Web Dashboard**:
  * Dark-mode interface accessible locally or across the LAN (`http://<client-ip>:3242/`).
  * Real-time configuration for TLS, discovery, subnet filters, VBUS power delay, auto-attach, and audio cues.
  * **Multi-User Lockout & In-Use Badges**: Displays remote client hostnames on active devices to prevent attach conflicts.
* 📟 **Diagnostic Consoles**:
  * **Client Console**: In-memory log streamer, regex search, log levels, and interactive CLI shell.
  * **Remote Server Console**: Live `journalctl` streaming, CPU temperature/uptime metrics, and remote maintenance commands (`rebind`, `restart`, `reboot`).
* 🎮 **Gamepad Tester**:
  * **Kenney Vector SVG Prompts**: Resolution-independent button prompts for Nintendo, PlayStation, Xbox, and NES/SNES layouts.
  * **`SDL_GameControllerDB`**: Community hardware mapping profiles.
  * Analog stick, trigger, and D-pad evaluation with visual deadzone rendering.
  * Multi-touch trackpad visualizer with absolute touch coordinates.
  * 6-axis IMU accelerometer and gyroscope motion telemetry.
  * **Sony DualSense** hardware controls: RGB lightbar, player LEDs, mic mute button, motorized adaptive triggers, and rumble tests.
* 💤 **Sleep & Wake Auto-Recovery**: Clears zombie connections and re-binds remote USB ports upon system resume using `systemd-login1` D-Bus signals.
* 📦 **Portable Packaging**: Self-contained **AppImage** and portable **Tarball** builds with zero host library requirements.

---

## 📸 Screenshots & UI Tour

<div align="center">

### 🖥️ Main Dashboard & Device Manager
*Dark-mode interface with live server metrics, latency telemetry, attach/detach controls, and USB power cycling.*

<img src="assets/screenshots/dashboard_overview.png" alt="Auto USB/IP Qt Dashboard Overview" width="900">

<br><br>

### 🎮 Gamepad Latency & Calibration Tester
*Live input telemetry with Kenney vector prompts, deadzone mapping, multi-touch trackpad, 6-axis IMU gyro/accel, and DualSense adaptive triggers.*

<img src="assets/screenshots/gamepad_tester.png" alt="Gamepad Latency and Calibration Tester" width="900">

<br><br>

### ⚙️ Client Options & Security Settings
*Customization toggles, LAN dashboard sharing, visual badge overlays, and BadUSB hardware class isolation.*

<img src="assets/screenshots/options_settings.png" alt="Client Options & Security Settings" width="900">

<br><br>

### 🎛️ Remote Server Configuration
*Remote daemon TLS management, mDNS discovery, VBUS reboot delays, and server-side hardware access control.*

<img src="assets/screenshots/server_settings.png" alt="Remote Server Settings Modal" width="900">

<br><br>

### 📟 Diagnostic Console & Live Event Stream
*Interactive developer shell with structured real-time logging, severity level filters, search, and log export.*

<img src="assets/screenshots/console_diagnostics.png" alt="Client Diagnostics Console" width="900">

</div>

---

## 🏛️ Architecture

```text
┌─────────────────────────────────────────────────────────────────────────┐
│               🖥️ REMOTE SERVER (Raspberry Pi / Linux)                   │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ autousbip.py Background Daemon (systemd + AppArmor + Capabilities)│  │
│  │   • Kernel usbip-host driver (Hardware USB Device Exporter)       │  │
│  │   • TLS Encrypted Control Socket (:3241 - Telemetry, CLI, Rebind) │  │
│  │   • Zeroconf mDNS Broadcaster (:5353 - Network Discovery)         │  │
│  │   • Direct sysfs VBUS Power Control (/sys/bus/usb/devices/...)    │  │
│  └──────────────────────────────────┬────────────────────────────────┘  │
└─────────────────────────────────────┼───────────────────────────────────┘
                                      │
                   TLS 1.3 / 1.2 Encrypted LAN & mDNS
                                      │
┌─────────────────────────────────────┴───────────────────────────────────┐
│                   💻 LOCAL CLIENT (Linux / Windows)                     │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ Auto USB/IP Client (AppImage / Standalone Portable / PyQt6)       │  │
│  │   • Pure-Python mDNS Listener (Automatic Server Discovery)        │  │
│  │   • VHCI Kernel Driver / usbip-win (Virtual USB Port Forwarding)  │  │
│  │   • Embedded Web Dashboard Server (:3242 - Local & LAN Access)    │  │
│  │   • Polkit D-Bus Bridge (Passwordless privileged kernel attaches) │  │
│  │   • Pure Vector SVG Kenney Gamepad Diagnostic Engine              │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🛡️ Security & Privilege Model

### 1. Automated Zero-Root Security & Driver Pre-Flight
* **Polkit & udev**: Rules in [`client/security/polkit/`](client/security/polkit/) & [`client/security/udev/`](client/security/udev/) grant active desktop users zero-sudo authorization to manage USB/IP without terminal commands or passwords.
* **Kernel Driver Pre-Flight**: On launch, the client automatically loads and validates kernel drivers (`vhci-hcd` on Linux via Polkit, and `usbip-win` VHCI on Windows).
* **AppArmor & SELinux**: Native MAC sandboxing profiles for Debian, Ubuntu, openSUSE, Fedora, Bazzite, RHEL, and CentOS are automatically applied during server service installation ([`server/install-server.sh`](server/install-server.sh) or `./autousbip-qt-server --install`).

### 2. On-Demand Security & Network Controls (Web UI Dashboard)
All security controls can be toggled on demand directly from the client options modal or server settings modal:
* 🔒 **Web API CSRF Protection**: Restricts mutating API actions (attach, detach, restart, reboot) to requests originating from verified local origins.
* 🔑 **TLS Certificate Pinning (TOFU)**: Records and validates the SHA-256 fingerprint of the server's TLS certificate on first connect.
* 🛡️ **Subnet & Firewall Filtering**: Restricts server control sockets (`3241/tcp`) and device streaming (`3240/tcp`) exclusively to trusted local subnets (`192.168.0.0/16`, `10.0.0.0/8`, `172.16.0.0/12`).
* 🦹 **BadUSB Device Class Filtering**:
  * Block Mass Storage / Flash Drives (Class 08h)
  * Block Virtual Network / Ethernet / Wi-Fi Adapters (Classes 02h/E0h)
  * Block Raw USB Keyboards (Keystroke Injection defense)

---

## 📦 Server Installation (Raspberry Pi / Linux)

### Option A: Standalone Self-Installing Binary
```bash
# Run in foreground:
sudo ./dist/autousbip-qt-server

# Install as systemd background service (starts on boot):
sudo ./dist/autousbip-qt-server --install

# Uninstall:
sudo ./dist/autousbip-qt-server --uninstall
```

### Option B: Automated 1-Command Web Installer
```bash
curl -fsSL https://raw.githubusercontent.com/marclemieux64/Auto-USB-IP-QT/dev/server/install-server.sh | sudo bash
```

### Option C: Manual Setup
```bash
sudo apt update && sudo apt install -y usbip hwdata openssl uhubctl avahi-utils
sudo cp server/autousbip.py /usr/local/bin/autousbip-qt-server.py
sudo chmod 755 /usr/local/bin/autousbip-qt-server.py
sudo cp server/autousbip.service /etc/systemd/system/autousbip-qt-server.service
sudo systemctl daemon-reload
sudo systemctl enable --now autousbip-qt-server.service
```

---

## 💻 Client Distribution & Installation

Auto USB/IP Client is distributed as a portable **AppImage** and a standalone **Tarball**. It runs on **Ubuntu, Fedora, Arch Linux, Bazzite, SteamOS, Debian, and openSUSE**.

### Option 1: Portable AppImage (Recommended)
```bash
# 1. Ensure kernel VHCI driver is loaded
sudo modprobe vhci-hcd

# 2. Make executable and launch:
chmod +x dist/AutoUSBIP-QT-x86_64.AppImage
./dist/AutoUSBIP-QT-x86_64.AppImage

# 3. (Optional) Integrate into Desktop Application Menu:
./dist/AutoUSBIP-QT-x86_64.AppImage --install

# 4. (Optional) Remove from Desktop Application Menu:
./dist/AutoUSBIP-QT-x86_64.AppImage --uninstall
```

### Option 2: Standalone Portable Tarball (.tar.gz)
```bash
# 1. Extract tarball
tar -xzf dist/AutoUSBIP-QT-x86_64.tar.gz
cd autousbip-qt-client-linux-x86_64

# 2. Run
./autousbip-qt-client

# 3. (Optional) Add to Desktop Application Menu:
./install-menu.sh

# 4. (Optional) Remove from Desktop Application Menu:
./uninstall-menu.sh
```

---

### 🧹 How to Fully Remove / Clean Up (Portable Mode)

If you are running the portable version (AppImage, Tarball, or standalone Windows folder) and want to completely delete all traces of the application, follow these steps:

#### **Linux (AppImage / Tarball)**
1. **Remove Desktop Menu Shortcuts** (if you ran `--install` or `install-menu.sh`):
   ```bash
   ./AutoUSBIP-QT-x86_64.AppImage --uninstall
   # OR for tarball:
   ./uninstall-menu.sh
   ```
2. **Remove User Configuration & Cached Data**:
   ```bash
   rm -rf ~/.config/auto-usbip
   ```
3. **Delete Application Binary / Folder**:
   ```bash
   rm -rf AutoUSBIP-QT-x86_64.AppImage autousbip-qt-client-linux-x86_64/
   ```

#### **Windows (Portable Mode)**
1. **Remove User Configuration & Cached Drivers**:
   - Delete `%APPDATA%\auto-usbip` (Configuration file `config.json`)
   - Delete `%LOCALAPPDATA%\auto-usbip` (Downloaded driver cache, if applicable)
   *Or run in PowerShell:*
   ```powershell
   Remove-Item -Recurse -Force "$env:APPDATA\auto-usbip" -ErrorAction SilentlyContinue
   Remove-Item -Recurse -Force "$env:LOCALAPPDATA\auto-usbip" -ErrorAction SilentlyContinue
   ```
2. **Delete the Portable Folder**:
   - Simply delete the extracted folder containing `autousbip-qt-client.exe`.

> [!NOTE]
> If you used the **Windows MSI Installer** (`AutoUSBIP-QT-Client.msi`), standard uninstallation via **Windows Settings > Installed Apps** or the Start Menu shortcut automatically removes the executable, drivers, and both `%APPDATA%` and `%LOCALAPPDATA%` directories cleanly.

---

### 🔨 Building Release Packages from Source

All individual target builders are located in [`scripts/`](scripts/):

| Target Package | Builder Script | Output Artifact |
| :--- | :--- | :--- |
| **Linux AppImage** | `bash scripts/build-appimage.sh` | `dist/AutoUSBIP-QT-x86_64.AppImage` |
| **Linux Portable Tarball** | `bash scripts/build-tarball.sh` | `dist/AutoUSBIP-QT-x86_64.tar.gz` |
| **Linux Standalone Server** | `bash scripts/build-server-binary.sh` | `dist/autousbip-qt-server` |
| **Windows Client (Single EXE)** | `scripts\build-windows-client-exe.bat` | `dist\autousbip-qt-client.exe` |
| **Windows Client (MSI Setup)** | `scripts\build-windows-msi.bat` | `dist\AutoUSBIP-QT-Client-Setup.msi` |
| **Windows Server Daemon** | `scripts\build-windows-server-exe.bat` | `dist\autousbip-qt-server.exe` |

---

### 🪟 Windows Client & Server Releases

#### 1. Windows Client (`autousbip-qt-client.exe` & MSI Installer)
* **Single-file Portable EXE**: Run `scripts\build-windows-client-exe.bat` to produce `dist\autousbip-qt-client.exe`.
* **WiX MSI Setup Package**: Run `scripts\build-windows-msi.bat` to compile `dist\AutoUSBIP-QT-Client-Setup.msi` with customized setup UI dialogs and auto-cleanup actions.
* On first launch, the client automatically verifies and configures the signed `usbip-win` VHCI driver.

#### 2. Windows Server Daemon (`autousbip-qt-server.exe`)
1. Run `scripts\build-windows-server-exe.bat` to build the standalone server executable.
2. The compiled binary is output to `dist\autousbip-qt-server.exe`.

---

## 🎮 Integrated Gamepad Tester

Click **Test Gamepad** on any attached controller to open diagnostics:

* **Vector SVG Visuals**: Powered by Kenney vector input prompts, scaling to any resolution.
* **Controller Identification**: Matches hardware signatures against `SDL_GameControllerDB` for button layouts (Nintendo A/B/X/Y, PlayStation Cross/Circle/Square/Triangle, Xbox A/B/X/Y, NES/SNES).
* **Sensors & Telemetry**:
  * `Touchpad`: Absolute multi-touch coordinates and click state.
  * `Accelerometer`: 3-axis gravity and tilt forces in m/s².
  * `Gyroscope`: 3-axis rotational velocity in rad/s.
  * `Adaptive Triggers`: Position resistance, machine-gun recoil, and feedback triggers.
  * `RGB Lightbar`: 24-bit customizable illumination and player LEDs.

---

## 📜 Credits & Licenses

This project is open-source software licensed under the **[MIT License](LICENSE)**.

### Upstream Lineage & Attribution
* **Original Project**: Derived and expanded from [`florianL21/auto-usbip`](https://github.com/florianL21/auto-usbip) (MIT License, Copyright © 2023 florianL21).

### Third-Party Assets & Libraries
* **[Kenney Input Prompts](https://kenney.nl/assets/input-prompts)**: Gamepad button, stick, and trigger vector graphics by **Kenney** ([CC0 1.0 Universal — Public Domain](https://creativecommons.org/publicdomain/zero/1.0/)).
* **[SDL_GameControllerDB](https://github.com/mdqinc/SDL_GameControllerDB)**: Community database of game controller mappings ([zlib License](https://github.com/mdqinc/SDL_GameControllerDB/blob/master/LICENSE)).
* **[Linux USB ID Repository](http://www.linux-usb.org/usb.ids)**: USB vendor and device identity dictionary ([GPL-2.0 / 3-Clause BSD](http://www.linux-usb.org/)).
* **[PyQt6 & Qt Framework](https://pypi.org/project/PyQt6/)**: Python GUI & WebEngine bindings by Riverbank Computing & The Qt Company ([GPL v3 / LGPL v3](https://www.riverbankcomputing.com/software/pyqt/license)).
* **[python-zeroconf](https://github.com/python-zeroconf/python-zeroconf)**: Pure-Python Multicast DNS Service Discovery library ([LGPL-2.1+](https://github.com/python-zeroconf/python-zeroconf/blob/master/COPYING)).
* **[pyserial](https://github.com/pyserial/pyserial)**: Python Serial Port Extension library ([BSD-3-Clause](https://github.com/pyserial/pyserial/blob/master/LICENSE.txt)).
* **[pyudev](https://github.com/pyudev/pyudev)**: Pure-Python libudev binding for hardware device management ([LGPL-2.1+](https://github.com/pyudev/pyudev/blob/master/COPYING)).

---

## 🤖 AI-Assisted Development Disclosure

In the spirit of open-source transparency:
* This project was designed, co-authored, and refactored with the assistance of **Google DeepMind / Antigravity AI** coding models.
* AI pair programming was used for modularization, diagnostic protocol design, multi-touch event decoders, SDL database integration, and UI design.
* Third-party libraries and assets were vetted for license compatibility.

---

## 📄 License

```text
MIT License

Copyright (c) 2023 florianL21
Copyright (c) 2026 Marc Lemieux & Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
