from __future__ import annotations

import json
import logging
import socket
import ssl

logger = logging.getLogger("auto-usbip-client")


class ServerControlClient:
    def __init__(self, ip: str, port: int = 3241, timeout: float = 5.0, token: str = "", use_tls: bool = True) -> None:
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.token = token
        self.use_tls = use_tls

    def _send_cmd(self, payload: dict) -> dict | None:
        if self.token and "token" not in payload:
            payload["token"] = self.token
        data_bytes = json.dumps(payload).encode("utf-8")

        # 1. Try TLS Encrypted Socket first if enabled
        if self.use_tls:
            try:
                raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                raw_sock.settimeout(self.timeout)
                raw_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE

                s = ctx.wrap_socket(raw_sock, server_hostname=self.ip)
                s.connect((self.ip, self.port))

                # Optional TLS Certificate Pinning (Trust-On-First-Use)
                try:
                    import hashlib
                    from config import load_config, save_config
                    der_cert = s.getpeercert(binary_form=True)
                    if der_cert:
                        fp = hashlib.sha256(der_cert).hexdigest().upper()
                        cfg = load_config()
                        if cfg.get("enable_tls_pinning", False):
                            pinned = cfg.get("pinned_certificates", {})
                            ip_clean = self.ip.strip()
                            if ip_clean not in pinned:
                                pinned[ip_clean] = fp
                                cfg["pinned_certificates"] = pinned
                                save_config(cfg)
                                logger.info(f"[Security] Pinned TLS certificate fingerprint for {ip_clean}: {fp[:16]}...")
                            elif pinned[ip_clean] != fp:
                                logger.error(f"[Security Alert] TLS certificate fingerprint mismatch for {ip_clean}! Expected {pinned[ip_clean]}, got {fp}. Connection blocked.")
                                s.close()
                                return {"status": "error", "message": f"TLS Certificate Pinning Mismatch! Expected {pinned[ip_clean][:16]}..., got {fp[:16]}..."}
                except Exception as pin_err:
                    logger.debug(f"TLS pinning check error: {pin_err}")

                s.sendall(data_bytes)

                chunks = []
                while True:
                    try:
                        data = s.recv(4096)
                        if not data:
                            break
                        chunks.append(data)
                    except Exception:
                        break
                s.close()
                raw = b"".join(chunks).decode("utf-8")
                if raw:
                    return json.loads(raw)
            except ssl.SSLError as e:
                logger.debug(f"TLS connection to {self.ip}:{self.port} failed ({e}), attempting unencrypted fallback...")
            except Exception as e:
                logger.debug(f"Encrypted control socket error ({self.ip}:{self.port}): {e}")

        # 2. Fallback to unencrypted socket if TLS is disabled or server is legacy
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self.timeout)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            s.connect((self.ip, self.port))
            s.sendall(data_bytes)

            chunks = []
            while True:
                try:
                    data = s.recv(4096)
                    if not data:
                        break
                    chunks.append(data)
                except Exception:
                    break
            s.close()
            raw = b"".join(chunks).decode("utf-8")
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.debug(f"ServerControlClient error ({self.ip}:{self.port}): {e}")

        return None

    def get_status(self) -> dict | None:
        return self._send_cmd({"cmd": "GET_STATUS"})

    def get_logs(self, lines: int = 100) -> dict | None:
        return self._send_cmd({"cmd": "GET_LOGS", "lines": lines})

    def reset_zombies(self) -> dict | None:
        return self._send_cmd({"cmd": "RESET_ZOMBIES"})

    def reset_power(self, ports: str | None = None, busid: str | None = None) -> dict | None:
        payload = {"cmd": "RESET_POWER"}
        if ports:
            payload["ports"] = ports
        if busid:
            payload["busid"] = busid
        return self._send_cmd(payload)

    def add_blacklist(self, vid_pid: str) -> dict | None:
        return self._send_cmd({"cmd": "ADD_BLACKLIST", "vid_pid": vid_pid})

    def remove_blacklist(self, vid_pid: str) -> dict | None:
        return self._send_cmd({"cmd": "REMOVE_BLACKLIST", "vid_pid": vid_pid})

    def get_config(self) -> dict | None:
        return self._send_cmd({"cmd": "GET_CONFIG"})

    def set_config(self, config: dict) -> dict | None:
        return self._send_cmd({"cmd": "SET_CONFIG", "config": config})

    def restart_daemon(self) -> dict | None:
        return self._send_cmd({"cmd": "RESTART_DAEMON"})

    def reboot_system(self) -> dict | None:
        return self._send_cmd({"cmd": "REBOOT_SYSTEM"})


def get_server_status(ip: str, token: str = "") -> dict | None:
    return ServerControlClient(ip, token=token).get_status()


def get_server_logs(ip: str, lines: int = 100, token: str = "") -> dict | None:
    return ServerControlClient(ip, token=token).get_logs(lines=lines)


def reset_zombies(ip: str, token: str = "") -> dict | None:
    return ServerControlClient(ip, token=token).reset_zombies()


def powercycle_remote_device(ip: str, busid: str, token: str = "") -> dict | None:
    return ServerControlClient(ip, token=token).reset_power(busid=busid)


def save_remote_server_config(ip: str, config: dict, token: str = "") -> dict | None:
    return ServerControlClient(ip, token=token).set_config(config)


def restart_remote_daemon(ip: str, token: str = "") -> dict | None:
    return ServerControlClient(ip, token=token).restart_daemon()


def reboot_remote_system(ip: str, token: str = "") -> dict | None:
    return ServerControlClient(ip, token=token).reboot_system()

# Aliases
set_server_config = save_remote_server_config
powercycle_device = powercycle_remote_device
restart_server_daemon = restart_remote_daemon
reboot_server_system = reboot_remote_system
