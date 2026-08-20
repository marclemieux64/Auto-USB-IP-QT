#!/usr/bin/env bash
# ==============================================================================
# Auto USB/IP - Server Firewall & Subnet Hardening Helper
# ==============================================================================

set -e

echo "🛡️ ============================================================="
echo "   Auto USB/IP — Server Firewall & Subnet Hardening Helper      "
echo "============================================================="

# Detect local subnet automatically
DEFAULT_SUBNET=$(ip route | grep -v default | grep -m1 "src " | awk '{print $1}' || echo "192.168.2.0/24")
SUBNET="${1:-$DEFAULT_SUBNET}"

echo "Detected Subnet: ${SUBNET}"
echo "This script will restrict Auto USB/IP ports to your trusted subnet:"
echo "  • Port 3240/tcp (USB/IP raw device forwarding)"
echo "  • Port 3241/tcp (TLS encrypted remote control socket)"
echo "  • Port 5353/udp (mDNS / Zeroconf discovery)"
echo ""

if [ "$EUID" -ne 0 ]; then
    echo "⚠️ This script requires root privileges. Please run with sudo:"
    echo "   sudo bash scripts/setup-firewall.sh [subnet]"
    exit 1
fi

# Detect firewall backend
if command -v ufw >/dev/null 2>&1; then
    echo "🔥 Configuring UFW (Uncomplicated Firewall)..."
    ufw allow from "${SUBNET}" to any port 3240 proto tcp comment "Auto USB/IP Raw Forwarding"
    ufw allow from "${SUBNET}" to any port 3241 proto tcp comment "Auto USB/IP Control Socket"
    ufw allow from "${SUBNET}" to any port 5353 proto udp comment "Auto USB/IP mDNS Discovery"
    echo "✅ UFW rules applied successfully!"
    ufw status numbered | grep -E "3240|3241|5353" || true

elif command -v firewall-cmd >/dev/null 2>&1; then
    echo "🔥 Configuring firewalld..."
    firewall-cmd --permanent --new-zone=autousbip 2>/dev/null || true
    firewall-cmd --permanent --zone=autousbip --add-source="${SUBNET}"
    firewall-cmd --permanent --zone=autousbip --add-port=3240/tcp
    firewall-cmd --permanent --zone=autousbip --add-port=3241/tcp
    firewall-cmd --permanent --zone=autousbip --add-port=5353/udp
    firewall-cmd --reload
    echo "✅ firewalld rules applied successfully!"

elif command -v iptables >/dev/null 2>&1; then
    echo "🔥 Configuring iptables..."
    iptables -A INPUT -p tcp --dport 3240 -s "${SUBNET}" -j ACCEPT
    iptables -A INPUT -p tcp --dport 3241 -s "${SUBNET}" -j ACCEPT
    iptables -A INPUT -p udp --dport 5353 -s "${SUBNET}" -j ACCEPT
    echo "✅ iptables rules applied successfully!"
else
    echo "⚠️ No supported firewall found (UFW, firewalld, or iptables)."
fi

echo ""
echo "============================================================="
echo "🎉 Server firewall hardening complete for subnet ${SUBNET}!"
echo "============================================================="
