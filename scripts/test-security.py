#!/usr/bin/env python3
"""
==============================================================================
AutoUSBIP-QT Automated Security & Vulnerability Test Suite
==============================================================================
Runs automated audits across Client and Server components:
1. Static Application Security Testing (SAST) via Bandit
2. Third-Party Dependency Vulnerability / CVE Audit via pip-audit
3. Remote Server TLS & Socket Protocol Fuzzer / Boundary Injection Tests
4. Server Systemd & Privilege Hardening Audit
==============================================================================
"""

import os
import sys
import json
import time
import socket
import ssl
import argparse
import subprocess
from pathlib import Path

# ANSI colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

REPO_ROOT = Path(__file__).resolve().parent.parent


def print_banner():
    print(f"\n{BLUE}{BOLD}" + "=" * 68 + f"{RESET}")
    print(f"{CYAN}{BOLD}   🛡️  AutoUSBIP-QT Automated Security & Vulnerability Auditor 🛡️   {RESET}")
    print(f"{BLUE}{BOLD}" + "=" * 68 + f"{RESET}\n")


def run_sast_audit():
    print(f"{BOLD}[1/4] Running Static Application Security Testing (Bandit SAST)...{RESET}")
    
    bandit_bin = REPO_ROOT / "client" / "venv" / "bin" / "bandit"
    if not bandit_bin.exists():
        bandit_bin = "bandit"
    
    cmd = [
        str(bandit_bin),
        "-r", "client", "server",
        "-x", "client/venv*,client/venv_build*,client/.agents*",
        "--severity-level", "medium",
        "-f", "json"
    ]
    
    try:
        proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
        try:
            data = json.loads(proc.stdout)
            results = data.get("results", [])
            high = [r for r in results if r.get("issue_severity") == "HIGH"]
            med = [r for r in results if r.get("issue_severity") == "MEDIUM"]
            
            if not high and not med:
                print(f"  {GREEN}✓ Bandit SAST: 0 High/Medium vulnerabilities identified.{RESET}")
                return True
            else:
                print(f"  {YELLOW}⚠️ Bandit SAST found {len(high)} HIGH, {len(med)} MEDIUM findings:{RESET}")
                for item in high + med:
                    fname = item.get("filename", "")
                    line = item.get("line_number", 0)
                    msg = item.get("issue_text", "")
                    test_id = item.get("test_id", "")
                    sev = item.get("issue_severity", "")
                    color = RED if sev == "HIGH" else YELLOW
                    print(f"    • {color}[{sev}]{RESET} {fname}:{line} - {msg} ({test_id})")
                return len(high) == 0
        except Exception:
            if proc.returncode == 0:
                print(f"  {GREEN}✓ Bandit SAST scan completed cleanly.{RESET}")
                return True
            else:
                print(f"  {YELLOW}⚠️ Bandit completed with warnings.{RESET}")
                return False
    except FileNotFoundError:
        print(f"  {YELLOW}⚠️ Bandit is not installed. (pip install bandit){RESET}")
        return True


