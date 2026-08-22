/* Auto USB/IP Client & Server Diagnostic Consoles */

/* =========================================================================
 * 1. CLIENT CONSOLE
 * ========================================================================= */
let clientConsoleLastId = 0;
let clientConsolePollingInterval = null;
let clientConsoleAutoScroll = true;
let clientConsoleActiveLevel = "ALL";
let clientConsoleSearchQuery = "";
let clientConsoleLogs = [];
let clientCommandHistory = [];
let clientHistoryIndex = -1;
let clientConsoleErrorCount = 0;

/* =========================================================================
 * 2. SERVER CONSOLE
 * ========================================================================= */
let activeServerConsoleIp = null;
let activeServerConsoleName = "Remote Server";
let serverConsolePollingInterval = null;
let serverConsoleAutoScroll = true;
let serverConsoleActiveLevel = "ALL";
let serverConsoleSearchQuery = "";
let serverConsoleLogs = [];
let serverCommandHistory = [];
let serverHistoryIndex = -1;

document.addEventListener("DOMContentLoaded", () => {
    initClientConsoleEvents();
    initServerConsoleEvents();
    startClientBackgroundMonitor();
});

/* --- Client Console Handlers --- */
function initClientConsoleEvents() {
    const input = document.getElementById("console-cmd-input");
    if (input) {
        input.addEventListener("keydown", handleClientKeydown);
    }

    const search = document.getElementById("console-search-input");
    if (search) {
        search.addEventListener("input", (e) => {
            clientConsoleSearchQuery = e.target.value.trim().toLowerCase();
            renderClientLogs();
        });
    }

    const logsContainer = document.getElementById("console-logs-container");
    if (logsContainer) {
        logsContainer.addEventListener("scroll", () => {
            const isAtBottom = (logsContainer.scrollHeight - logsContainer.scrollTop - logsContainer.clientHeight) < 30;
            clientConsoleAutoScroll = isAtBottom;
            const autoBtn = document.getElementById("console-autoscroll-btn");
            if (autoBtn) autoBtn.style.opacity = clientConsoleAutoScroll ? "1" : "0.5";
        });
    }
}

function startClientBackgroundMonitor() {
    setInterval(async () => {
        if (!document.getElementById("console-modal") || document.getElementById("console-modal").style.display !== "flex") {
            try {
                const res = await API.getConsoleLogs(clientConsoleLastId, 50);
                if (res && res.status === "ok" && res.logs && res.logs.length > 0) {
                    clientConsoleLastId = res.last_id || clientConsoleLastId;
                    for (const l of res.logs) {
                        clientConsoleLogs.push(l);
                        if (l.level === "ERROR") clientConsoleErrorCount++;
                    }
                    if (clientConsoleLogs.length > 1500) {
                        clientConsoleLogs = clientConsoleLogs.slice(-1500);
                    }
                    updateClientBadge();
                }
            } catch (e) {}
        }
    }, 3000);
}

function updateClientBadge() {
    const badge = document.getElementById("console-badge");
    if (badge) {
        if (clientConsoleErrorCount > 0) {
            badge.textContent = clientConsoleErrorCount > 99 ? "99+" : clientConsoleErrorCount;
            badge.style.display = "inline-block";
        } else {
            badge.style.display = "none";
        }
    }
}

async function openConsoleModal() {
    const modal = document.getElementById("console-modal");
    if (!modal) return;
    modal.style.display = "flex";
    clientConsoleErrorCount = 0;
    updateClientBadge();

    setTimeout(() => {
        const inp = document.getElementById("console-cmd-input");
        if (inp) inp.focus();
    }, 100);

    await refreshClientLogs(true);
    if (clientConsolePollingInterval) clearInterval(clientConsolePollingInterval);
    clientConsolePollingInterval = setInterval(fetchNewClientLogs, 600);
}

function closeConsoleModal() {
    const modal = document.getElementById("console-modal");
    if (modal) modal.style.display = "none";
    if (clientConsolePollingInterval) {
        clearInterval(clientConsolePollingInterval);
        clientConsolePollingInterval = null;
    }
}

