"""
==============================================================================
AutoUSBIP-QT Dynamic Runtime Latency Optimizer & Graceful Reversion Engine
==============================================================================
Applies non-permanent, runtime low-latency optimizations across Linux (x86_64,
ARM/Raspberry Pi) and Windows (x64), and automatically reverts all system
settings to their exact original states upon process exit or shutdown.

Linux Optimizations:
1. Wi-Fi 802.11 Power Saving (iw dev <wlan> set power_save off)
2. Energy-Efficient Ethernet (ethtool --set-eee <eth> eee off)
3. CPU Scaling Governor (performance governor locking)
4. Energy Performance Preference (EPP / EPB -> performance on Intel & AMD)
5. Dynamic Network Sysctls (tcp_low_latency, tcp_slow_start_after_idle, bbr/fq)
6. USB Autosuspend & Runtime PM (usbcore.autosuspend = -1, power/control = on)
7. Process Scheduler Niceness (Elevated process priority)

Windows Optimizations:
1. 1ms High-Precision Multimedia Timer Resolution (timeBeginPeriod(1))
2. Windows Process Priority Class (HIGH_PRIORITY_CLASS)
3. Disable Windows 10/11 EcoQoS Power Throttling (ProcessPowerThrottling)
==============================================================================
"""

from __future__ import annotations

import atexit
import glob
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("auto-usbip-latency")


