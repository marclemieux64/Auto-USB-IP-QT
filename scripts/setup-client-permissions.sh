#!/usr/bin/env bash
# ==============================================================================
# AutoUSBIP-QT Client — Linux Permissions & Polkit Setup Script
# Works on standard distros and immutable distros (Fedora Silverblue/Atomic/Kinoite)
# ==============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}=====================================================${NC}"
echo -e "${GREEN}  ⚡ AutoUSBIP-QT Client Permissions Setup${NC}"
echo -e "${BLUE}=====================================================${NC}"

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[!] Please run as root or with sudo: sudo bash scripts/setup-client-permissions.sh${NC}"
    exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo -e "${BLUE}[1/4] Loading vhci-hcd kernel module...${NC}"
modprobe vhci-hcd 2>/dev/null || true

# Persist vhci-hcd module across reboots in /etc
mkdir -p /etc/modules-load.d
if ! grep -q "vhci-hcd" /etc/modules-load.d/autousbip-client.conf 2>/dev/null; then
    echo "vhci-hcd" > /etc/modules-load.d/autousbip-client.conf
fi

echo -e "${BLUE}[2/4] Installing Polkit rules in /etc/polkit-1/rules.d/...${NC}"
POLKIT_RULES_DIR="/etc/polkit-1/rules.d"
mkdir -p "${POLKIT_RULES_DIR}"

if [ -f "${REPO_ROOT}/client/security/polkit/50-autousbip.rules" ]; then
    cp -f "${REPO_ROOT}/client/security/polkit/50-autousbip.rules" "${POLKIT_RULES_DIR}/"
    chmod 644 "${POLKIT_RULES_DIR}/50-autousbip.rules"
fi

# Optional policy file (if /usr is writable)
POLKIT_POLICY_DIR="/usr/share/polkit-1/actions"
if [ -w "${POLKIT_POLICY_DIR}" ] && [ -f "${REPO_ROOT}/client/security/polkit/org.autousbip.client.policy" ]; then
    cp -f "${REPO_ROOT}/client/security/polkit/org.autousbip.client.policy" "${POLKIT_POLICY_DIR}/" 2>/dev/null || true
fi

echo -e "${BLUE}[3/4] Installing udev rules for hidraw / gamepads in /etc/udev/rules.d/...${NC}"
UDEV_RULES_DIR="/etc/udev/rules.d"
mkdir -p "${UDEV_RULES_DIR}"

if [ -f "${REPO_ROOT}/client/security/udev/99-autousbip-client.rules" ]; then
    cp -f "${REPO_ROOT}/client/security/udev/99-autousbip-client.rules" "${UDEV_RULES_DIR}/"
    chmod 644 "${UDEV_RULES_DIR}/99-autousbip-client.rules"
    udevadm control --reload-rules 2>/dev/null || true
    udevadm trigger 2>/dev/null || true
fi

echo -e "${BLUE}[4/4] Setting capability fallback on usbip binary if writable...${NC}"
USBIP_BIN="$(which usbip 2>/dev/null || true)"
if [ -n "${USBIP_BIN}" ] && [ -w "${USBIP_BIN}" ] && command -v setcap >/dev/null 2>&1; then
    setcap cap_net_admin,cap_sys_admin+ep "${USBIP_BIN}" 2>/dev/null || true
fi

echo -e "\n${GREEN}✅ Client permissions setup complete!${NC}"
echo -e "   Passwordless Polkit rules successfully installed in /etc/polkit-1/rules.d/50-autousbip.rules."