async function refreshClientLogs(full = false) {
    try {
        const since = full ? 0 : clientConsoleLastId;
        const res = await API.getConsoleLogs(since, 500);
        if (res && res.status === "ok") {
            clientConsoleLastId = res.last_id || 0;
            if (full) {
                clientConsoleLogs = res.logs || [];
            } else if (res.logs && res.logs.length > 0) {
                clientConsoleLogs.push(...res.logs);
                if (clientConsoleLogs.length > 1500) {
                    clientConsoleLogs = clientConsoleLogs.slice(-1500);
                }
            }
            renderClientLogs();
        }
    } catch (e) {
        console.error("Error fetching client logs:", e);
    }
}

async function fetchNewClientLogs() {
    try {
        const res = await API.getConsoleLogs(clientConsoleLastId, 100);
        if (res && res.status === "ok" && res.logs && res.logs.length > 0) {
            clientConsoleLastId = res.last_id || clientConsoleLastId;
            clientConsoleLogs.push(...res.logs);
            if (clientConsoleLogs.length > 1500) {
                clientConsoleLogs = clientConsoleLogs.slice(-1500);
            }
            renderClientLogs();
        }
    } catch (e) {}
}

function renderClientLogs() {
    const container = document.getElementById("console-logs-container");
    if (!container) return;

    let filtered = clientConsoleLogs;
    if (clientConsoleActiveLevel !== "ALL") {
        filtered = filtered.filter(l => l.level === clientConsoleActiveLevel);
    }
    if (clientConsoleSearchQuery) {
        filtered = filtered.filter(l => 
            l.message.toLowerCase().includes(clientConsoleSearchQuery) ||
            l.name.toLowerCase().includes(clientConsoleSearchQuery)
        );
    }

    if (filtered.length === 0) {
        container.innerHTML = '<div style="color:var(--text-muted); font-style:italic; padding:16px; text-align:center;">No logs match current filter criteria.</div>';
        return;
    }

    container.innerHTML = filtered.map(l => formatLogLine(l)).join("");
    if (clientConsoleAutoScroll) {
        container.scrollTop = container.scrollHeight;
    }
}

function setConsoleLevel(level) {
    clientConsoleActiveLevel = level;
    document.querySelectorAll("[data-level]").forEach(btn => {
        btn.classList.toggle("active", btn.getAttribute("data-level") === level);
    });
    renderClientLogs();
}

function toggleConsoleAutoScroll() {
    clientConsoleAutoScroll = !clientConsoleAutoScroll;
    const autoBtn = document.getElementById("console-autoscroll-btn");
    if (autoBtn) autoBtn.style.opacity = clientConsoleAutoScroll ? "1" : "0.5";
    if (clientConsoleAutoScroll) {
        const container = document.getElementById("console-logs-container");
        if (container) container.scrollTop = container.scrollHeight;
    }
    showToast(clientConsoleAutoScroll ? "Auto-scroll enabled" : "Auto-scroll paused");
}

async function clearConsole() {
    try {
        await API.clearConsoleLogs();
        clientConsoleLogs = [];
        clientConsoleLastId = 0;
        clientConsoleErrorCount = 0;
        updateClientBadge();
        renderClientLogs();
        showToast("Client console cleared.");
    } catch (e) {
        console.error("Error clearing client console:", e);
    }
}

function copyConsoleLogs() {
    if (clientConsoleLogs.length === 0) {
        showToast("No logs to copy.");
        return;
    }
    const text = clientConsoleLogs.map(l => `[${l.timestamp}] [${l.level}] <${l.name}> ${l.message}`).join("\n");
    navigator.clipboard.writeText(text).then(() => showToast("Logs copied to clipboard!")).catch(console.error);
}

function exportConsoleLogs() {
    if (clientConsoleLogs.length === 0) {
        showToast("No logs to export.");
        return;
    }
    const text = clientConsoleLogs.map(l => `[${l.timestamp}] [${l.level}] <${l.name}> ${l.message}`).join("\n");
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `autousbip-client-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.log`;
    a.click();
    URL.revokeObjectURL(url);
    showToast("Downloaded client log file.");
}

async function runClientQuickCommand(cmd) {
    const input = document.getElementById("console-cmd-input");
    if (input) input.value = cmd;
    await executeClientCommand(cmd);
}