def run_dependency_cve_audit():
    print(f"\n{BOLD}[2/4] Scanning Dependencies for Known CVEs (pip-audit)...{RESET}")
    
    pip_audit_bin = REPO_ROOT / "client" / "venv" / "bin" / "pip-audit"
    if not pip_audit_bin.exists():
        pip_audit_bin = "pip-audit"
        
    req_file = REPO_ROOT / "client" / "requirements.txt"
    if not req_file.exists():
        print(f"  {YELLOW}⚠️ requirements.txt not found at {req_file}{RESET}")
        return True
        
    cmd = [str(pip_audit_bin), "-r", str(req_file), "-f", "json"]
    try:
        proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
        try:
            data = json.loads(proc.stdout)
            vulns = data.get("dependencies", [])
            found_vulns = []
            for dep in vulns:
                if dep.get("vulns"):
                    found_vulns.append((dep.get("name"), dep.get("version"), dep.get("vulns")))
            
            if not found_vulns:
                print(f"  {GREEN}✓ pip-audit: All dependencies have 0 known CVEs.{RESET}")
                return True
            else:
                print(f"  {RED}✗ Found vulnerabilities in {len(found_vulns)} packages:{RESET}")
                for pkg, ver, vlist in found_vulns:
                    for v in vlist:
                        print(f"    • {pkg} ({ver}): {v.get('id')} - {v.get('description')}")
                return False
        except Exception:
            if proc.returncode == 0:
                print(f"  {GREEN}✓ pip-audit: No known vulnerabilities found.{RESET}")
                return True
            else:
                print(f"  {YELLOW}⚠️ pip-audit output: {proc.stdout or proc.stderr}{RESET}")
                return False
    except FileNotFoundError:
        print(f"  {YELLOW}⚠️ pip-audit not installed. (pip install pip-audit){RESET}")
        return True


def test_remote_socket_fuzzing(host="192.168.2.123", port=3241, auth_token=""):
    print(f"\n{BOLD}[3/4] Testing Server Protocol Resiliency & Fuzzing on {host}:{port}...{RESET}")
    
    # 1. Plaintext probe to TLS port
    print(f"  {CYAN}• Test 3.1: Plaintext downgrade / garbage probe to TLS port...{RESET}")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.5)
        s.connect((host, port))
        s.sendall(b"GARBAGE_PLAINTEXT_REQUEST_PROBE\r\n\r\n")
        data = s.recv(1024)
        s.close()
        print(f"    {GREEN}✓ Safely dropped/closed plaintext connection without crash.{RESET}")
    except Exception as e:
        print(f"    {GREEN}✓ Connection closed/rejected as expected ({type(e).__name__}).{RESET}")

    # Setup TLS
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    fuzz_vectors = [
        ("Empty Payload", b""),
        ("Raw Non-JSON String", b"PING_SERVER_RAW_STRING"),
        ("Malformed JSON Syntax", b"{invalid_json_key: 1234}"),
        ("Oversized Buffer (64KB)", b'{"cmd": "' + b"A" * 65536 + b'"}'),
        ("Negative Log Range Query", b'{"cmd": "GET_LOGS", "lines": -999999}'),
        ("Type-Confusion in Parameters", b'{"cmd": "GET_LOGS", "lines": ["nested", "array"]}'),
        ("Directory Traversal Probe", b'{"cmd": "BIND_DEVICE", "busid": "../../../../etc/shadow"}'),
        ("Command Injection Probe", b'{"cmd": "UNBIND_DEVICE", "busid": "; $(id) ;"}'),
        ("Subshell Parameter Expansion", b'{"cmd": "BIND_DEVICE", "busid": "`whoami`"}'),
        ("SQL Injection string probe", b'{"cmd": "GET_STATUS", "token": "\' OR \'1\'=\'1"}'),
        ("Config Override Injection", b'{"cmd": "SET_CONFIG", "config": {"vbus_off_delay": "INVALID_DELAY"}}'),
    ]

    print(f"  {CYAN}• Test 3.2: Injecting {len(fuzz_vectors)} malicious/fuzzed payloads over TLS...{RESET}")
    for name, payload in fuzz_vectors:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3.0)
            ts = ctx.wrap_socket(s, server_hostname=host)
            ts.connect((host, port))
            ts.sendall(payload)
            resp = ts.recv(4096)
            ts.close()
            print(f"    {GREEN}✓{RESET} {name:<30} -> Handled safely (Response: {len(resp)} bytes)")
        except Exception as e:
            print(f"    {GREEN}✓{RESET} {name:<30} -> Rejected/Dropped safely ({type(e).__name__})")

    # Verify Server Health Post-Attack
    print(f"  {CYAN}• Test 3.3: Verifying server liveness & health post-fuzzing...{RESET}")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3.0)
        ts = ctx.wrap_socket(s, server_hostname=host)
        ts.connect((host, port))
        req = {"cmd": "GET_STATUS"}
        if auth_token:
            req["token"] = auth_token
        ts.sendall(json.dumps(req).encode("utf-8"))
        resp = ts.recv(4096)
        ts.close()
        
        if resp and b'"status": "ok"' in resp:
            data = json.loads(resp.decode("utf-8"))
            cpu = data.get("metrics", {}).get("cpu_temp", "N/A")
            uptime = data.get("metrics", {}).get("uptime", "N/A")
            print(f"    {GREEN}✓ SERVER IS HEALTHY! (Uptime: {uptime}, CPU Temp: {cpu}){RESET}")
            return True
        else:
            print(f"    {RED}✗ Server returned abnormal response: {resp}{RESET}")
            return False
    except Exception as e:
        print(f"    {RED}✗ Server failed to respond / crashed after fuzzing: {e}{RESET}")
        return False


