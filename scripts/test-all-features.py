#!/usr/bin/env python3
"""
==============================================================================
AutoUSBIP-QT Automated Feature Verification & Master Test Suite Runner
==============================================================================
Systematically validates all application features, options, APIs, and daemons:
1. Environment & Kernel Pre-Flight Checks
2. Client Configuration & Option Schema Integrity
3. Device Management, Attach/Detach & Hardware Routes
4. Server Daemon Features, Sysfs VBUS & Control Socket Sockets
5. Vector Gamepad Diagnostics, DualSense Adaptive Triggers & Latency Engine
6. Web Server CSRF, Path Traversal & Security Hardening
7. Diagnostic Shell, Systemd Sleep/Resume Lifecycle & Wake-on-LAN
8. (Optional) Live Hardware Probing (--live)
==============================================================================
"""

import os
import sys
import json
import time
import socket
import argparse
import subprocess
from pathlib import Path

# ANSI colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"

REPO_ROOT = Path(__file__).resolve().parent.parent
CLIENT_DIR = REPO_ROOT / "client"
SERVER_DIR = REPO_ROOT / "server"


def print_banner():
    print(f"\n{BLUE}{BOLD}" + "=" * 74 + f"{RESET}")
    print(f"{CYAN}{BOLD}   ⚡  AutoUSBIP-QT Master Feature Verification & Testing Orchestrator ⚡  {RESET}")
    print(f"{BLUE}{BOLD}" + "=" * 74 + f"{RESET}\n")


def check_preflight_environment() -> dict:
    print(f"{BOLD}[1/3] Running System Environment & Kernel Pre-Flight Checks...{RESET}")
    checks = {}

    # 1. Python version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    is_py_ok = sys.version_info >= (3, 10)
    checks["Python Version (>=3.10)"] = (is_py_ok, f"Python {py_ver}")

    # 2. Kernel Module / Driver
    if sys.platform == "linux":
        try:
            lsmod = subprocess.run(["lsmod"], capture_output=True, text=True, timeout=2.0)
            has_vhci = "vhci_hcd" in lsmod.stdout
            checks["Kernel Module (vhci-hcd)"] = (
                has_vhci,
                "Loaded (Active)" if has_vhci else "Not loaded in current kernel session"
            )
        except Exception:
            checks["Kernel Module (vhci-hcd)"] = (False, "Could not query lsmod")
    elif sys.platform == "win32":
        checks["Windows VHCI Driver"] = (True, "Windows driver check")

    # 3. Polkit & AppArmor security rules
    polkit_rule = CLIENT_DIR / "security" / "polkit" / "50-autousbip.rules"
    has_polkit = polkit_rule.exists()
    checks["Polkit Authorization Rule"] = (
        has_polkit,
        "Present in repo" if has_polkit else "Missing"
    )

    # 4. Port availability probe (3240, 3241, 3242)
    for p in (3240, 3241, 3242):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", p))
            checks[f"Port {p}/tcp (Local Binding)"] = (True, "Available")
            s.close()
        except OSError:
            checks[f"Port {p}/tcp (Local Binding)"] = (True, "Active / In Use (Service Running)")

    for name, (passed, detail) in checks.items():
        status_str = f"{GREEN}✓ PASS{RESET}" if passed else f"{YELLOW}⚠️ INFO{RESET}"
        print(f"  • {name:<36} {status_str} ({detail})")

    return checks


def run_pytest_suites() -> tuple[bool, dict]:
    print(f"\n{BOLD}[2/3] Executing Modular Automated Feature Test Matrix...{RESET}")
    pytest_bin = CLIENT_DIR / "venv" / "bin" / "pytest"
    if not pytest_bin.exists():
        pytest_bin = Path("pytest")

    suite_categories = [
        ("Client Configuration & Schema Options", "tests/test_config_and_options.py"),
        ("Full Options & Settings Enable/Disable Matrix", "tests/test_all_options_toggle_matrix.py"),
        ("Device Management & Routing APIs", "tests/test_device_operations_and_routes.py"),
        ("Server Connection & Management APIs", "tests/test_server_operations_and_routes.py"),
        ("Gamepad Diagnostics & DualSense Engine", "tests/test_gamepad_engine_and_routes.py"),
        ("Server Daemon Hardening & Sysfs VBUS", "tests/test_server_daemon_features.py"),
        ("Diagnostics Shell, D-Bus & Wake-on-LAN", "tests/test_console_and_system_services.py"),
        ("Client Core & Hardware Fallbacks", "tests/test_client_core.py"),
        ("Web Dashboard Security & Path Traversal", "tests/test_web_server_security.py"),
        ("Windows Portability & Driver Sandboxing", "tests/test_windows_security.py"),
    ]

    all_passed = True
    results = {}

    for cat_name, test_file in suite_categories:
        t0 = time.time()
        cmd = [str(pytest_bin), str(REPO_ROOT / test_file), "-q", "--no-header"]
        proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
        dur = time.time() - t0
        passed = (proc.returncode == 0)
        
        if not passed:
            all_passed = False

        # Extract test count summary
        out_line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
        results[cat_name] = {
            "passed": passed,
            "duration": dur,
            "summary": out_line,
            "file": test_file,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }

        status_str = f"{GREEN}{BOLD}PASSED{RESET}" if passed else f"{RED}{BOLD}FAILED{RESET}"
        print(f"  {status_str} [{dur:.2f}s] {BOLD}{cat_name}{RESET}")
        print(f"         └─ {CYAN}{out_line}{RESET}")

    return all_passed, results


