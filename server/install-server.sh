#!/usr/bin/env bash
# ==============================================================================
# AutoUSBIP-QT Server — Automated 1-Command Installer
# Works on Raspberry Pi OS, Debian, Ubuntu, Fedora, Arch Linux, Alpine
# Automatically configures Polkit, udev, AppArmor, SELinux, and systemd.
# ==============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}=====================================================${NC}"
echo -e "${GREEN}  ⚡ AutoUSBIP-QT Server Daemon Installer${NC}"
echo -e "${BLUE}=====================================================${NC}"

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[!] Please run as root or with sudo: sudo bash install-server.sh${NC}"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}[1/5] Installing system dependencies (usbip, openssl)...${NC}"
if command -v apt-get &>/dev/null; then
    apt-get update -qq || true
    apt-get install -y -qq usbip linux-tools-generic hwdata openssl uhubctl avahi-utils || true
elif command -v dnf &>/dev/null; then
    dnf install -y usbip hwdata openssl uhubctl avahi-tools || true
elif command -v pacman &>/dev/null; then
    pacman -Sy --noconfirm usbip hwdata openssl uhubctl || true
elif command -v zypper &>/dev/null; then
    zypper --non-interactive install usbip hwdata openssl uhubctl avahi-utils || true
elif command -v apk &>/dev/null; then
    apk add --no-cache usbip-tools hwdata openssl uhubctl avahi || true
elif command -v xbps-install &>/dev/null; then
    xbps-install -Sy usbip hwdata openssl uhubctl avahi || true
fi

echo -e "${BLUE}[2/5] Loading USB/IP kernel modules...${NC}"
modprobe usbip_core || true
modprobe usbip_host || true

# Persist modules across reboot
mkdir -p /etc/modules-load.d /etc/auto-usbip /root/.config/auto-usbip
cat << 'EOF_MODS' > /etc/modules-load.d/autousbip.conf
usbip_core
usbip_host
EOF_MODS

echo -e "${BLUE}[3/5] Installing autousbip daemon to /usr/local/bin/...${NC}"
if [ -f "$SCRIPT_DIR/autousbip.py" ]; then
    cp "$SCRIPT_DIR/autousbip.py" /usr/local/bin/autousbip-qt-server.py
elif [ -f "$SCRIPT_DIR/autousbip-qt-server" ]; then
    cp "$SCRIPT_DIR/autousbip-qt-server" /usr/local/bin/autousbip-qt-server
else
    echo -e "${YELLOW}Downloading latest autousbip.py from GitHub...${NC}"
    curl -fsSL https://raw.githubusercontent.com/marclemieux64/Auto-USB-IP-QT/dev/server/autousbip.py -o /usr/local/bin/autousbip-qt-server.py
fi
[ -f /usr/local/bin/autousbip-qt-server.py ] && chmod 755 /usr/local/bin/autousbip-qt-server.py
[ -f /usr/local/bin/autousbip-qt-server ] && chmod 755 /usr/local/bin/autousbip-qt-server

echo -e "${BLUE}[4/5] Installing Security Policies (Polkit, udev, AppArmor, SELinux)...${NC}"
# 1. Polkit Policy & Rules
if [ -d "/usr/share/polkit-1/actions" ] && [ -f "$SCRIPT_DIR/security/polkit/org.autousbip.server.policy" ]; then
    cp "$SCRIPT_DIR/security/polkit/org.autousbip.server.policy" /usr/share/polkit-1/actions/
fi
if [ -d "/etc/polkit-1/rules.d" ] && [ -f "$SCRIPT_DIR/security/polkit/10-autousbip-server.rules" ]; then
    cp "$SCRIPT_DIR/security/polkit/10-autousbip-server.rules" /etc/polkit-1/rules.d/
    chmod 644 /etc/polkit-1/rules.d/10-autousbip-server.rules
fi

# 2. udev Rules
if [ -d "/etc/udev/rules.d" ] && [ -f "$SCRIPT_DIR/security/udev/99-autousbip-server.rules" ]; then
    cp "$SCRIPT_DIR/security/udev/99-autousbip-server.rules" /etc/udev/rules.d/99-autousbip-server.rules
    udevadm control --reload-rules 2>/dev/null && udevadm trigger 2>/dev/null || true
fi

# 3. AppArmor Profile
if command -v apparmor_parser >/dev/null 2>&1 && [ -d "/etc/apparmor.d" ] && [ -f "$SCRIPT_DIR/security/apparmor/usr.local.bin.autousbip" ]; then
    cp "$SCRIPT_DIR/security/apparmor/usr.local.bin.autousbip" /etc/apparmor.d/usr.local.bin.autousbip
    apparmor_parser -r -T /etc/apparmor.d/usr.local.bin.autousbip 2>/dev/null || true
fi

# 4. SELinux Modules
if command -v semodule >/dev/null 2>&1 && [ -f "$SCRIPT_DIR/security/selinux/autousbip-server.cil" ]; then
    semodule -i "$SCRIPT_DIR/security/selinux/autousbip-server.cil" 2>/dev/null || true
    if command -v restorecon >/dev/null 2>&1; then
        restorecon -Rv /usr/local/bin/autousbip-qt-server* /etc/systemd/system/autousbip-qt-server.service 2>/dev/null || true
    fi
fi

echo -e "${BLUE}[5/5] Configuring systemd service...${NC}"
SERVER_EXEC="/usr/local/bin/autousbip-qt-server.py"
if [ -f "/usr/local/bin/autousbip-qt-server" ]; then
    SERVER_EXEC="/usr/local/bin/autousbip-qt-server"
fi

cat << EOF_SVC > /etc/systemd/system/autousbip-qt-server.service
[Unit]
Description=AutoUSBIP-QT Server Daemon
After=network-online.target systemd-udevd.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=${SERVER_EXEC}
Restart=on-failure
RestartSec=3s

# Security Hardening & Linux Capabilities
CapabilityBoundingSet=CAP_NET_ADMIN CAP_SYS_ADMIN CAP_SYS_RAWIO
AmbientCapabilities=CAP_NET_ADMIN CAP_SYS_ADMIN CAP_SYS_RAWIO
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=-/etc/auto-usbip -/root/.config/auto-usbip /var/log /sys /dev
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF_SVC

systemctl daemon-reload
systemctl enable autousbip-qt-server.service
systemctl restart autousbip-qt-server.service

echo -e "${GREEN}=====================================================${NC}"
echo -e "${GREEN}  🎉 AutoUSBIP-QT Server installed & running!${NC}"
echo -e "${BLUE}  • Status:  sudo systemctl status autousbip-qt-server${NC}"
echo -e "${BLUE}  • Logs:    sudo journalctl -u autousbip-qt-server -f${NC}"
echo -e "${BLUE}  • TCP:     Ports 3240 (USB/IP) and 3241 (Control/TLS)${NC}"
echo -e "${GREEN}=====================================================${NC}"