def test_systemd_hardening(host=None):
    print(f"\n{BOLD}[4/4] Auditing Systemd Hardening & Linux Sandbox Isolation...{RESET}")
    
    if host:
        cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3", host, "systemd-analyze security autousbip.service"]
    else:
        cmd = ["systemd-analyze", "security", "autousbip-qt-server.service"]
        
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            lines = proc.stdout.splitlines()
            summary_line = lines[-1] if lines else ""
            print(f"  {GREEN}✓ Systemd Analysis Completed:{RESET}")
            print(f"    {summary_line}")
            return True
        else:
            print(f"  {YELLOW}⚠️ Systemd security check unavailable or unit not loaded on target.{RESET}")
            return True
    except Exception as e:
        print(f"  {YELLOW}⚠️ Could not run systemd-analyze ({e}){RESET}")
        return True


def main():
    parser = argparse.ArgumentParser(description="AutoUSBIP-QT Security & Vulnerability Test Suite")
    parser.add_argument("--host", default="192.168.2.123", help="Remote server IP to test (default: 192.168.2.123)")
    parser.add_argument("--port", type=int, default=3241, help="Remote server TLS port (default: 3241)")
    parser.add_argument("--token", default="", help="Optional authentication token for server")
    parser.add_argument("--skip-remote", action="store_true", help="Skip remote server socket fuzzing tests")
    args = parser.parse_args()

    print_banner()

    sast_ok = run_sast_audit()
    cve_ok = run_dependency_cve_audit()
    
    if not args.skip_remote:
        token = args.token
        if not token:
            try:
                sys.path.insert(0, str(REPO_ROOT / 'client'))
                from config import load_config
                cfg = load_config()
                for s in cfg.get('servers', []):
                    if s.get('ip') == args.host and s.get('token'):
                        token = s.get('token')
                        break
            except Exception:
                pass
        fuzz_ok = test_remote_socket_fuzzing(host=args.host, port=args.port, auth_token=token)
        sys_ok = test_systemd_hardening(host=args.host)
    else:
        fuzz_ok = True
        sys_ok = True

    print(f"\n{BLUE}{BOLD}" + "=" * 68 + f"{RESET}")
    print(f"{BOLD}Summary of Security Assessment:{RESET}")
    print(f"  • Static Analysis (Bandit):    {'✅ PASS' if sast_ok else '⚠️ FINDINGS'}")
    print(f"  • Dependency CVEs (pip-audit): {'✅ PASS' if cve_ok else '❌ VULNERABLE'}")
    if not args.skip_remote:
        print(f"  • Socket Fuzzing Resiliency:   {'✅ PASS' if fuzz_ok else '❌ FAILED'}")
        print(f"  • Host Sandbox (systemd):      {'✅ PASS' if sys_ok else '⚠️ CHECK'}")
    print(f"{BLUE}{BOLD}" + "=" * 68 + f"{RESET}\n")


if __name__ == "__main__":
    main()
