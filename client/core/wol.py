from __future__ import annotations

import sys

import logging
import os
import re
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger("auto-usbip-client")


def get_primary_network_interface() -> str | None:
    """Find the default route network interface (e.g. enp7s0, eth0, wlan0)."""
    try:
        r = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True, timeout=1.0)
        m = re.search(r"dev\s+([^\s]+)", r.stdout)
        if m:
            return m.group(1).strip()
    except Exception:
        pass

    try:
        net_dir = Path("/sys/class/net")
        if net_dir.exists():
            for p in net_dir.iterdir():
                if p.name != "lo" and not p.name.startswith(("docker", "veth", "virbr", "br-", "tailscale")):
                    return p.name
    except Exception:
        pass

    return None


def get_primary_mac_address() -> str | None:
    """Read the hardware MAC address of the active primary network adapter."""
    if sys.platform == "win32":
        try:
            import uuid
            node = uuid.getnode()
            if (node >> 40) % 2 == 0:
                mac_hex = f"{node:012x}"
                return ":".join(mac_hex[i:i+2] for i in range(0, 12, 2)).lower()
        except Exception:
            pass

    iface = get_primary_network_interface()
    if iface:
        try:
            mac_file = Path(f"/sys/class/net/{iface}/address")
            if mac_file.exists():
                mac = mac_file.read_text().strip().lower()
                if mac and mac != "00:00:00:00:00:00":
                    return mac
        except Exception:
            pass

    # Fallback to ip link
    try:
        r = subprocess.run(["ip", "link"], capture_output=True, text=True, timeout=1.0)
        matches = re.findall(r"link/ether\s+([0-9a-fA-F:]{17})", r.stdout)
        if matches:
            return matches[0].lower()
    except Exception:
        pass

    # Fallback to uuid.getnode()
    try:
        import uuid
        node = uuid.getnode()
        if (node >> 40) % 2 == 0:
            mac_hex = f"{node:012x}"
            return ":".join(mac_hex[i:i+2] for i in range(0, 12, 2)).lower()
    except Exception:
        pass

    return None


def enable_client_wake_on_lan() -> tuple[bool, str]:
    """Enable Wake-on-LAN (magic packet) on the primary active Ethernet/WiFi interface."""
    mac = get_primary_mac_address()
    if not mac:
        return False, "Could not detect active network MAC address"

    if sys.platform == "win32":
        return True, f"MAC: {mac} (Windows network adapter)"

    iface = get_primary_network_interface()

    success = False
    details = []

    # 1. NetworkManager persistent configuration
    if shutil.which("nmcli") and iface:
        try:
            res = subprocess.run(
                ["nmcli", "-t", "-f", "NAME,DEVICE,TYPE", "connection", "show", "--active"],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            for line in res.stdout.splitlines():
                parts = line.strip().split(":")
                if len(parts) >= 3 and parts[1] == iface and "ethernet" in parts[2]:
                    con_name = parts[0]
                    mod_res = subprocess.run(
                        ["nmcli", "connection", "modify", con_name, "802-3-ethernet.wake-on-lan", "magic"],
                        capture_output=True,
                        text=True,
                        timeout=1.5,
                    )
                    if mod_res.returncode == 0:
                        success = True
                        details.append(f"NetworkManager WoL set to 'magic' on '{con_name}'")
                        logger.info(f"Enabled Wake-on-LAN via nmcli on '{con_name}' ({iface})")
        except Exception as e:
            logger.debug(f"nmcli WoL error: {e}")

    # 2. ethtool immediate configuration
    if shutil.which("ethtool") and iface:
        try:
            cmd = ["ethtool", "-s", iface, "wol", "g"]
            if os.geteuid() != 0:
                if shutil.which("pkexec"):
                    cmd = ["pkexec", "--disable-internal-agent", "ethtool", "-s", iface, "wol", "g"]
                else:
                    cmd = ["sudo", "-n", "ethtool", "-s", iface, "wol", "g"]
            eth_res = subprocess.run(cmd, capture_output=True, text=True, timeout=1.5)
            if eth_res.returncode == 0:
                success = True
                details.append(f"ethtool set 'wol g' on {iface}")
                logger.info(f"Enabled Wake-on-LAN via ethtool on {iface}")
        except Exception as e:
            logger.debug(f"ethtool WoL error: {e}")

    desc = f"MAC: {mac}" + (f" ({', '.join(details)})" if details else "")
    return True, desc


def sync_client_wol_to_servers(controller: Any):
    """Notify all enabled servers of client MAC address and Wake-on-LAN configuration."""
    mac = get_primary_mac_address()
    if not mac:
        return

    enable_wol = getattr(controller.config, "enable_wol_wake", False)
    from core.server_control import ServerControlClient

    for srv in getattr(controller, "servers", []):
        if getattr(srv, "enabled", True):
            try:
                client = ServerControlClient(srv.ip, token=getattr(srv, "token", ""))
                client._send_cmd({"cmd": "REGISTER_WOL_CLIENT", "mac": mac, "enabled": enable_wol})
            except Exception as e:
                logger.debug(f"Error syncing WoL MAC to server {srv.ip}: {e}")