async function executeClientCommand(cmd) {
    try {
        const res = await API.execConsoleCommand(cmd, "client");
        const nowTs = getNowTs();

        clientConsoleLogs.push({
            id: ++clientConsoleLastId,
            timestamp: nowTs,
            level: "CMD",
            name: "user",
            message: `> ${cmd}`
        });

        if (res && res.output) {
            clientConsoleLogs.push({
                id: ++clientConsoleLastId,
                timestamp: nowTs,
                level: "INFO",
                name: "output",
                message: res.output
            });
        } else if (res && res.message) {
            clientConsoleLogs.push({
                id: ++clientConsoleLastId,
                timestamp: nowTs,
                level: res.status === "error" ? "ERROR" : "INFO",
                name: "output",
                message: res.message
            });
        }
        renderClientLogs();
    } catch (err) {
        clientConsoleLogs.push({
            id: ++clientConsoleLastId,
            timestamp: getNowTs(),
            level: "ERROR",
            name: "client",
            message: `Execution failed: ${err.message || err}`
        });
        renderClientLogs();
    }
}

function handleConsoleEnterKey() {
    const input = document.getElementById("console-cmd-input");
    if (!input) return;
    const cmd = input.value.trim();
    if (!cmd) return;
    clientCommandHistory.push(cmd);
    clientHistoryIndex = clientCommandHistory.length;
    input.value = "";
    if (cmd.toLowerCase() === "clear" || cmd.toLowerCase() === "cls") {
        clearConsole();
        return;
    }
    executeClientCommand(cmd);
}

function handleClientKeydown(e) {
    const input = document.getElementById("console-cmd-input");
    if (!input) return;
    if (e.key === "Enter") {
        e.preventDefault();
        handleConsoleEnterKey();
    } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (clientCommandHistory.length > 0 && clientHistoryIndex > 0) {
            clientHistoryIndex--;
            input.value = clientCommandHistory[clientHistoryIndex] || "";
        }
    } else if (e.key === "ArrowDown") {
        e.preventDefault();
        if (clientHistoryIndex < clientCommandHistory.length - 1) {
            clientHistoryIndex++;
            input.value = clientCommandHistory[clientHistoryIndex] || "";
        } else {
            clientHistoryIndex = clientCommandHistory.length;
            input.value = "";
        }
    }
}


/* =========================================================================
 * 2. SERVER CONSOLE (OPENED FROM SERVER CARD CONSOLE BUTTON)
 * ========================================================================= */

function initServerConsoleEvents() {
    const input = document.getElementById("srv-console-cmd-input");
    if (input) {
        input.addEventListener("keydown", handleServerKeydown);
    }

    const search = document.getElementById("srv-console-search-input");
    if (search) {
        search.addEventListener("input", (e) => {
            serverConsoleSearchQuery = e.target.value.trim().toLowerCase();
            renderServerLogs();
        });
    }

    const logsContainer = document.getElementById("srv-console-logs-container");
    if (logsContainer) {
        logsContainer.addEventListener("scroll", () => {
            const isAtBottom = (logsContainer.scrollHeight - logsContainer.scrollTop - logsContainer.clientHeight) < 30;
            serverConsoleAutoScroll = isAtBottom;
            const autoBtn = document.getElementById("srv-console-autoscroll-btn");
            if (autoBtn) autoBtn.style.opacity = serverConsoleAutoScroll ? "1" : "0.5";
        });
    }
}

async function openServerLogsModal(ip, nameEnc) {
    activeServerConsoleIp = ip;
    activeServerConsoleName = decodeURIComponent(nameEnc || ip);

    const titleEl = document.getElementById("modal-logs-title");
    if (titleEl) {
        titleEl.textContent = `Server Console — ${activeServerConsoleName}`;
    }

    const promptEl = document.getElementById("srv-console-prompt");
    if (promptEl) {
        promptEl.textContent = `${activeServerConsoleName} >`;
    }

    const modal = document.getElementById("server-logs-modal");
    if (modal) modal.style.display = "flex";

    setTimeout(() => {
        const inp = document.getElementById("srv-console-cmd-input");
        if (inp) inp.focus();
    }, 100);

    // Update server status pill
    updateServerStatusPill();

    // Fetch initial logs
    await fetchServerConsoleLogs();

    if (serverConsolePollingInterval) clearInterval(serverConsolePollingInterval);
    serverConsolePollingInterval = setInterval(fetchServerConsoleLogs, 2500);
}

