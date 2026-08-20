// Centralized API Client
const API = {
    async getStatus() {
        const res = await fetch("/api/status");
        return await res.json();
    },

    async addServer(payload) {
        const res = await fetch("/api/add_server", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        return await res.json();
    },

    async removeServer(ip, port) {
        const res = await fetch(`/api/remove_server?ip=${encodeURIComponent(ip)}&port=${port}`);
        return await res.json();
    },

    async toggleServer(ip) {
        const res = await fetch(`/api/toggle_server?ip=${encodeURIComponent(ip)}`);
        return await res.json();
    },

    async attachDevice(ip, busid) {
        const res = await fetch(`/api/attach?ip=${encodeURIComponent(ip)}&busid=${encodeURIComponent(busid)}`);
        return await res.json();
    },

    async detachDevice(port) {
        const res = await fetch(`/api/detach?port=${encodeURIComponent(port)}`);
        return await res.json();
    },

    async detachAll() {
        const res = await fetch("/api/detach_all");
        return await res.json();
    },

    async powerCycle(ip, busid) {
        const res = await fetch(`/api/powercycle_device?ip=${encodeURIComponent(ip)}&busid=${encodeURIComponent(busid)}`);
        return await res.json();
    },

    async recoverZombies() {
        const res = await fetch("/api/recover_zombies");
        return await res.json();
    },

    async toggleAudio(port) {
        const res = await fetch("/api/toggle_device_audio", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ port })
        });
        return await res.json();
    },

    async toggleTouchpadMouse(port, enabled) {
        const res = await fetch("/api/toggle_touchpad_mouse", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ port, enabled })
        });
        return await res.json();
    },

    async openStorage(port) {
        const res = await fetch(`/api/open_storage?port=${encodeURIComponent(port)}`);
        return await res.json();
    },

    async setNickname(key, nickname) {
        const res = await fetch("/api/set_nickname", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ key, nickname })
        });
        return await res.json();
    },

    async blacklistDevice(payload) {
        const body = typeof payload === "string" ? { identifier: payload } : payload;
        const res = await fetch("/api/blacklist_device", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
        });
        return await res.json();
    },

    async unblacklistDevice(payload) {
        const body = typeof payload === "string" ? { identifier: payload } : payload;
        const res = await fetch("/api/unblacklist_device", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
        });
        return await res.json();
    },

    async saveOptions(options) {
        const res = await fetch("/api/save_options", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(options)
        });
        return await res.json();
    },

    async getServerStatus(ip) {
        const res = await fetch(`/api/server_status?ip=${encodeURIComponent(ip)}`);
        return await res.json();
    },

    async getServerLogs(ip, lines = 80) {
        const res = await fetch(`/api/server_logs?ip=${encodeURIComponent(ip)}&lines=${lines}`);
        return await res.json();
    },

    async saveServerConfig(ip, config, token = "") {
        const res = await fetch("/api/save_server_config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ip, config, token })
        });
        return await res.json();
    },

    async restartServerDaemon(ip) {
        const res = await fetch(`/api/restart_server_daemon?ip=${encodeURIComponent(ip)}`);
        return await res.json();
    },

    async rebootServerSystem(ip) {
        const res = await fetch(`/api/reboot_server_system?ip=${encodeURIComponent(ip)}`);
        return await res.json();
    },

    async restartClient() {
        const res = await fetch("/api/restart_client");
        return await res.json();
    },

    async getGamepadState(port) {
        const res = await fetch(`/api/gamepad_state?port=${encodeURIComponent(port)}`);
        return await res.json();
    },

    async sendGamepadControl(params) {
        const q = new URLSearchParams(params).toString();
        const res = await fetch(`/api/gamepad_control?${q}`);
        return await res.json();
    },

    async getConsoleLogs(sinceId = 0, limit = 250, level = null, search = null) {
        const params = new URLSearchParams({ since_id: sinceId, limit: limit });
        if (level) params.set("level", level);
        if (search) params.set("search", search);
        const res = await fetch(`/api/console_logs?${params.toString()}`);
        return await res.json();
    },

    async execConsoleCommand(command, target = "client") {
        const res = await fetch("/api/console_exec", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ command: command, target: target })
        });
        return await res.json();
    },

    async clearConsoleLogs() {
        const res = await fetch("/api/console_clear", { method: "POST" });
        return await res.json();
    }
};
