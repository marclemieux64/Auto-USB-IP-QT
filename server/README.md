# Auto USB/IP — Server Daemon

Lightweight, high-performance background daemon for exporting USB devices over the network from Raspberry Pi, Orange Pi, Debian, Ubuntu, or any Linux server.

---

## ⚡ Quick 1-Command Automated Installation

Run this single command on your Raspberry Pi / Linux server:

```bash
curl -fsSL https://raw.githubusercontent.com/marclemieux64/Auto-USB-IP-QT/dev/server/install-server.sh | sudo bash
```

This will automatically:
1. Install system utilities (`usbip`, `openssl`, `uhubctl`, `avahi-utils`).
2. Load and persist `usbip_core` and `usbip_host` kernel modules.
3. Install `autousbip.py` to `/usr/local/bin/autousbip.py`.
4. Configure, enable, and start `autousbip.service` under systemd.

---

## 📦 Zero-Dependency Architecture

`autousbip.py` has **100% zero external pip dependencies** and runs directly on bare Python standard library:
* **USB Hotplug**: Uses direct Linux kernel netlink sockets (`AF_NETLINK(15)`) with automatic `pyudev` fallback.
* **Network Discovery (mDNS)**: Uses system `avahi-publish-service` with automatic `zeroconf` fallback.
* **Security & TLS**: Uses Python's built-in `ssl` module with self-signed certificate generation.

---

## 🚀 Standalone Single Binary Executable

If you do not want to install Python on the server, you can use the pre-compiled single binary:

```bash
# Run the standalone binary directly:
sudo chmod +x ./dist/autousbip-server
sudo ./dist/autousbip-server
```

To compile a new binary:
```bash
bash scripts/build-server-binary.sh
```

---

## 🛠️ Service Management

```bash
# Check service status
sudo systemctl status autousbip

# View live daemon logs
sudo journalctl -u autousbip -f

# Restart daemon
sudo systemctl restart autousbip
```
