"""
Unit tests for the Dynamic Runtime Latency Optimizer and Graceful Reversion Engine.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
CLIENT_DIR = REPO_ROOT / "client"
SERVER_DIR = REPO_ROOT / "server"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(CLIENT_DIR))
sys.path.insert(0, str(SERVER_DIR))

from core.latency_optimizer import RuntimeLatencyOptimizer, init_latency_optimizer
from server.latency_optimizer import ServerLatencyOptimizer, init_server_latency_optimizer


def test_client_latency_optimizer_lifecycle(tmp_path):
    """Verify that the client latency optimizer snapshots original state and restores it on cleanup."""
    optimizer = RuntimeLatencyOptimizer(elevated_priority=False)
    
    # Mock sysfs CPU governor files
    gov_file = tmp_path / "scaling_governor"
    gov_file.write_text("powersave")
    
    optimizer._orig_cpu_governors[str(gov_file)] = "powersave"
    gov_file.write_text("performance")
    
    assert gov_file.read_text().strip() == "performance"
    
    # Test restore
    optimizer.restore_all()
    assert gov_file.read_text().strip() == "powersave"


def test_server_latency_optimizer_lifecycle(tmp_path):
    """Verify that the server latency optimizer snapshots and restores sysctl / power settings."""
    optimizer = ServerLatencyOptimizer(elevated_priority=False)
    
    fake_sysctl = tmp_path / "tcp_low_latency"
    fake_sysctl.write_text("0")
    
    optimizer._orig_sysctls[str(fake_sysctl)] = "0"
    fake_sysctl.write_text("1")
    
    assert fake_sysctl.read_text().strip() == "1"
    
    optimizer.restore_all()
    assert fake_sysctl.read_text().strip() == "0"


def test_latency_optimizer_safe_execution():
    """Verify that apply_all runs safely and returns a dictionary of statuses without throwing."""
    optimizer = RuntimeLatencyOptimizer(elevated_priority=False)
    results = optimizer.apply_all()
    assert isinstance(results, dict)
    assert "wifi_powersave" in results
    assert "ethernet_eee" in results
    assert "cpu_governor" in results
    assert "network_sysctl" in results
    assert "usb_autosuspend" in results
    
    # Cleanup
    optimizer.restore_all()