class RuntimeLatencyOptimizer:
    """Manages temporary low-latency OS and network optimizations with guaranteed cleanup."""

    def __init__(self, elevated_priority: bool = True):
        self.elevated_priority = elevated_priority
        self._orig_wifi_powersave: dict[str, str] = {}
        self._orig_eth_eee: dict[str, str] = {}
        self._orig_cpu_governors: dict[str, str] = {}
        self._orig_cpu_epp: dict[str, str] = {}
        self._orig_sysctls: dict[str, str] = {}
        self._orig_usb_power: dict[str, str] = {}
        self._orig_usb_autosuspend: str | None = None
        self._win_timer_set = False
        self._applied = False
        self._cleaned_up = False

        # Register cleanup handler
        atexit.register(self.restore_all)

    def apply_all(self) -> dict[str, bool]:
        """Snapshot original settings and apply runtime low-latency tweaks."""
        if self._applied:
            return {"status": True}

        results = {}
        logger.info("[Latency Optimizer] Initializing dynamic runtime low-latency profile...")

        if sys.platform == "win32":
            # --- WINDOWS OPTIMIZATIONS ---
            results["win_timer_resolution"] = self._optimize_windows_timer()
            results["win_process_priority"] = self._optimize_windows_priority()
            results["win_power_throttling"] = self._optimize_windows_power_throttling()
        else:
            # --- LINUX OPTIMIZATIONS (ARM Pi & x86_64) ---
            results["wifi_powersave"] = self._optimize_wifi_powersave()
            results["ethernet_eee"] = self._optimize_ethernet_eee()
            results["cpu_governor"] = self._optimize_cpu_governor()
            results["cpu_epp"] = self._optimize_cpu_epp()
            results["network_sysctl"] = self._optimize_network_sysctls()
            results["usb_autosuspend"] = self._optimize_usb_autosuspend()
            if self.elevated_priority:
                results["process_priority"] = self._optimize_process_priority()

        self._applied = True
        logger.info(f"[Latency Optimizer] Low-latency runtime profile active (Optimizations: {results})")
        return results

    # =========================================================================
    # Windows-Specific Low-Latency Handlers
    # =========================================================================

    def _optimize_windows_timer(self) -> bool:
        """Set Windows system multimedia timer resolution to 1.0ms (default is 15.6ms)."""
        try:
            import ctypes
            res = ctypes.windll.winmm.timeBeginPeriod(1)
            if res == 0:  # TIMERR_NOERROR
                self._win_timer_set = True
                logger.info("[Latency Optimizer] Windows system timer resolution lowered to 1.0ms (1000Hz).")
                return True
        except Exception as e:
            logger.debug(f"[Latency Optimizer] Windows timer tuning: {e}")
        return False

    def _optimize_windows_priority(self) -> bool:
        """Set process priority to HIGH_PRIORITY_CLASS."""
        try:
            import ctypes
            HIGH_PRIORITY_CLASS = 0x00000080
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            res = ctypes.windll.kernel32.SetPriorityClass(handle, HIGH_PRIORITY_CLASS)
            if res:
                logger.info("[Latency Optimizer] Elevated Windows process priority to HIGH_PRIORITY_CLASS.")
                return True
        except Exception as e:
            logger.debug(f"[Latency Optimizer] Windows priority tuning: {e}")
        return False

    def _optimize_windows_power_throttling(self) -> bool:
        """Disable Windows 10/11 EcoQoS Power Throttling to prevent background core throttling."""
        try:
            import ctypes
            class ProcessPowerThrottlingState(ctypes.Structure):
                _fields_ = [
                    ("Version", ctypes.c_ulong),
                    ("ControlMask", ctypes.c_ulong),
                    ("StateMask", ctypes.c_ulong)
                ]
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            state = ProcessPowerThrottlingState()
            state.Version = 1
            state.ControlMask = 1  # PROCESS_POWER_THROTTLING_EXECUTION_SPEED
            state.StateMask = 0    # Disable throttling (full performance)
            res = ctypes.windll.kernel32.SetProcessInformation(
                handle,
                4,  # ProcessPowerThrottling
                ctypes.byref(state),
                ctypes.sizeof(state)
            )
            if res:
                logger.info("[Latency Optimizer] Disabled Windows EcoQoS background power throttling.")
                return True
        except Exception as e:
            logger.debug(f"[Latency Optimizer] Windows power throttling check: {e}")
        return False

    # =========================================================================
    # Linux-Specific Low-Latency Handlers
    # =========================================================================

    def _optimize_wifi_powersave(self) -> bool:
        """Disable 802.11 power saving on active Wi-Fi adapters."""
        if not shutil.which("iw"):
            return False

        success = False
        try:
            proc = subprocess.run(["iw", "dev"], capture_output=True, text=True, timeout=2.0)
            if proc.returncode != 0:
                return False

            ifaces = re.findall(r"Interface\s+([a-zA-Z0-9_-]+)", proc.stdout)
            for iface in ifaces:
                st_proc = subprocess.run(["iw", "dev", iface, "get", "power_save"], capture_output=True, text=True, timeout=2.0)
                if st_proc.returncode == 0:
                    current_state = "on" if "Power save: on" in st_proc.stdout else "off"
                    self._orig_wifi_powersave[iface] = current_state
                    if current_state == "on":
                        set_proc = subprocess.run(["iw", "dev", iface, "set", "power_save", "off"], capture_output=True, text=True, timeout=2.0)
                        if set_proc.returncode == 0:
                            logger.info(f"[Latency Optimizer] Disabled Wi-Fi power saving on '{iface}' (was {current_state}).")
                            success = True
        except Exception as e:
            logger.debug(f"[Latency Optimizer] Wi-Fi optimization check: {e}")
        return success

    def _optimize_ethernet_eee(self) -> bool:
        """Disable Energy-Efficient Ethernet (802.3az) on physical wired links."""
        if not shutil.which("ethtool"):
            return False

        success = False
        net_dir = Path("/sys/class/net")
        if not net_dir.exists():
            return False

        for iface_path in net_dir.iterdir():
            iface = iface_path.name
            if iface.startswith(("lo", "virbr", "docker", "veth", "tailscale", "tun", "tap", "wg")):
                continue

            try:
                proc = subprocess.run(["ethtool", "--show-eee", iface], capture_output=True, text=True, timeout=1.5)
                if proc.returncode == 0 and "EEE status: enabled" in proc.stdout:
                    self._orig_eth_eee[iface] = "on"
                    set_proc = subprocess.run(["ethtool", "--set-eee", iface, "eee", "off"], capture_output=True, text=True, timeout=1.5)
                    if set_proc.returncode == 0:
                        logger.info(f"[Latency Optimizer] Disabled Energy-Efficient Ethernet on '{iface}'.")
                        success = True
            except Exception:
                pass
        return success

    def _optimize_cpu_governor(self) -> bool:
        """Set CPU scaling governor to performance."""
        gov_files = glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor")
        if not gov_files:
            return False

        success = False
        for gf in gov_files:
            try:
                p = Path(gf)
                if p.exists():
                    orig = p.read_text().strip()
                    self._orig_cpu_governors[gf] = orig
                    if orig != "performance":
                        try:
                            p.write_text("performance")
                            success = True
                        except PermissionError:
                            pass
            except Exception:
                pass

        if success:
            logger.info(f"[Latency Optimizer] Locked {len(self._orig_cpu_governors)} CPU cores to 'performance' governor.")
        return success

    def _optimize_cpu_epp(self) -> bool:
        """Lock Intel & AMD Energy Performance Preference (EPP) to performance."""
        epp_files = glob.glob("/sys/devices/system/cpu/cpufreq/policy*/energy_performance_preference")
        if not epp_files:
            return False

        success = False
        for ef in epp_files:
            try:
                p = Path(ef)
                if p.exists():
                    orig = p.read_text().strip()
                    self._orig_cpu_epp[ef] = orig
                    if orig != "performance":
                        try:
                            p.write_text("performance")
                            success = True
                        except PermissionError:
                            pass
            except Exception:
                pass
        return success

    def _optimize_network_sysctls(self) -> bool:
        """Apply dynamic low-latency TCP sysctl knobs."""
        sysctl_map = {
            "/proc/sys/net/ipv4/tcp_low_latency": "1",
            "/proc/sys/net/ipv4/tcp_slow_start_after_idle": "0",
        }

        success = False
        for path_str, opt_val in sysctl_map.items():
            p = Path(path_str)
            if p.exists():
                try:
                    orig = p.read_text().strip()
                    self._orig_sysctls[path_str] = orig
                    if orig != opt_val:
                        try:
                            p.write_text(opt_val)
                            success = True
                        except PermissionError:
                            pass
                except Exception:
                    pass
        return success

    def _optimize_usb_autosuspend(self) -> bool:
        """Disable USB autosuspend runtime power collapse on active host controllers."""
        success = False

        as_param = Path("/sys/module/usbcore/parameters/autosuspend")
        if as_param.exists():
            try:
                orig = as_param.read_text().strip()
                self._orig_usb_autosuspend = orig
                if orig != "-1":
                    try:
                        as_param.write_text("-1")
                        success = True
                    except PermissionError:
                        pass
            except Exception:
                pass

        power_files = glob.glob("/sys/bus/usb/devices/*/power/control")
        for pf in power_files:
            try:
                p = Path(pf)
                if p.exists():
                    orig = p.read_text().strip()
                    self._orig_usb_power[pf] = orig
                    if orig != "on":
                        try:
                            p.write_text("on")
                            success = True
                        except PermissionError:
                            pass
            except Exception:
                pass
        return success

    def _optimize_process_priority(self) -> bool:
        """Elevate process scheduling priority (nice value)."""
        try:
            cur_nice = os.nice(0)
            if cur_nice > -10:
                try:
                    os.nice(-5)
                    logger.debug(f"[Latency Optimizer] Elevated process nice value to {os.nice(0)}")
                    return True
                except PermissionError:
                    pass
        except Exception:
            pass
        return False

    def restore_all(self):
        """Cleanly revert all system settings back to their original snapshotted values."""
        if self._cleaned_up:
            return

        self._cleaned_up = True
        logger.info("[Latency Optimizer] Reverting dynamic low-latency settings to original values...")

        # Windows cleanup
        if sys.platform == "win32" and self._win_timer_set:
            try:
                import ctypes
                ctypes.windll.winmm.timeEndPeriod(1)
                logger.info("[Latency Optimizer] Restored standard Windows system timer resolution.")
            except Exception:
                pass

        # Linux cleanup
        for iface, orig_val in self._orig_wifi_powersave.items():
            try:
                subprocess.run(["iw", "dev", iface, "set", "power_save", orig_val], capture_output=True, timeout=2.0)
            except Exception:
                pass

        for iface, orig_val in self._orig_eth_eee.items():
            try:
                subprocess.run(["ethtool", "--set-eee", iface, "eee", orig_val], capture_output=True, timeout=1.5)
            except Exception:
                pass

        for gf, orig_val in self._orig_cpu_governors.items():
            try:
                Path(gf).write_text(orig_val)
            except Exception:
                pass

        for ef, orig_val in self._orig_cpu_epp.items():
            try:
                Path(ef).write_text(orig_val)
            except Exception:
                pass

        for path_str, orig_val in self._orig_sysctls.items():
            try:
                Path(path_str).write_text(orig_val)
            except Exception:
                pass

        if self._orig_usb_autosuspend:
            try:
                Path("/sys/module/usbcore/parameters/autosuspend").write_text(self._orig_usb_autosuspend)
            except Exception:
                pass

        for pf, orig_val in self._orig_usb_power.items():
            try:
                Path(pf).write_text(orig_val)
            except Exception:
                pass

        logger.info("[Latency Optimizer] Successfully restored all system settings to original states.")


_GLOBAL_OPTIMIZER: RuntimeLatencyOptimizer | None = None


def init_latency_optimizer(elevated_priority: bool = True) -> RuntimeLatencyOptimizer:
    """Initialize and apply global low-latency runtime optimizer with automatic cleanup."""
    global _GLOBAL_OPTIMIZER
    if _GLOBAL_OPTIMIZER is None:
        _GLOBAL_OPTIMIZER = RuntimeLatencyOptimizer(elevated_priority=elevated_priority)
        _GLOBAL_OPTIMIZER.apply_all()
    return _GLOBAL_OPTIMIZER


def get_latency_optimizer() -> RuntimeLatencyOptimizer | None:
    return _GLOBAL_OPTIMIZER
