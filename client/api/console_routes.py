from __future__ import annotations

import logging
from typing import Any
from core.console import get_console_logs, clear_console_logs, execute_console_command, log_console_event

logger = logging.getLogger("auto-usbip-client")


def handle_get_console_logs(since_id: int = 0, limit: int = 250, level: str | None = None, search: str | None = None) -> dict[str, Any]:
    logs, last_id = get_console_logs(since_id=since_id, limit=limit, level=level, search=search)
    return {
        "status": "ok",
        "logs": logs,
        "last_id": last_id,
    }


def handle_exec_console_command(controller: Any, command: str, target_mode: str = "client") -> dict[str, Any]:
    cmd_str = (command or "").strip()
    if not cmd_str:
        return {"status": "error", "message": "Empty command"}
    try:
        output = execute_console_command(cmd_str, controller, target_mode=target_mode)
        return {
            "status": "ok",
            "command": cmd_str,
            "output": output,
        }
    except Exception as e:
        logger.error(f"Console command error on '{cmd_str}': {e}", exc_info=True)
        return {
            "status": "error",
            "command": cmd_str,
            "message": f"Execution error: {e}",
        }


def handle_clear_console_logs() -> dict[str, Any]:
    clear_console_logs()
    log_console_event("INFO", "system", "Console log buffer cleared by user.")
    return {"status": "ok", "message": "Console logs cleared"}
