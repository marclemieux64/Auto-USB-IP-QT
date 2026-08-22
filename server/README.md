# AutoUSBIP-QT — Server Daemon

Lightweight, high-performance background daemon for exporting USB devices over the network from Raspberry Pi, Orange Pi, Debian, Ubuntu, Arch Linux, Fedora, or any Linux server.

---

## 🚀 Installation & Deployment Methods

### Method 1: Self-Installing Standalone Binary (Recommended)
You can deploy the server as a single compiled executable with zero external dependencies:

```bash
# 1. Download or copy the binary to your server:
chmod +x ./autousbip-qt-server

# 2. To test in temporary foreground mode (stops when you press Ctrl+C, no files installed):
sudo ./autousbip-qt-server

# 3. To PERMANENTLY install as a systemd background service (auto-starts on boot):
sudo ./autousbip-qt-server --install

# 4. To cleanly uninstall and remove all systemd services & files:
sudo ./autousbip-qt-server --uninstall
```

---

### Method 2: Automated 1-Command Web Installer
Run this single command on your Raspberry Pi / Linux server:

```bash
curl -fsSL https://raw.githubusercontent.com/marclemieux64/Auto-USB-IP-QT/dev/server/install-server.sh | sudo bash
```

This will automatically:
1. Install system utilities (`usbip`, `openssl`, `uhubctl`, `avahi-utils`).
2. Load and persist `usbip_core` and `usbip_host` kernel modules across reboots.
3. Install `autousbip-qt-server.py` to `/usr/local/bin/autousbip-qt-server.py`.
4. Deploy Polkit security policies to `/usr/share/polkit-1/actions/`.
5. Configure, enable, and start `autousbip-qt-server.service` under systemd.

---

## 📦 Zero-Dependency Architecture

`autousbip-qt-server.py` has **100% zero external pip dependencies** and runs directly on the bare Python standard library:
* **USB Hotplug Detection**: Uses direct Linux kernel Netlink sockets (`AF_NETLINK(15)`) with automatic `pyudev` fallback.
* **Network Discovery (mDNS)**: Uses native `avahi-publish-service` with automatic `zeroconf` fallback.
* **Security & TLS**: Uses Python's built-in `ssl` module with self-signed certificate generation.

---

## 🛠️ Service Management

```bash
# Check service status
sudo systemctl status autousbip-qt-server.service

# View live daemon logs
sudo journalctl -u autousbip-qt-server.service -f

# Restart daemon
sudo systemctl restart autousbip-qt-server.service

# Stop daemon
sudo systemctl stop autousbip-qt-server.service
```