function closeServerLogsModal() {
    const modal = document.getElementById("server-logs-modal");
    if (modal) modal.style.display = "none";
    if (serverConsolePollingInterval) {
        clearInterval(serverConsolePollingInterval);
        serverConsolePollingInterval = null;
    }
    activeServerConsoleIp = null;
}

async function updateServerStatusPill() {
    if (!activeServerConsoleIp) return;
    const pill = document.getElementById("srv-console-status-pill");
    if (!pill) return;
    try {
        const data = await API.getServerStatus(activeServerConsoleIp);
        if (data && data.status === "ok") {
            pill.textContent = "Online";
            pill.style.color = "#34d399";
            pill.style.background = "rgba(52, 211, 153, 0.1)";
            pill.style.borderColor = "#059669";
        }
    } catch (e) {
        pill.textContent = "Offline / Unreachable";
        pill.style.color = "#f87171";
        pill.style.background = "rgba(248, 113, 113, 0.1)";
        pill.style.borderColor = "#dc2626";
    }
}

async function fetchServerConsoleLogs() {
    if (!activeServerConsoleIp) return;
    try {
        const data = await API.getServerLogs(activeServerConsoleIp, 100);
        if (data && data.status === "ok" && data.logs) {
            serverConsoleLogs = data.logs.map(line => {
                let lvl = "INFO";
                if (line.includes("ERROR") || line.includes("FAILED") || line.includes("Traceback")) lvl = "ERROR";
                else if (line.includes("WARNING") || line.includes("WARN")) lvl = "WARNING";
                else if (line.includes("DEBUG")) lvl = "DEBUG";

                const match = line.match(/^([A-Za-z]{3}\s+[0-9]+\s+[0-9:]+)\s+([^\s]+)\s+([^:]+):\s+(.*)$/);
                if (match) {
                    return {
                        timestamp: match[1],
                        level: lvl,
                        name: match[3],
                        message: match[4]
                    };
                }
                return {
                    timestamp: new Date().toTimeString().split(" ")[0],
                    level: lvl,
                    name: activeServerConsoleIp,
                    message: line
                };
            });
            renderServerLogs();
        }
    } catch (e) {}
}

function renderServerLogs() {
    const container = document.getElementById("srv-console-logs-container");
    if (!container) return;

    let filtered = serverConsoleLogs;
    if (serverConsoleActiveLevel !== "ALL") {
        filtered = filtered.filter(l => l.level === serverConsoleActiveLevel);
    }
    if (serverConsoleSearchQuery) {
        filtered = filtered.filter(l => 
            l.message.toLowerCase().includes(serverConsoleSearchQuery) ||
            l.name.toLowerCase().includes(serverConsoleSearchQuery)
        );
    }

    if (filtered.length === 0) {
        container.innerHTML = '<div style="color:var(--text-muted); font-style:italic; padding:16px; text-align:center;">No logs match current filter criteria.</div>';
        return;
    }

    container.innerHTML = filtered.map(l => formatLogLine(l)).join("");
    if (serverConsoleAutoScroll) {
        container.scrollTop = container.scrollHeight;
    }
}

function setServerConsoleLevel(level) {
    serverConsoleActiveLevel = level;
    document.querySelectorAll("[data-srv-level]").forEach(btn => {
        btn.classList.toggle("active", btn.getAttribute("data-srv-level") === level);
    });
    renderServerLogs();
}

function toggleServerConsoleAutoScroll() {
    serverConsoleAutoScroll = !serverConsoleAutoScroll;
    const autoBtn = document.getElementById("srv-console-autoscroll-btn");
    if (autoBtn) autoBtn.style.opacity = serverConsoleAutoScroll ? "1" : "0.5";
    if (serverConsoleAutoScroll) {
        const container = document.getElementById("srv-console-logs-container");
        if (container) container.scrollTop = container.scrollHeight;
    }
    showToast(serverConsoleAutoScroll ? "Auto-scroll enabled" : "Auto-scroll paused");
}

function clearServerConsole() {
    serverConsoleLogs = [];
    renderServerLogs();
    showToast("Server log view cleared.");
}

function copyServerConsoleLogs() {
    if (serverConsoleLogs.length === 0) {
        showToast("No logs to copy.");
        return;
    }
    const text = serverConsoleLogs.map(l => `[${l.timestamp}] [${l.level}] <${l.name}> ${l.message}`).join("\n");
    navigator.clipboard.writeText(text).then(() => showToast("Server logs copied to clipboard!")).catch(console.error);
}

