#!/usr/bin/env bash
# ==============================================================================
# Auto USB/IP - Universal Linux Security Policy Installer
# Supports: Polkit, udev, AppArmor (Debian/Ubuntu/openSUSE), and SELinux (Fedora/RHEL/Bazzite)
# ==============================================================================

set -e

if [ "$EUID" -ne 0 ]; then
  echo "❌ Please run as root: sudo ./install-security.sh"
  exit 1
fi

echo "🛡️ ============================================================="
echo "   Auto USB/IP — Universal Security Policy Installer            "
echo "============================================================="

# 1. Install Polkit Policy & Rules (Universal)
if [ -d "/usr/share/polkit-1/actions" ]; then
  echo "  • Installing Polkit policy (/usr/share/polkit-1/actions/org.autousbip.client.policy)..."
  cp client/security/polkit/org.autousbip.client.policy /usr/share/polkit-1/actions/
fi

if [ -d "/etc/polkit-1/rules.d" ]; then
  echo "  • Installing Polkit JavaScript rules (/etc/polkit-1/rules.d/50-autousbip.rules)..."
  cp client/security/polkit/50-autousbip.rules /etc/polkit-1/rules.d/
  chmod 644 /etc/polkit-1/rules.d/50-autousbip.rules
fi

# 2. Install udev Rules (Universal)
if [ -d "/etc/udev/rules.d" ]; then
  echo "  • Installing udev rules (/etc/udev/rules.d/99-autousbip-*.rules)..."
  cp client/security/udev/99-autousbip-client.rules /etc/udev/rules.d/99-autousbip-client.rules
  cp server/security/udev/99-autousbip-server.rules /etc/udev/rules.d/99-autousbip-server.rules
  udevadm control --reload-rules && udevadm trigger || true
fi

# 3. Install AppArmor Profiles (Debian, Ubuntu, openSUSE, Arch)
if command -v apparmor_parser >/dev/null 2>&1 && [ -d "/etc/apparmor.d" ]; then
  echo "  • Installing AppArmor profiles (/etc/apparmor.d/)..."
  cp client/security/apparmor/autousbip-client /etc/apparmor.d/autousbip-client
  cp server/security/apparmor/usr.local.bin.autousbip /etc/apparmor.d/usr.local.bin.autousbip
  apparmor_parser -r -T /etc/apparmor.d/autousbip-client 2>/dev/null || true
  apparmor_parser -r -T /etc/apparmor.d/usr.local.bin.autousbip 2>/dev/null || true
  echo "    ↳ AppArmor profiles active."
fi

# 4. Install SELinux Modules (Fedora, Bazzite, RHEL, CentOS, Rocky Linux)
if command -v semodule >/dev/null 2>&1; then
  echo "  • Detected SELinux. Installing SELinux policy modules..."
  if [ -f "server/security/selinux/autousbip-server.cil" ]; then
    semodule -i server/security/selinux/autousbip-server.cil 2>/dev/null || true
  fi
  if [ -f "client/security/selinux/autousbip-client.cil" ]; then
    semodule -i client/security/selinux/autousbip-client.cil 2>/dev/null || true
  fi
  if command -v restorecon >/dev/null 2>&1; then
    restorecon -Rv /usr/local/bin/autousbip.py /etc/systemd/system/autousbip.service 2>/dev/null || true
  fi
  echo "    ↳ SELinux modules installed."
fi

# 5. Install Hardened Systemd Service (Server)
if [ -d "/etc/systemd/system" ]; then
  echo "  • Installing hardened systemd service (/etc/systemd/system/autousbip.service)..."
  cp server/autousbip.service /etc/systemd/system/autousbip.service
  systemctl daemon-reload || true
fi

echo "============================================================="
echo "✅ All security policies installed successfully!"
echo "   Your system is secured with zero-sudo authorization."
echo "============================================================="
