#!/usr/bin/env bash
# ==============================================================================
# Auto USB/IP - Modern Security Installer (Polkit, AppArmor, udev, Systemd)
# Replaces sudoers with fine-grained authorization, MAC confinement, and udev rules.
# ==============================================================================

set -e

if [ "$EUID" -ne 0 ]; then
  echo "❌ Please run as root: sudo ./install-security.sh"
  exit 1
fi

echo "🛡️ Installing Auto USB/IP Security Policies..."

# 1. Install Polkit Policy & Rules (Client)
if [ -d "/usr/share/polkit-1/actions" ]; then
  echo "  • Installing Polkit policy (/usr/share/polkit-1/actions/org.autousbip.client.policy)..."
  cp client/security/polkit/org.autousbip.client.policy /usr/share/polkit-1/actions/
fi

if [ -d "/etc/polkit-1/rules.d" ]; then
  echo "  • Installing Polkit JavaScript rules (/etc/polkit-1/rules.d/50-autousbip.rules)..."
  cp client/security/polkit/50-autousbip.rules /etc/polkit-1/rules.d/
  chmod 644 /etc/polkit-1/rules.d/50-autousbip.rules
fi

# 2. Install udev Rules (Client & Server)
if [ -d "/etc/udev/rules.d" ]; then
  echo "  • Installing udev rules (/etc/udev/rules.d/99-autousbip.rules)..."
  cp client/security/udev/99-autousbip-client.rules /etc/udev/rules.d/99-autousbip-client.rules
  cp server/security/udev/99-autousbip-server.rules /etc/udev/rules.d/99-autousbip-server.rules
  udevadm control --reload-rules && udevadm trigger || true
fi

# 3. Install AppArmor Profiles (if AppArmor is active)
if command -v apparmor_parser >/dev/null 2>&1 && [ -d "/etc/apparmor.d" ]; then
  echo "  • Installing AppArmor profiles (/etc/apparmor.d/)..."
  cp client/security/apparmor/autousbip-client /etc/apparmor.d/autousbip-client
  cp server/security/apparmor/usr.local.bin.autousbip /etc/apparmor.d/usr.local.bin.autousbip
  apparmor_parser -r -T /etc/apparmor.d/autousbip-client 2>/dev/null || true
  apparmor_parser -r -T /etc/apparmor.d/usr.local.bin.autousbip 2>/dev/null || true
fi

# 4. Install Hardened Systemd Service (Server)
if [ -d "/etc/systemd/system" ]; then
  echo "  • Installing hardened systemd service (/etc/systemd/system/autousbip.service)..."
  cp server/autousbip.service /etc/systemd/system/autousbip.service
  systemctl daemon-reload || true
fi

echo "✅ Security policies installed successfully! No passwordless sudoers rules required."