function exportServerConsoleLogs() {
    if (serverConsoleLogs.length === 0) {
        showToast("No logs to export.");
        return;
    }
    const text = serverConsoleLogs.map(l => `[${l.timestamp}] [${l.level}] <${l.name}> ${l.message}`).join("\n");
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `autousbip-server-${activeServerConsoleIp}-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.log`;
    a.click();
    URL.revokeObjectURL(url);
    showToast("Downloaded server log file.");
}

async function runServerQuickCommand(cmd) {
    const input = document.getElementById("srv-console-cmd-input");
    if (input) input.value = cmd;
    await executeServerCommand(cmd);
}

async function executeServerCommand(cmd) {
    if (!activeServerConsoleIp) return;
    try {
        const res = await API.execConsoleCommand(cmd, `server:${activeServerConsoleIp}`);
        const nowTs = getNowTs();

        serverConsoleLogs.push({
            timestamp: nowTs,
            level: "CMD",
            name: activeServerConsoleIp,
            message: `> ${cmd}`
        });

        if (res && res.output) {
            serverConsoleLogs.push({
                timestamp: nowTs,
                level: "INFO",
                name: "server",
                message: res.output
            });
        } else if (res && res.message) {
            serverConsoleLogs.push({
                timestamp: nowTs,
                level: res.status === "error" ? "ERROR" : "INFO",
                name: "server",
                message: res.message
            });
        }
        renderServerLogs();
    } catch (err) {
        serverConsoleLogs.push({
            timestamp: getNowTs(),
            level: "ERROR",
            name: activeServerConsoleIp,
            message: `Command execution failed: ${err.message || err}`
        });
        renderServerLogs();
    }
}

function handleServerConsoleEnterKey() {
    const input = document.getElementById("srv-console-cmd-input");
    if (!input) return;
    const cmd = input.value.trim();
    if (!cmd) return;
    serverCommandHistory.push(cmd);
    serverHistoryIndex = serverCommandHistory.length;
    input.value = "";
    if (cmd.toLowerCase() === "clear" || cmd.toLowerCase() === "cls") {
        clearServerConsole();
        return;
    }
    executeServerCommand(cmd);
}

function handleServerKeydown(e) {
    const input = document.getElementById("srv-console-cmd-input");
    if (!input) return;
    if (e.key === "Enter") {
        e.preventDefault();
        handleServerConsoleEnterKey();
    } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (serverCommandHistory.length > 0 && serverHistoryIndex > 0) {
            serverHistoryIndex--;
            input.value = serverCommandHistory[serverHistoryIndex] || "";
        }
    } else if (e.key === "ArrowDown") {
        e.preventDefault();
        if (serverHistoryIndex < serverCommandHistory.length - 1) {
            serverHistoryIndex++;
            input.value = serverCommandHistory[serverHistoryIndex] || "";
        } else {
            serverHistoryIndex = serverCommandHistory.length;
            input.value = "";
        }
    }
}


/* =========================================================================
 * 3. SHARED HELPERS
 * ========================================================================= */

function formatLogLine(l) {
    let lvlClass = "log-info";
    let lvlBadge = l.level || "INFO";
    if (lvlBadge === "WARNING" || lvlBadge === "WARN") {
        lvlClass = "log-warn";
        lvlBadge = "WARN";
    } else if (lvlBadge === "ERROR" || lvlBadge === "CRITICAL") {
        lvlClass = "log-error";
        lvlBadge = "ERR ";
    } else if (lvlBadge === "DEBUG") {
        lvlClass = "log-debug";
        lvlBadge = "DBUG";
    } else if (lvlBadge === "CMD") {
        lvlClass = "log-cmd";
        lvlBadge = "CMD ";
    }

    const safeMsg = escapeHtml(l.message);
    return `
        <div class="console-line ${lvlClass}">
            <span class="console-ts">${l.timestamp}</span>
            <span class="console-lvl">[${lvlBadge}]</span>
            <span class="console-src">&lt;${l.name}&gt;</span>
            <span class="console-msg">${safeMsg}</span>
        </div>
    `;
}

function getNowTs() {
    const d = new Date();
    return d.toTimeString().split(" ")[0] + "." + String(d.getMilliseconds()).padStart(3, "0");
}

function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
