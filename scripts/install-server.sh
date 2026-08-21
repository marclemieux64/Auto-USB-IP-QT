#!/usr/bin/env bash
# ==============================================================================
# AutoUSBIP-QT Server — Automated 1-Command Installer
# Works on Raspberry Pi OS, Debian, Ubuntu, Fedora, Arch Linux, Alpine
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

echo -e "${BLUE}[1/4] Installing system dependencies (usbip, openssl)...${NC}"
if command -v apt-get &>/dev/null; then
    apt-get update -qq || true
    apt-get install -y -qq usbip linux-tools-generic hwdata openssl uhubctl avahi-utils || true
elif command -v dnf &>/dev/null; then
    dnf install -y usbip hwdata openssl uhubctl avahi-tools || true
elif command -v pacman &>/dev/null; then
    pacman -Sy --noconfirm usbip hwdata openssl uhubctl || true
fi

echo -e "${BLUE}[2/4] Loading USB/IP kernel modules...${NC}"
modprobe usbip_core || true
modprobe usbip_host || true

# Persist modules across reboot
cat << 'EOF_MODS' > /etc/modules-load.d/autousbip.conf
usbip_core
usbip_host
EOF_MODS

echo -e "${BLUE}[3/4] Installing autousbip daemon to /usr/local/bin/...${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/autousbip.py" ]; then
    cp "$SCRIPT_DIR/autousbip.py" /usr/local/bin/autousbip.py
else
    echo -e "${YELLOW}Downloading latest autousbip.py from GitHub...${NC}"
    curl -fsSL https://raw.githubusercontent.com/marclemieux64/Auto-USB-IP-QT/dev/server/autousbip.py -o /usr/local/bin/autousbip.py
fi
chmod 755 /usr/local/bin/autousbip.py

echo -e "${BLUE}[4/4] Installing Polkit security policy & configuring systemd...${NC}"
# Install Polkit policy and rules if polkit is present
if [ -d "/usr/share/polkit-1/actions" ]; then
    if [ -f "$SCRIPT_DIR/security/polkit/org.autousbip.server.policy" ]; then
        cp "$SCRIPT_DIR/security/polkit/org.autousbip.server.policy" /usr/share/polkit-1/actions/
    fi
fi
if [ -d "/etc/polkit-1/rules.d" ]; then
    if [ -f "$SCRIPT_DIR/security/polkit/10-autousbip-server.rules" ]; then
        cp "$SCRIPT_DIR/security/polkit/10-autousbip-server.rules" /etc/polkit-1/rules.d/
    fi
fi

cat << 'EOF_SVC' > /etc/systemd/system/autousbip.service
[Unit]
Description=AutoUSBIP-QT Server Daemon
After=network-online.target systemd-udevd.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/autousbip.py
Restart=on-failure
RestartSec=3s

# Security Hardening & Linux Capabilities
CapabilityBoundingSet=CAP_NET_ADMIN CAP_SYS_ADMIN CAP_SYS_RAWIO
AmbientCapabilities=CAP_NET_ADMIN CAP_SYS_ADMIN CAP_SYS_RAWIO
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/etc/auto-usbip /root/.config/auto-usbip /var/log /sys /dev
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF_SVC

systemctl daemon-reload
systemctl enable autousbip.service
systemctl restart autousbip.service

echo -e "${GREEN}=====================================================${NC}"
echo -e "${GREEN}  🎉 AutoUSBIP-QT Server installed & running!${NC}"
echo -e "${BLUE}  • Status:  sudo systemctl status autousbip${NC}"
echo -e "${BLUE}  • Logs:    sudo journalctl -u autousbip -f${NC}"
echo -e "${BLUE}  • TCP:     Ports 3240 (USB/IP) and 3241 (Control/TLS)${NC}"
echo -e "${GREEN}=====================================================${NC}"