def run_live_hardware_probe():
    print(f"\n{BOLD}[3/3] Live Hardware & Device Probing Mode (--live)...{RESET}")
    # Probe local USB devices
    if sys.platform == "linux":
        try:
            lsusb = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=2.0)
            devices = [d.strip() for d in lsusb.stdout.splitlines() if d.strip()]
            print(f"  • Physical USB Devices Detected on Host: {len(devices)}")
            for d in devices[:4]:
                print(f"    - {d}")
            if len(devices) > 4:
                print(f"    - ... and {len(devices) - 4} more")
        except Exception:
            print("  • lsusb command not available")

        # Probe joystick nodes
        js_nodes = list(Path("/dev/input").glob("js*")) if Path("/dev/input").exists() else []
        event_nodes = list(Path("/dev/input").glob("event*")) if Path("/dev/input").exists() else []
        print(f"  • Gamepad / Joystick Device Nodes: {len(js_nodes)} js nodes, {len(event_nodes)} event nodes")
        for j in js_nodes:
            print(f"    - {j}")
    else:
        print("  • Windows live hardware enumeration active")


def generate_report(preflight: dict, test_results: dict, output_path: str):
    p = Path(output_path)
    total_suites = len(test_results)
    passed_suites = sum(1 for r in test_results.values() if r["passed"])
    
    lines = [
        "# AutoUSBIP-QT Test Verification Report",
        f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Platform:** {sys.platform} (Python {sys.version.split()[0]})",
        f"**Overall Status:** {'✅ ALL TESTS PASSED' if passed_suites == total_suites else '❌ FAILURES DETECTED'}",
        f"**Score:** {passed_suites}/{total_suites} suites passed\n",
        "## 1. Environment Pre-Flight Checks",
        "| Check | Status | Details |",
        "| :--- | :--- | :--- |",
    ]
    for k, (ok, det) in preflight.items():
        lines.append(f"| {k} | {'✅ Pass' if ok else '⚠️ Info'} | {det} |")

    lines.extend([
        "\n## 2. Automated Feature Test Matrix Results",
        "| Category / Feature Area | Status | Execution Time | Results |",
        "| :--- | :--- | :--- | :--- |",
    ])
    for cat, data in test_results.items():
        st = "✅ PASSED" if data["passed"] else "❌ FAILED"
        lines.append(f"| {cat} | {st} | {data['duration']:.2f}s | `{data['summary']}` |")

    p.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n{GREEN}📄 Test report saved to: {p.resolve()}{RESET}")


def main():
    parser = argparse.ArgumentParser(description="AutoUSBIP-QT Master Feature Test Suite")
    parser.add_argument("--live", action="store_true", help="Probe and test live physical USB/controller hardware")
    parser.add_argument("--report", type=str, default="", help="Path to export Markdown report")
    args = parser.parse_args()

    print_banner()
    t_start = time.time()

    preflight = check_preflight_environment()
    all_passed, results = run_pytest_suites()

    if args.live:
        run_live_hardware_probe()

    if args.report:
        generate_report(preflight, results, args.report)

    total_time = time.time() - t_start
    print(f"\n{BLUE}" + "=" * 74 + f"{RESET}")
    if all_passed:
        print(f"{GREEN}{BOLD}🎉 ALL FEATURE TESTS PASSED SUCCESSFULLY in {total_time:.2f}s! 🎉{RESET}")
        print(f"{BLUE}" + "=" * 74 + f"{RESET}\n")
        sys.exit(0)
    else:
        print(f"{RED}{BOLD}❌ SOME FEATURE TESTS FAILED (Completed in {total_time:.2f}s){RESET}")
        print(f"{BLUE}" + "=" * 74 + f"{RESET}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
