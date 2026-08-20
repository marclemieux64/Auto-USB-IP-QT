<div align="center">

<img src="client/assets/branding/app-logo.svg" alt="Auto USB/IP Qt Banner" width="560">

# Auto USB/IP Qt

**Seamless, encrypted Network USB forwarding with ZeroConf discovery, Polkit/AppArmor security, rich web dashboard, remote server console, and full-fidelity gamepad diagnostics.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green.svg)](https://pypi.org/project/PyQt6/)
[![Security: Polkit & AppArmor](https://img.shields.io/badge/Security-Polkit%20%7C%20AppArmor-red.svg)](client/security/)
[![Packaging: AppImage & Tarball](https://img.shields.io/badge/Packaging-AppImage%20%7C%20Tarball-blueviolet.svg)](dist/)
[![Linux](https://img.shields.io/badge/OS-Linux%20%7C%20Windows-lightgrey.svg)](https://github.com/)

[Key Features](#-key-features) • [Architecture](#-architecture) • [Security & Privileges](#-security--privilege-model) • [Server Setup](#-server-installation-raspberry-pi--linux) • [Client Setup](#-client-distribution--installation) • [Gamepad Diagnostics](#-integrated-gamepad-tester) • [Credits & Licenses](#-credits--licenses) • [AI Disclosure](#-ai-assisted-development-disclosure)

</div>

---

## 🚀 Key Features

* ⚡ **Zero-Configuration Server Discovery**: Uses pure-Python mDNS (Zeroconf / DNS-SD) to automatically broadcast and discover remote USB/IP servers on the local subnet without manual IP configuration.
* 🔒 **Zero-Sudo Security Architecture**:
  * **Polkit D-Bus Policies**: Replaces legacy `sudoers` with granular PolicyKit actions (`org.autousbip.client.*`).
  * **AppArmor Profiles**: Sandboxes both client and server processes to enforce strict file and capability boundaries.
  * **udev Access Rules**: Direct non-root access to USB devices and gamepad telemetry via `uaccess`.
  * **Systemd Ambient Capabilities**: Hardens daemons using `CAP_NET_ADMIN`, `CAP_SYS_ADMIN`, and `CAP_SYS_RAWIO` with `PrivateTmp=true`.
* 🛡️ **Encrypted Remote Communication (TLS 1.3 / 1.2)**: All control commands, log streaming, and telemetry sockets run over encrypted TLS with auto-generated self-signed certificates or custom CA certificates.
* 🖥️ **High-Tech Web Dashboard**:
  * Fast, sleek, dark-mode management interface accessible locally or across the LAN (`http://<client-ip>:3242/`).
  * Full real-time configuration modals for both Server and Client settings (TLS, discovery, subnet filters, VBUS power delay, auto-attach, audio cues).
* 📟 **Interactive Diagnostic Consoles**:
  * **Client Diagnostics Console**: Live in-memory log streamer, regex search, log levels, and interactive CLI shell.
  * **Remote Server Console**: Real-time remote `journalctl` daemon log streaming, CPU temperature/uptime telemetry, and remote management commands (`status`, `metrics`, `rebind`, `restart`, `reboot`).
* 🎮 **Full-Fidelity Gamepad Tester**:
  * **Pure Vector SVG Kenney Assets**: Resolution-independent button prompts for Nintendo, PlayStation, Xbox, and NES/SNES layouts.
  * **`SDL_GameControllerDB`**: Community hardware auto-mapping with physical controller profiles.
  * Real-time analog stick, trigger, and D-pad evaluation with visual deadzone rendering.
  * Multi-touch trackpad visualizer with absolute touch coordinates.
  * Independent **Accelerometer** & **Gyroscope** 6-Axis IMU motion telemetry.
  * **Sony DualSense** interactive hardware controls: 24-bit RGB lightbar illumination, player LEDs, microphone mute button, motorized adaptive triggers (resistance, recoil, vibration), and rumble tests.
* 💤 **Sleep & Wake Auto-Recovery**: Automatically cleans zombie connections and re-binds remote USB ports upon system resume using `systemd-login1` D-Bus signals and a monotonic jump watchdog.
* 📦 **Portable Release Packaging**: 1-click build script producing both self-contained **AppImage** and portable **Tarball** releases with zero host dependency requirements.

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

Auto USB/IP Qt provides a multi-layered, enterprise-grade defense-in-depth security model where **all hardening features are configurable and optional**:

### 1. Zero-Sudo Privilege Model
* **Polkit (PolicyKit)**: Rules defined in [`client/security/polkit/`](client/security/polkit/) allow non-root users to attach/detach kernel USB devices via D-Bus without `sudoers` or root shells.
* **AppArmor MAC Profiles**: Confines client and server binaries on Debian/Ubuntu/openSUSE ([`client/security/apparmor/`](client/security/apparmor/) & [`server/security/apparmor/`](server/security/apparmor/)).
* **SELinux Policy Modules**: Native CIL & Type Enforcement policies for Fedora, Bazzite, RHEL, and CentOS ([`client/security/selinux/`](client/security/selinux/) & [`server/security/selinux/`](server/security/selinux/)).
* **udev `uaccess` Rules**: Non-root desktop access to physical gamepad telemetry and sysfs nodes ([`client/security/udev/`](client/security/udev/) & [`server/security/udev/`](server/security/udev/)).
* **Automated Security Installer**: Run `./install-security.sh` on both client and server to auto-detect and deploy all policies.

### 2. Optional Hardening Controls (Configurable in Dashboard)
* 🔒 **Web API CSRF & Cross-Origin Protection**: Restricts mutating API actions (attach, detach, restart, reboot) to requests originating from `localhost` or verified client IP addresses.
* 🔑 **TLS Certificate Pinning (Trust-On-First-Use / TOFU)**: Automatically records and validates the SHA-256 fingerprint of the server's TLS certificate to detect Man-in-the-Middle (MitM) attacks.
* 🦹 **BadUSB Device Class Filtering**: Restricts auto-attaching rogue USB devices by class:
  * Block Mass Storage / Flash Drives (Class 08h)
  * Block Virtual Network / Ethernet / Wi-Fi Adapters (Classes 02h/E0h)
  * Block Raw USB Keyboards (Keystroke Injection / Rubber Ducky defense)
* 🔥 **1-Click Server Firewall Script**:
  ```bash
  sudo bash scripts/setup-firewall.sh 192.168.2.0/24
  ```
  Restricts ports `3240/tcp` (usbip), `3241/tcp` (TLS control), and `5353/udp` (mDNS) strictly to your trusted LAN subnet.

---

## 📦 Server Installation (Raspberry Pi / Linux)

### 1. Prerequisites
```bash
# Install USB/IP tools and dependencies
sudo apt update
sudo apt install -y usbip hwdata python3 python3-pip

# Enable usbip-host kernel module at boot
echo "usbip-host" | sudo tee -a /etc/modules
sudo modprobe usbip-host
```

### 2. Deploy Server Daemon & Security Policies
```bash
# Clone the repository
git clone https://github.com/your-username/auto-usbip.git
cd auto-usbip

# 1. Install security policies (Polkit, AppArmor, udev, Systemd capabilities)
sudo ./install-security.sh

# 2. Deploy daemon and start service
sudo cp server/autousbip.py /usr/local/bin/autousbip.py
sudo chmod 755 /usr/local/bin/autousbip.py

sudo cp server/autousbip.service /etc/systemd/system/autousbip.service
sudo systemctl daemon-reload
sudo systemctl enable --now autousbip.service
```

---

## 💻 Client Distribution & Installation

Auto USB/IP Client is distributed as **both a portable AppImage and a standalone Tarball** with zero external dependencies. It runs out-of-the-box on **Ubuntu, Fedora, Arch Linux, Bazzite, SteamOS, Debian, and openSUSE**.

### Option 1: Portable AppImage (Recommended)
```bash
# 1. Ensure kernel VHCI driver is loaded
sudo modprobe vhci-hcd

# 2. Make executable and launch
chmod +x dist/Auto-USBIP-x86_64.AppImage
./dist/Auto-USBIP-x86_64.AppImage

# 3. (Optional) Integrate into your Desktop Application Menu
./dist/Auto-USBIP-x86_64.AppImage --install
```

### Option 2: Standalone Portable Tarball (.tar.gz)
```bash
# 1. Extract tarball
tar -xzf dist/Auto-USBIP-x86_64.tar.gz
cd auto-usbip-client-linux-x86_64

# 2. Run directly
./autousbip-client

# 3. (Optional) Add to Desktop Application Menu
./install-menu.sh
```

---

### 🔨 Building Release Artifacts from Source
To build both `Auto-USBIP-x86_64.AppImage` and `Auto-USBIP-x86_64.tar.gz`:
```bash
bash scripts/build-appimage.sh
```
The output binaries will be created in [`dist/`](dist/).

---

### Windows
1. Install the [usbip-win](https://github.com/cezanne/usbip-win) signed VHCI driver.
2. In the `client/` folder:
   ```cmd
   python -m venv venv
   .env\Scripts\pip install -r requirements.txt
   .env\Scripts\python client.py
   ```

---

## 🎮 Integrated Gamepad Tester

The client includes an advanced real-time controller testing environment accessible by clicking **Test Gamepad** on any attached controller.

* **Vector SVG Visuals**: Powered by Kenney vector input prompts, scaling crisply to any resolution.
* **Controller Identification**: Matches hardware signatures against `SDL_GameControllerDB` for authentic button layouts (Nintendo A/B/X/Y, PlayStation Cross/Circle/Square/Triangle, Xbox A/B/X/Y, NES/SNES layouts).
* **Sensors & Telemetry**:
  * `Touchpad`: Absolute multi-touch coordinates & click state visualizer.
  * `Accelerometer`: 3-axis gravity & tilt forces in m/s².
  * `Gyroscope`: 3-axis rotational velocity in rad/s.
  * `Adaptive Triggers`: Real-time position resistance, machine-gun recoil, and feedback triggers.
  * `RGB Lightbar`: 24-bit customizable illumination and player LEDs.

---

## 📜 Credits & Licenses

This project is open-source software licensed under the **[MIT License](LICENSE)**.

### Upstream Lineage & Attribution
* **Original Project**: Derived and expanded from [`florianL21/auto-usbip`](https://github.com/florianL21/auto-usbip) (MIT License, Copyright © 2023 florianL21).

### Third-Party Assets & Libraries
* **[Kenney Input Prompts](https://kenney.nl/assets/input-prompts)**: Gamepad button, stick, and trigger vector graphics created by **Kenney** ([CC0 1.0 Universal — Public Domain](https://creativecommons.org/publicdomain/zero/1.0/)).
* **[SDL_GameControllerDB](https://github.com/mdqinc/SDL_GameControllerDB)**: Community database of game controller mappings ([zlib License](https://github.com/mdqinc/SDL_GameControllerDB/blob/master/LICENSE)).
* **[Linux USB ID Repository](http://www.linux-usb.org/usb.ids)**: USB vendor and device identity dictionary ([GPL-2.0 / 3-Clause BSD](http://www.linux-usb.org/)).
* **[PyQt6 & Qt Framework](https://pypi.org/project/PyQt6/)**: Python GUI & WebEngine bindings by Riverbank Computing & The Qt Company ([GPL v3 / LGPL v3](https://www.riverbankcomputing.com/software/pyqt/license)).
* **[python-zeroconf](https://github.com/python-zeroconf/python-zeroconf)**: Pure-Python Multicast DNS (mDNS / Zeroconf) Service Discovery library ([LGPL-2.1+](https://github.com/python-zeroconf/python-zeroconf/blob/master/COPYING)).
* **[pyserial](https://github.com/pyserial/pyserial)**: Python Serial Port Extension library ([BSD-3-Clause](https://github.com/pyserial/pyserial/blob/master/LICENSE.txt)).
* **[pyudev](https://github.com/pyudev/pyudev)**: Pure-Python libudev binding for hardware device management ([LGPL-2.1+](https://github.com/pyudev/pyudev/blob/master/COPYING)).

---

## 🤖 AI-Assisted Development Disclosure

In the spirit of open-source transparency and responsible AI development:
* This project was designed, co-authored, and refactored with the assistance of **Google DeepMind / Antigravity AI** agentic coding models.
* AI pair programming was used for architectural modularization, diagnostic protocol design, multi-touch event decoders, SDL database integration, and UI design.
* All third-party libraries and assets were vetted to ensure strict license compatibility and absence of copyright infringement.

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
