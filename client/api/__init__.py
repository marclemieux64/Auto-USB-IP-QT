"""REST API Route Handlers for Auto USB/IP Client."""
from .status_routes import (
    handle_status,
    handle_save_options,
    handle_export_client_config,
    handle_import_client_config,
    handle_restart_client,
)
from .server_routes import (
    handle_add_server,
    handle_remove_server,
    handle_toggle_server,
    handle_server_status,
    handle_server_logs,
    handle_save_server_config,
    handle_restart_server_daemon,
    handle_reboot_server_system,
)
from .device_routes import (
    handle_attach,
    handle_detach,
    handle_detach_all,
    handle_toggle_device_audio,
    handle_toggle_touchpad_mouse,
    handle_powercycle_device,
    handle_recover_zombies,
    handle_set_nickname,
    handle_blacklist_device,
    handle_unblacklist_device,
    handle_open_storage,
)
from .gamepad_routes import (
    handle_gamepad_state,
    handle_gamepad_control,
)

__all__ = [
    "handle_status",
    "handle_save_options",
    "handle_export_client_config",
    "handle_import_client_config",
    "handle_restart_client",
    "handle_add_server",
    "handle_remove_server",
    "handle_toggle_server",
    "handle_server_status",
    "handle_server_logs",
    "handle_save_server_config",
    "handle_restart_server_daemon",
    "handle_reboot_server_system",
    "handle_attach",
    "handle_detach",
    "handle_detach_all",
    "handle_toggle_device_audio",
    "handle_toggle_touchpad_mouse",
    "handle_powercycle_device",
    "handle_recover_zombies",
    "handle_set_nickname",
    "handle_blacklist_device",
    "handle_unblacklist_device",
    "handle_open_storage",
    "handle_gamepad_state",
    "handle_gamepad_control",
]

from .console_routes import (
    handle_get_console_logs,
    handle_exec_console_command,
    handle_clear_console_logs,
)

__all__ += [
    "handle_get_console_logs",
    "handle_exec_console_command",
    "handle_clear_console_logs",
]
