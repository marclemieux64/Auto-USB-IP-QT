let currentStatus = {
    servers: [],
    attached_devices: [],
    available_devices: [],
    discovered_servers: [],
    blacklisted_devices: [],
    config: {}
};

const pendingDetachedPorts = {};
const pendingAttachDevices = {};
const pendingRemovedServers = {};

let editingNicknameKey = null;
let activeServerSettingsIp = null;
let serverStatusCache = {};
try {
    serverStatusCache = JSON.parse(localStorage.getItem("autousbip_server_status_cache") || "{}");
} catch (e) {
    serverStatusCache = {};
}

function saveServerStatusCache() {
    try {
        localStorage.setItem("autousbip_server_status_cache", JSON.stringify(serverStatusCache));
    } catch (e) {}
}
const pendingRestartServers = {}; // ip -> { text: 'Restarting...', timestamp: number, timeout: number }
let serverLogInterval = null;

function showToast(msg) {
    let t = document.getElementById("ui-toast");
    if (!t) {
        t = document.createElement("div");
        t.id = "ui-toast";
        t.style.position = "fixed";
        t.style.bottom = "24px";
        t.style.left = "50%";
        t.style.transform = "translateX(-50%)";
        t.style.backgroundColor = "rgba(17, 24, 39, 0.92)";
        t.style.backdropFilter = "blur(8px)";
        t.style.color = "#f8fafc";
        t.style.padding = "8px 18px";
        t.style.borderRadius = "20px";
        t.style.border = "1px solid rgba(168, 85, 247, 0.4)";
        t.style.boxShadow = "0 4px 20px rgba(0,0,0,0.5), 0 0 15px rgba(168,85,247,0.3)";
        t.style.fontSize = "0.82rem";
        t.style.fontWeight = "600";
        t.style.zIndex = "999999";
        t.style.transition = "opacity 0.3s ease, transform 0.3s ease";
        t.style.pointerEvents = "none";
        document.body.appendChild(t);
    }
    t.textContent = msg;
    t.style.opacity = "1";
    t.style.transform = "translateX(-50%) translateY(0)";
    clearTimeout(t._timeout);
    t._timeout = setTimeout(() => {
        t.style.opacity = "0";
        t.style.transform = "translateX(-50%) translateY(10px)";
    }, 3000);
}

function triggerSyncFlash() {
    const dot = document.getElementById("sync-dot");
    if (dot) {
        dot.classList.add("flash");
        setTimeout(() => dot.classList.remove("flash"), 220);
    }
}

async function fetchStatus() {
    try {
        const data = await API.getStatus();
        if (data.status === "error") return;

        const now = Date.now();
        // Reconcile pending detach operations to prevent backend unbind lag flicker
        for (const [port, item] of Object.entries(pendingDetachedPorts)) {
            if (now - item.timestamp > 3500) {
                delete pendingDetachedPorts[port];
            } else {
                if (data.attached_devices) {
                    data.attached_devices = data.attached_devices.filter(d => String(d.port) !== String(port));
                }
                if (data.available_devices && item.dev && item.dev.server_ip && item.dev.bus_id) {
                    const exists = data.available_devices.some(d => d.server_ip === item.dev.server_ip && d.bus_id === item.dev.bus_id);
                    if (!exists) {
                        data.available_devices.push(item.dev);
                    }
                }
            }
        }

        // Reconcile pending removed servers
        for (const [ip, ts] of Object.entries(pendingRemovedServers)) {
            if (now - ts > 6000) {
                delete pendingRemovedServers[ip];
            } else {
                if (data.servers) {
                    data.servers = data.servers.filter(s => s.ip !== ip);
                }
                if (data.available_devices) {
                    data.available_devices = data.available_devices.filter(d => d.server_ip !== ip);
                }
            }
        }

        // Reconcile pending attach operations
        for (const [key, item] of Object.entries(pendingAttachDevices)) {
            if (now - item.timestamp > 3500) {
                delete pendingAttachDevices[key];
            } else {
                if (data.available_devices) {
                    data.available_devices = data.available_devices.filter(d => `${d.server_ip}:${d.bus_id}` !== key);
                }
            }
        }

        currentStatus = data;
        triggerSyncFlash();
        renderAll();
        if (data.servers) {
            prefetchServerSettings(data.servers);
        }
    } catch (e) {
        console.error("fetchStatus error:", e);
    }
}

function renderAll() {
    renderServers();
    renderAttachedDevices();
    renderAvailableDevices();
    renderDiscoveredServers();
    renderBlacklistedDevices();
    checkGlobalEmpty();
}

function renderServers() {
    const sec = document.getElementById("servers-section");
    const c = document.getElementById("servers-list");
    const srvs = currentStatus.servers || [];
    if (srvs.length === 0) {
        if (sec) sec.style.display = "none";
        return;
    }
    if (sec) sec.style.display = "block";
    const cfg = currentStatus.config || {};
    const now = Date.now();
    c.innerHTML = srvs.map(s => {
        const title = s.name ? `${s.name} (${s.ip})` : s.ip;
        let badges = [];
        const restartInfo = pendingRestartServers[s.ip];
        if (restartInfo) {
            if ((now - restartInfo.timestamp > 3500) && s.is_alive) {
                delete pendingRestartServers[s.ip];
                badges.push('<span class="badge badge-online">Online</span>');
            } else if (now - restartInfo.timestamp > (restartInfo.timeout || 15000)) {
                delete pendingRestartServers[s.ip];
                if (s.is_alive) {
                    badges.push('<span class="badge badge-online">Online</span>');
                } else {
                    badges.push('<span class="badge badge-offline">Offline</span>');
                }
            } else {
                badges.push(`<span class="badge badge-restarting"><span class="spinner-inline"></span> ${restartInfo.text}</span>`);
            }
        } else if (s.enabled) {
            if (s.is_alive) {
                badges.push('<span class="badge badge-online">Online</span>');
                if (s.tls !== false) {
                    badges.push('<span class="badge badge-tls" title="Control socket is encrypted with TLS 1.3 / 1.2"><img src="/icons/badge-tls.png" style="width:12px;height:12px;object-fit:contain;vertical-align:-1px;margin-right:3px;">TLS</span>');
                }
                if (cfg.show_latency && s.latency_ms != null) {
                    badges.push(`<span class="badge badge-latency"><img src="/icons/badge-latency.png"> ${s.latency_ms} ms</span>`);
                }
            } else {
                badges.push('<span class="badge badge-offline">Offline</span>');
            }
        } else {
            badges.push('<span class="badge">Disabled</span>');
        }
        return `
            <div class="card">
                <div class="card-main">
                    <div class="card-left">
                        <div class="card-icon"><img src="/icons/server-card.png"></div>
                        <div class="card-info">
                            <div class="card-title">${title}</div>
                            <div class="card-sub">${badges.join(" ")}</div>
                        </div>
                    </div>
                    <div class="card-actions">
                        <button class="btn" onclick="toggleServer('${encodeURIComponent(s.ip)}')"><img src="${s.enabled ? '/icons/network-disconnect.png' : '/icons/network-connect.png'}"> ${s.enabled ? 'Disable' : 'Enable'}</button>
                        <button class="btn" onclick="openServerLogsModal('${encodeURIComponent(s.ip)}', '${encodeURIComponent(s.name || s.ip)}')"><img src="/icons/utilities-terminal.png"> Console</button>
                        <button class="btn" onclick="openServerSettingsModal('${encodeURIComponent(s.ip)}', '${encodeURIComponent(s.name || s.ip)}')"><img src="/icons/settings.png"> Settings</button>
                        <button class="btn btn-danger" onclick="removeServer('${encodeURIComponent(s.ip)}', ${s.port})"><img src="/icons/detach-btn.png"> Remove</button>
                    </div>
                </div>
            </div>
        `;
    }).join("");
}

function getKenneyControllerHero(family, cleanName, controllerType, desc) {
    const text = [family, cleanName, controllerType, desc].filter(Boolean).join(" ").toLowerCase();

    // 1. PlayStation Series
    if (text.includes("dualsense") || text.includes("054c:0ce6") || text.includes("054c:0df2") || text.includes("ps5") || text.includes("playstation 5")) {
        return "/assets/kenney_input/PlayStation%20Series/Vector/controller_playstation5.svg";
    }
    if (text.includes("dualshock 4") || text.includes("054c:05c4") || text.includes("054c:09cc") || text.includes("ps4") || text.includes("playstation 4")) {
        return "/assets/kenney_input/PlayStation%20Series/Vector/controller_playstation4.svg";
    }
    if (text.includes("dualshock 3") || text.includes("ps3") || text.includes("sixaxis") || text.includes("playstation 3")) {
        return "/assets/kenney_input/PlayStation%20Series/Vector/controller_playstation3.svg";
    }
    if (text.includes("playstation") || text.includes("sony") || text.includes("054c:")) {
        return "/assets/kenney_input/PlayStation%20Series/Vector/controller_playstation5.svg";
    }

    // 2. Xbox Series / One / 360
    if (text.includes("series") || text.includes("045e:0b12") || text.includes("rematch") || text.includes("0e6f:034a") || text.includes("series x") || text.includes("series s")) {
        return "/assets/kenney_input/Xbox%20Series/Vector/controller_xboxseries.svg";
    }
    if (text.includes("xbox 360") || text.includes("045e:028e")) {
        return "/assets/kenney_input/Xbox%20Series/Vector/controller_xbox360.svg";
    }
    if (text.includes("xbox") || text.includes("x-box") || text.includes("045e:") || text.includes("xpad")) {
        return "/assets/kenney_input/Xbox%20Series/Vector/controller_xboxone.svg";
    }

    // 3. Nintendo Family (Wii Classic, Wii Classic Pro, Switch, GameCube, Wiimote)
    if (text.includes("wiimote") || text.includes("wii remote")) {
        return "/assets/kenney_input/Nintendo%20Wii/Vector/wii_controller_vertical.svg";
    }
    if (text.includes("switch pro") || text.includes("057e:2009")) {
        return "/assets/kenney_input/Nintendo%20Switch/Vector/controller_switch_pro.svg";
    }
    if (text.includes("joycon") || text.includes("switch") || text.includes("057e:")) {
        return "/assets/kenney_input/Nintendo%20Switch/Vector/controller_switch.svg";
    }
    if (text.includes("gamecube") || text.includes("057e:0337")) {
        return "/assets/kenney_input/Nintendo%20Gamecube/Vector/gamecube_controller.svg";
    }
    if (text.includes("wii u") || text.includes("wiiu")) {
        return "/assets/kenney_input/Nintendo%20WiiU/Vector/controller_wiiu_pro.svg";
    }
    if (text.includes("classic pro") || text.includes("wii classic pro")) {
        return "/assets/kenney_input/Nintendo%20Wii/Vector/controller_wii_classic_pro.svg";
    }
    if (text.includes("nes") || text.includes("snes") || text.includes("gembird") || text.includes("12bd:d015") || text.includes("retro") || text.includes("2axes") || text.includes("clone") || text.includes("classic") || text.includes("nintendo") || text.includes("wii")) {
        return "/assets/kenney_input/Nintendo%20Wii/Vector/controller_wii_classic.svg";
    }

    // 4. Steam Deck / Steam Controller
    if (text.includes("steam deck") || text.includes("steamdeck") || text.includes("jupiter") || text.includes("galileo")) {
        return "/assets/kenney_input/Steam%20Deck/Vector/controller_steamdeck.svg";
    }
    if (text.includes("steam controller") || text.includes("valve") || text.includes("28de:")) {
        return "/assets/kenney_input/Steam%20Controller/Vector/controller_steam_new.svg";
    }

    // 5. Generic Gamepad Fallback
    return "/assets/kenney_input/Flairs/Vector/controller_generic.svg";
}
window.getKenneyControllerHero = getKenneyControllerHero;

function getDeviceIllustrationUrl(d) {
    if (!d) return "/icons/generic-usb.png";
    if (d.is_storage) return "/icons/storage.png";
    if (d.has_audio && !d.is_controller) return "/icons/audio-card.png";
    if (d.is_controller) return "/icons/gamepad.png";
    if (d.icon_alias) return `/icons/${d.icon_alias}.png`;
    return "/icons/generic-usb.png";
}

function renderAttachedDevices() {
    const sec = document.getElementById("attached-section");
    const c = document.getElementById("devices-list");
    const devs = currentStatus.attached_devices || [];
    if (devs.length === 0) {
        if (sec) sec.style.display = "none";
        return;
    }
    if (sec) sec.style.display = "block";
    const cfg = currentStatus.config || {};
    c.innerHTML = devs.map(d => {
        const iconSrc = getDeviceIllustrationUrl(d);
        const iconName = d.is_controller ? "gamepad" : (d.icon_alias || "generic-usb");
        let title = (cfg.enable_nicknames && d.clean_name) ? d.clean_name : d.desc;
        let badges = [];
        if (cfg.show_port && d.port) badges.push(`<span class="badge badge-port"><img src="/icons/badge-port.png"> Port ${d.port}</span>`);
        if (cfg.show_speed && d.speed) badges.push(`<span class="badge badge-speed"><img src="/icons/badge-speed.png"> ${d.speed}</span>`);
        if (cfg.show_vid_pid && d.vid_pid) badges.push(`<span class="badge badge-vidpid"><img src="/icons/badge-vidpid.png"> ${d.vid_pid}</span>`);
        if (cfg.show_battery && d.battery) badges.push(`<span class="badge badge-battery"><img src="/icons/badge-battery.png"> ${d.battery}</span>`);
        if (cfg.show_latency !== false && (d.latency_str || d.latency_ms != null)) {
            const latText = d.latency_str || `${d.latency_ms} ms`;
            badges.push(`<span class="badge badge-latency" title="Real-time controller polling interval and frequency"><img src="/icons/badge-latency.png"> ${latText}</span>`);
        }

        const btnTester = d.is_controller ? `<button class="btn btn-warning" onclick="openGamepadTesterModal('${d.port}', '${encodeURIComponent(title)}')"><img src="/icons/gamepad.png"> Gamepad Tester</button>` : "";
        const btnStorage = d.is_storage ? `<button class="btn btn-primary" onclick="openStorageDevice('${d.port}')"><img src="/icons/document-open.png"> Open Files</button>` : "";
        const isAudioActive = (d.audio_enabled !== false);
        const btnAudio = d.has_audio ? `<button class="btn ${isAudioActive ? 'btn-secondary' : 'btn-success'}" onclick="toggleDeviceAudio('${d.port}', ${isAudioActive})"><img src="/icons/${isAudioActive ? 'audio-card' : 'audio-volume-muted'}.png"> Audio: ${isAudioActive ? 'On' : 'Off'}</button>` : "";
        const isMouseActive = (d.touchpad_mouse_enabled !== false);
        const btnTouchpad = d.has_touchpad ? `<button class="btn ${isMouseActive ? 'btn-secondary' : 'btn-success'}" onclick="toggleTouchpadMouse('${d.port}', ${!isMouseActive})" title="Toggle whether PlayStation trackpad moves the desktop mouse cursor or stays isolated for gaming"><img src="/icons/input-mouse.png" style="width:13px;height:13px;object-fit:contain;vertical-align:middle;margin-right:3px;"> Trackpad Mouse: ${isMouseActive ? 'On' : 'Off'}</button>` : "";

        return `
            <div class="card">
                <div class="card-main">
                    <div class="card-left">
                        <div class="card-icon"><img src="${iconSrc}"></div>
                        <div class="card-info">
                            <div class="card-title">${title}</div>
                            <div class="card-sub">${badges.join(" ")}</div>
                        </div>
                    </div>
                    <div class="card-actions">
                        <button class="btn btn-danger" onclick="detachSingleDevice('${d.port}')"><img src="/icons/detach-btn.png"> Detach</button>
                        ${d.server_ip && d.bus_id ? `<button class="btn" onclick="powerCycleDevice('${d.server_ip}', '${d.bus_id}')" title="Power cycle / reboot USB port on remote server"><img src="/icons/power-cycle.png"> Power Cycle</button>` : ''}
                        <button class="btn" onclick="openNicknameModal('${d.identifier_key || d.port}', '${encodeURIComponent(title)}')"><img src="/icons/rename.png"> Rename</button>
                        ${btnAudio}
                        ${btnTouchpad}
                        ${btnStorage}
                        ${btnTester}
                        <button class="btn btn-blacklist" onclick="blacklistDevice('${d.port}', '${d.identifier_key || d.vid_pid || d.bus_id || d.port}', '${encodeURIComponent(title)}', '${d.vid_pid || ""}', '${d.bus_id || ""}', '${iconName}', ${d.is_controller ? "true" : "false"})"><img src="/icons/blacklist.png"> Blacklist</button>
                    </div>
                </div>
            </div>
        `;
    }).join("");
}

function renderAvailableDevices() {
    const sec = document.getElementById("available-section");
    const c = document.getElementById("available-list");
    const devs = currentStatus.available_devices || [];
    if (devs.length === 0) {
        if (sec) sec.style.display = "none";
        return;
    }
    if (sec) sec.style.display = "block";
    const cfg = currentStatus.config || {};
    c.innerHTML = devs.map(d => {
        const iconSrc = getDeviceIllustrationUrl(d);
        const iconName = d.is_controller ? "gamepad" : (d.icon_alias || "generic-usb");
        let title = (cfg.enable_nicknames && d.clean_name) ? d.clean_name : d.desc;
        let badges = [];
        if (cfg.show_port && d.bus_id) badges.push(`<span class="badge badge-port"><img src="/icons/badge-port.png"> Bus ${d.bus_id}</span>`);
        if (cfg.show_vid_pid && d.vid_pid) badges.push(`<span class="badge badge-vidpid"><img src="/icons/badge-vidpid.png"> ${d.vid_pid}</span>`);
        if (d.server_ip) badges.push(`<span class="badge badge-server"><img src="/icons/badge-server.png"> ${d.server_ip}</span>`);

        return `
            <div class="card">
                <div class="card-main">
                    <div class="card-left">
                        <div class="card-icon"><img src="${iconSrc}"></div>
                        <div class="card-info">
                            <div class="card-title">${title}</div>
                            <div class="card-sub">${badges.join(" ")}</div>
                        </div>
                    </div>
                    <div class="card-actions">
                        <button class="btn btn-primary" onclick="attachSingleDevice('${d.server_ip}', '${d.bus_id}')"><img src="/icons/network-connect.png"> Attach</button>
                        <button class="btn" onclick="powerCycleDevice('${d.server_ip}', '${d.bus_id}')"><img src="/icons/power-cycle.png"> Power Cycle</button>
                        <button class="btn" onclick="openNicknameModal('${d.identifier_key || d.bus_id}', '${encodeURIComponent(title)}')"><img src="/icons/rename.png"> Rename</button>
                        <button class="btn btn-blacklist" onclick="blacklistDevice('', '${d.identifier_key || d.vid_pid || d.bus_id}', '${encodeURIComponent(title)}', '${d.vid_pid || ""}', '${d.bus_id || ""}', '${iconName}', ${d.is_controller ? "true" : "false"})"><img src="/icons/blacklist.png"> Blacklist</button>
                    </div>
                </div>
            </div>
        `;
    }).join("");
}

function renderDiscoveredServers() {
    const sec = document.getElementById("discovered-section");
    const c = document.getElementById("discovered-list");
    const dSrvs = currentStatus.discovered_servers || [];
    if (dSrvs.length === 0) {
        if (sec) sec.style.display = "none";
        return;
    }
    if (sec) sec.style.display = "block";
    c.innerHTML = dSrvs.map(d => {
        const title = d.name ? `${d.name} (${d.ip})` : d.ip;
        let badges = [
            '<span class="badge badge-online">mDNS Discovered</span>',
            `<span class="badge"><img src="/icons/badge-server.png"> Port ${d.port}</span>`
        ];
        if (d.auth_required) {
            badges.push('<span class="badge badge-warning">🔒 Token Protected</span>');
        }
        return `
            <div class="card">
                <div class="card-main">
                    <div class="card-left">
                        <div class="card-icon"><img src="/icons/discovered-server.png"></div>
                        <div class="card-info">
                            <div class="card-title">${title}</div>
                            <div class="card-sub">${badges.join(" ")}</div>
                        </div>
                    </div>
                    <div class="card-actions">
                        <button class="btn btn-primary" onclick="addDiscoveredServer('${d.ip}', ${d.port}, '${encodeURIComponent(d.name || d.ip)}', ${d.auth_required})"><img src="/icons/add-server.png"> Add Server</button>
                    </div>
                </div>
            </div>
        `;
    }).join("");
}

function renderBlacklistedDevices() {
    const sec = document.getElementById("blacklisted-section");
    const c = document.getElementById("blacklisted-list");
    const list = currentStatus.blacklisted_devices || [];
    if (list.length === 0) {
        if (sec) sec.style.display = "none";
        return;
    }
    if (sec) sec.style.display = "block";
    c.innerHTML = list.map(item => {
        const isObj = (typeof item === "object" && item !== null);
        const ident = isObj ? (item.identifier || item.vid_pid || item.name) : item;
        const name = isObj ? (item.name || item.identifier) : item;
        const vidPid = isObj ? item.vid_pid : "";
        const busId = isObj ? item.bus_id : "";

        let iconName = "generic-usb";
        if (isObj && item.is_controller) {
            iconName = "gamepad";
        } else if (isObj && item.icon_alias) {
            iconName = item.icon_alias;
        } else if (typeof name === "string") {
            const nl = name.toLowerCase();
            if (nl.includes("controller") || nl.includes("gamepad") || nl.includes("dualsense") || nl.includes("nes") || nl.includes("joystick")) {
                iconName = "gamepad";
            } else if (nl.includes("storage") || nl.includes("flash") || nl.includes("drive") || nl.includes("disk")) {
                iconName = "drive-harddisk";
            } else if (nl.includes("audio") || nl.includes("sound") || nl.includes("dac") || nl.includes("speaker") || nl.includes("headset")) {
                iconName = "audio-card";
            } else if (nl.includes("keyboard")) {
                iconName = "input-keyboard";
            } else if (nl.includes("mouse")) {
                iconName = "input-mouse";
            } else if (nl.includes("camera") || nl.includes("webcam")) {
                iconName = "camera-web";
            }
        }

        let badges = [];
        if (vidPid) badges.push(`<span class="badge badge-vidpid"><img src="/icons/badge-vidpid.png"> ${vidPid}</span>`);
        if (busId) badges.push(`<span class="badge badge-port"><img src="/icons/badge-port.png"> Bus ${busId}</span>`);

        return `
            <div class="card" style="margin-bottom: 6px;">
                <div class="card-main">
                    <div class="card-left">
                        <div class="card-icon" style="position: relative;">
                            <img src="/icons/${iconName}.png">
                        </div>
                        <div class="card-info">
                            <div class="card-title" style="color: #f87171;">${name}</div>
                            <div class="card-sub">${badges.join(" ")} <span class="badge badge-offline"><img src="/icons/blacklist.png"> Blocked</span></div>
                        </div>
                    </div>
                    <div class="card-actions">
                        <button class="btn btn-danger" onclick="unblacklistDevice('${encodeURIComponent(ident)}')"><img src="/icons/detach-btn.png"> Unblock</button>
                    </div>
                </div>
            </div>
        `;
    }).join("");
}

function checkGlobalEmpty() {
    const emptyEl = document.getElementById("global-empty");
    const srvCount = (currentStatus.servers || []).length;
    const attCount = (currentStatus.attached_devices || []).length;
    const avCount = (currentStatus.available_devices || []).length;
    const discCount = (currentStatus.discovered_servers || []).length;
    if (emptyEl) {
        emptyEl.style.display = (srvCount === 0 && attCount === 0 && avCount === 0 && discCount === 0) ? "block" : "none";
    }
}

/* User Action Handlers */
async function toggleServer(encodedIp) {
    const ip = decodeURIComponent(encodedIp);
    await API.toggleServer(ip);
    fetchStatus();
}

async function removeServer(encodedIp, port) {
    const ip = decodeURIComponent(encodedIp);
    if (!confirm(`Remove server ${ip}:${port}?`)) return;
    pendingRemovedServers[ip] = Date.now();
    if (currentStatus.servers) {
        currentStatus.servers = currentStatus.servers.filter(s => !(s.ip === ip && s.port === port));
        if (currentStatus.available_devices) {
            currentStatus.available_devices = currentStatus.available_devices.filter(d => d.server_ip !== ip);
        }
        if (currentStatus.attached_devices) {
            if (currentStatus.servers.length === 0) {
                currentStatus.attached_devices = [];
            } else {
                currentStatus.attached_devices = currentStatus.attached_devices.filter(d => d.server_ip !== ip);
            }
        }
        renderServers();
        renderAttachedDevices();
        renderAvailableDevices();
    }
    showToast("Removing server...");
    try {
        await API.removeServer(ip, port);
        showToast("Server removed and devices detached.");
    } catch (e) {
        console.error("Error removing server:", e);
    } finally {
        await fetchStatus();
    }
}

async function detachSingleDevice(port) {
    if (currentStatus.attached_devices) {
        const dev = currentStatus.attached_devices.find(d => String(d.port) === String(port));
        if (dev) {
            currentStatus.attached_devices = currentStatus.attached_devices.filter(d => String(d.port) !== String(port));
            const availDev = {
                server_ip: dev.server_ip,
                bus_id: dev.bus_id,
                desc: dev.raw_desc || dev.desc,
                clean_name: dev.clean_name,
                vid_pid: dev.vid_pid,
                identifier_key: dev.identifier_key,
                is_controller: dev.is_controller,
                icon_alias: dev.icon_alias
            };
            if (dev.server_ip && dev.bus_id && currentStatus.available_devices) {
                const exists = currentStatus.available_devices.some(d => d.server_ip === dev.server_ip && d.bus_id === dev.bus_id);
                if (!exists) {
                    currentStatus.available_devices.push(availDev);
                }
            }
            pendingDetachedPorts[String(port)] = { timestamp: Date.now(), dev: availDev };
            renderAttachedDevices();
            renderAvailableDevices();
        }
    }
    showToast("Detached device.");
    try {
        await API.detachDevice(port);
    } catch (e) {
        console.error("Error detaching device:", e);
    } finally {
        await fetchStatus();
    }
}

async function detachAllPorts() {
    if (currentStatus.attached_devices && currentStatus.attached_devices.length > 0) {
        const now = Date.now();
        if (currentStatus.available_devices) {
            for (const dev of currentStatus.attached_devices) {
                if (dev.server_ip && dev.bus_id) {
                    const availDev = {
                        server_ip: dev.server_ip,
                        bus_id: dev.bus_id,
                        desc: dev.raw_desc || dev.desc,
                        clean_name: dev.clean_name,
                        vid_pid: dev.vid_pid,
                        identifier_key: dev.identifier_key,
                        is_controller: dev.is_controller,
                        icon_alias: dev.icon_alias
                    };
                    const exists = currentStatus.available_devices.some(d => d.server_ip === dev.server_ip && d.bus_id === dev.bus_id);
                    if (!exists) {
                        currentStatus.available_devices.push(availDev);
                    }
                    if (dev.port) {
                        pendingDetachedPorts[String(dev.port)] = { timestamp: now, dev: availDev };
                    }
                }
            }
        }
        currentStatus.attached_devices = [];
        renderAttachedDevices();
        renderAvailableDevices();
    }
    showToast("Detached all devices.");
    try {
        await API.detachAll();
    } catch (e) {
        console.error("Error detaching all:", e);
    } finally {
        await fetchStatus();
    }
}

async function attachSingleDevice(ip, busid) {
    const key = `${ip}:${busid}`;
    if (currentStatus.available_devices) {
        const dev = currentStatus.available_devices.find(d => d.server_ip === ip && d.bus_id === busid);
        if (dev) {
            currentStatus.available_devices = currentStatus.available_devices.filter(d => !(d.server_ip === ip && d.bus_id === busid));
            pendingAttachDevices[key] = { timestamp: Date.now(), dev };
            renderAttachedDevices();
            renderAvailableDevices();
        }
    }
    showToast("Attaching device...");
    try {
        await API.attachDevice(ip, busid);
    } catch (e) {
        console.error("Error attaching device:", e);
    } finally {
        await fetchStatus();
    }
}

async function powerCycleDevice(ip, busid) {
    showToast(`⚡ Initiating power cycle for USB ${busid}...`);
    try {
        const res = await API.powerCycle(ip, busid);
        if (res && res.status === "ok") {
            showToast(`⚡ Power cycle completed for USB ${busid}.`);
        } else {
            showToast(`⚡ Power cycle signal sent.`);
        }
    } catch (e) {
        console.error("Error power cycling device:", e);
    } finally {
        fetchStatus();
    }
}

async function recoverZombieConnections() {
    showToast("⚡ Recovering USB connection: clearing stale sockets & rebinding...");
    try {
        await API.recoverZombies();
        showToast("⚡ Rebind requested. Reconnecting devices...");
    } catch (e) {
        console.error("Error recovering zombies:", e);
    } finally {
        setTimeout(fetchStatus, 800);
    }
}

async function openStorageDevice(port) {
    await API.openStorage(port);
}

async function toggleDeviceAudio(port, currentlyEnabled) {
    try {
        const res = await API.toggleAudio(port);
        if (res && res.status === "ok") {
            showToast(res.audio_enabled ? "Controller audio enabled" : "Controller audio disabled & muted");
            await fetchStatus();
        } else {
            showToast("Failed to toggle audio", "error");
        }
    } catch (e) {
        console.error("Error toggling audio:", e);
        showToast("Error toggling audio: " + e, "error");
    }
}

/* Modals Management */
function promptAddServer() {
    document.getElementById("add-srv-ip").value = "";
    document.getElementById("add-srv-name").value = "";
    document.getElementById("add-srv-token").value = "";
    document.getElementById("add-server-modal").style.display = "flex";
    setTimeout(() => document.getElementById("add-srv-ip").focus(), 100);
}

function addDiscoveredServer(ip, port, nameEnc, authRequired) {
    document.getElementById("add-srv-ip").value = ip;
    document.getElementById("add-srv-port").value = port;
    document.getElementById("add-srv-name").value = decodeURIComponent(nameEnc);
    document.getElementById("add-srv-token").value = "";
    document.getElementById("add-server-modal").style.display = "flex";
    if (authRequired) {
        setTimeout(() => document.getElementById("add-srv-token").focus(), 150);
    }
}

function closeAddServerModal() {
    document.getElementById("add-server-modal").style.display = "none";
}

async function submitAddServer() {
    const ip = document.getElementById("add-srv-ip").value.trim();
    const port = parseInt(document.getElementById("add-srv-port").value.trim()) || 3240;
    const name = document.getElementById("add-srv-name").value.trim();
    const token = document.getElementById("add-srv-token").value.trim();
    if (!ip) {
        alert("Please enter an IP address.");
        return;
    }
    closeAddServerModal();
    if (currentStatus.servers) {
        const existing = currentStatus.servers.find(s => s.ip === ip && s.port === port);
        if (existing) {
            existing.token = token;
            if (name) existing.name = name;
            existing.enabled = true;
        } else {
            currentStatus.servers.push({ ip, port, name: name || ip, token, enabled: true, is_alive: true });
        }
        if (currentStatus.discovered_servers) {
            currentStatus.discovered_servers = currentStatus.discovered_servers.filter(d => d.ip !== ip);
        }
        renderServers();
        renderDiscoveredServers();
    }
    showToast("Adding server...");
    try {
        await API.addServer({ ip, port, name, token, enabled: true });
        showToast("Server added successfully.");
    } catch (e) {
        console.error("Error adding server:", e);
    } finally {
        fetchStatus();
    }
}

function openNicknameModal(key, titleEnc) {
    editingNicknameKey = key;
    const title = decodeURIComponent(titleEnc);
    document.getElementById("nick-device-title").textContent = title;
    const currentNick = (currentStatus.config.nicknames || {})[key] || "";
    document.getElementById("nick-input").value = currentNick;
    document.getElementById("nickname-modal").style.display = "flex";
    setTimeout(() => document.getElementById("nick-input").focus(), 100);
}

function closeNicknameModal() {
    document.getElementById("nickname-modal").style.display = "none";
    editingNicknameKey = null;
}

async function saveNickname() {
    if (!editingNicknameKey) return;
    const nick = document.getElementById("nick-input").value.trim();
    await API.setNickname(editingNicknameKey, nick);
    closeNicknameModal();
    fetchStatus();
}

async function blacklistDevice(port, ident, titleEnc, vidPid, busId, iconAlias, isController) {
    const title = decodeURIComponent(titleEnc);
    if (confirm(`Blacklist device "${title}"?\nIt will be detached immediately and prevented from auto-connecting.`)) {
        await API.blacklistDevice({
            identifier: ident || vidPid || busId || port,
            name: title,
            port: port || "",
            vid_pid: vidPid || "",
            bus_id: busId || "",
            icon_alias: iconAlias || "generic-usb",
            is_controller: !!isController
        });
        showToast(`Blacklisted and detached ${title}`);
        fetchStatus();
    }
}

async function unblacklistDevice(itemEnc) {
    const item = decodeURIComponent(itemEnc);
    await API.unblacklistDevice(item);
    fetchStatus();
}

function openClientOptionsModal() {
    const cfg = currentStatus.config || {};
    document.getElementById("opt-auto-attach").checked = cfg.auto_attach !== false;
    document.getElementById("opt-remember-detached").checked = cfg.remember_detached_devices !== false;
    document.getElementById("opt-show-notifications").checked = cfg.show_notifications !== false;
    if (document.getElementById("opt-play-sound")) document.getElementById("opt-play-sound").checked = cfg.play_sound_cues !== false;
    if (document.getElementById("opt-power-cycle-attach")) document.getElementById("opt-power-cycle-attach").checked = cfg.power_cycle_on_attach !== false;
    document.getElementById("opt-auto-discover").checked = cfg.auto_discover !== false;
    document.getElementById("opt-enable-nicknames").checked = cfg.enable_nicknames !== false;
    document.getElementById("opt-enable-wol").checked = !!cfg.enable_wol_wake;
    const lanAllowed = cfg.allow_lan_access !== false;
    const lanCheck = document.getElementById("opt-allow-lan-access");
    if (lanCheck) {
        lanCheck.checked = lanAllowed;
        toggleLanUrlDisplay(lanAllowed);
    }
    
    const poll = parseFloat(cfg.polling_interval || 1.0);
    const pollSlider = document.getElementById("opt-polling-interval");
    if (pollSlider) {
        pollSlider.value = poll;
        const valEl = document.getElementById("opt-polling-val");
        if (valEl) valEl.textContent = poll.toFixed(1) + "s";
    }

    document.getElementById("opt-show-port").checked = cfg.show_port !== false;
    document.getElementById("opt-show-speed").checked = cfg.show_speed !== false;
    document.getElementById("opt-show-vid-pid").checked = cfg.show_vid_pid !== false;
    document.getElementById("opt-show-battery").checked = cfg.show_battery !== false;
    document.getElementById("opt-show-latency").checked = cfg.show_latency !== false;

    // Security & Hardening
    if (document.getElementById("opt-enable-csrf")) document.getElementById("opt-enable-csrf").checked = !!cfg.enable_web_csrf;
    if (document.getElementById("opt-enable-tls-pinning")) document.getElementById("opt-enable-tls-pinning").checked = !!cfg.enable_tls_pinning;
    const classFilter = !!cfg.enable_device_class_filter;
    if (document.getElementById("opt-enable-class-filter")) {
        document.getElementById("opt-enable-class-filter").checked = classFilter;
        const badUsbBox = document.getElementById("badusb-options");
        if (badUsbBox) badUsbBox.style.display = classFilter ? "block" : "none";
    }
    if (document.getElementById("opt-block-storage")) document.getElementById("opt-block-storage").checked = !!cfg.block_mass_storage;
    if (document.getElementById("opt-block-network")) document.getElementById("opt-block-network").checked = !!cfg.block_network_devices;
    if (document.getElementById("opt-block-keyboard")) document.getElementById("opt-block-keyboard").checked = !!cfg.block_hid_keyboards;

    document.getElementById("options-modal").style.display = "flex";
}

function closeClientOptionsModal() {
    document.getElementById("options-modal").style.display = "none";
}

async function saveClientOptions() {
    const payload = {
        auto_attach: document.getElementById("opt-auto-attach").checked,
        remember_detached_devices: document.getElementById("opt-remember-detached").checked,
        show_notifications: document.getElementById("opt-show-notifications").checked,
        play_sound_cues: document.getElementById("opt-play-sound") ? document.getElementById("opt-play-sound").checked : true,
        power_cycle_on_attach: document.getElementById("opt-power-cycle-attach") ? document.getElementById("opt-power-cycle-attach").checked : true,
        auto_discover: document.getElementById("opt-auto-discover").checked,
        enable_nicknames: document.getElementById("opt-enable-nicknames").checked,
        enable_wol_wake: document.getElementById("opt-enable-wol").checked,
        allow_lan_access: document.getElementById("opt-allow-lan-access") ? document.getElementById("opt-allow-lan-access").checked : true,
        polling_interval: parseFloat(document.getElementById("opt-polling-interval")?.value || 1.0),
        show_port: document.getElementById("opt-show-port").checked,
        show_speed: document.getElementById("opt-show-speed").checked,
        show_vid_pid: document.getElementById("opt-show-vid-pid").checked,
        show_battery: document.getElementById("opt-show-battery").checked,
        show_latency: document.getElementById("opt-show-latency").checked,
        enable_web_csrf: document.getElementById("opt-enable-csrf") ? document.getElementById("opt-enable-csrf").checked : false,
        enable_tls_pinning: document.getElementById("opt-enable-tls-pinning") ? document.getElementById("opt-enable-tls-pinning").checked : false,
        enable_device_class_filter: document.getElementById("opt-enable-class-filter") ? document.getElementById("opt-enable-class-filter").checked : false,
        block_mass_storage: document.getElementById("opt-block-storage") ? document.getElementById("opt-block-storage").checked : false,
        block_network_devices: document.getElementById("opt-block-network") ? document.getElementById("opt-block-network").checked : false,
        block_hid_keyboards: document.getElementById("opt-block-keyboard") ? document.getElementById("opt-block-keyboard").checked : false,
    };
    await API.saveOptions(payload);
    closeClientOptionsModal();
    fetchStatus();
}

function exportClientBackup() {
    window.location.href = "/api/export_client_config";
}

function triggerImportClientBackup() {
    document.getElementById("client-backup-file").click();
}

async function handleClientBackupFile(event) {
    const file = event.target.files[0];
    if (!file) return;
    const text = await file.text();
    try {
        const data = JSON.parse(text);
        await fetch("/api/import_client_config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data)
        });
        alert("Client configuration imported successfully.");
        closeClientOptionsModal();
        fetchStatus();
    } catch (e) {
        alert("Invalid configuration file JSON.");
    }
}

async function restartClient(event) {
    if (confirm("Restart Auto USB/IP Client?")) {
        const btn = event?.target?.closest('button');
        if (btn) {
            btn.innerHTML = '<span class="spinner-inline"></span> Restarting...';
            btn.disabled = true;
        }
        showToast("Client restarting...");
        try {
            await API.restartClient();
        } catch (e) {}
        setTimeout(() => {
            const checkInterval = setInterval(() => {
                fetch("/api/status").then(r => {
                    if (r.ok) {
                        clearInterval(checkInterval);
                        location.reload();
                    }
                }).catch(() => {});
            }, 800);
        }, 1000);
    }
}

/* Server Remote Console is managed in console.js */

/* Server Remote Settings Modal */
function prefetchServerSettings(servers) {
    if (!servers || !Array.isArray(servers)) return;
    for (const s of servers) {
        if (s.ip && s.enabled && s.is_alive) {
            API.getServerStatus(s.ip).then(res => {
                if (res && res.status === "ok") {
                    serverStatusCache[s.ip] = res;
                    saveServerStatusCache();
                }
            }).catch(() => {});
        }
    }
}

function populateServerSettingsForm(data) {
    if (!data || data.status !== "ok") return;
    const m = data.metrics || {};
    const tempEl = document.getElementById("srv-m-temp");
    if (tempEl) {
        tempEl.textContent = m.cpu_temp || "--";
        tempEl.className = "badge";
        if (m.cpu_temp && m.cpu_temp !== "N/A") {
            const tempNum = parseFloat(m.cpu_temp);
            if (tempNum < 60) tempEl.classList.add("badge-success");
            else if (tempNum < 75) tempEl.classList.add("badge-warning");
            else tempEl.classList.add("badge-danger");
        }
    }
    const ramEl = document.getElementById("srv-m-ram");
    if (ramEl) ramEl.textContent = m.ram_usage || "--";
    const upEl = document.getElementById("srv-m-uptime");
    if (upEl) upEl.textContent = m.uptime || "--";
    const kernEl = document.getElementById("srv-m-kernel");
    if (kernEl) kernEl.textContent = m.kernel || "--";
    
    const cfg = data.config || {};
    const discEl = document.getElementById("srv-opt-discovery");
    if (discEl) discEl.checked = cfg.enable_discovery !== false;
    const authEl = document.getElementById("srv-opt-auth");
    if (authEl) authEl.checked = !!cfg.enable_auth;
    const tokenEl = document.getElementById("srv-opt-token");
    if (tokenEl) tokenEl.value = cfg.auth_token || "";
    const subEl = document.getElementById("srv-opt-subnet");
    if (subEl) subEl.checked = !!cfg.enable_subnet_filter;
    const tlsEl = document.getElementById("srv-opt-tls");
    if (tlsEl) tlsEl.checked = cfg.enable_tls !== false;
    const powerEl = document.getElementById("srv-opt-startup-power");
    if (powerEl) powerEl.checked = cfg.startup_power_cycle !== false;
    const vbusEl = document.getElementById("srv-opt-vbus-delay");
    if (vbusEl) vbusEl.value = parseFloat(cfg.vbus_off_delay || cfg.power_reset_off_delay || 2.5);
    const wolEl = document.getElementById("srv-opt-wol");
    if (wolEl) wolEl.checked = !!cfg.enable_wake_on_lan;
    const rebindEl = document.getElementById("srv-opt-rebind");
    if (rebindEl) rebindEl.checked = cfg.auto_rebind_on_boot !== false;
    
    const bl = data.blacklist || [];
    const blListEl = document.getElementById("srv-blacklist-list");
    if (blListEl) {
        blListEl.innerHTML = bl.length === 0 ? '<div style="font-size:0.75rem;color:var(--text-muted);">No blacklisted hardware.</div>' : bl.map(item => `
            <div style="display:flex; justify-content:space-between; align-items:center; background:#12141c; padding:3px 8px; border-radius:4px; border:1px solid var(--border-color); font-size:0.75rem;">
                <span style="font-family:monospace;">${item}</span>
                <button class="btn btn-danger" style="padding:1px 5px; font-size:0.7rem;" onclick="removeServerBlacklistItem('${item}')">Unblock</button>
            </div>
        `).join("");
    }
}

async function openServerSettingsModal(encodedIp, nameEnc) {
    const ip = decodeURIComponent(encodedIp);
    const name = decodeURIComponent(nameEnc);
    activeServerSettingsIp = ip;
    
    const titleEl = document.getElementById("modal-server-title");
    if (titleEl) {
        titleEl.innerHTML = `<img src="/icons/configure.png" style="width:20px;height:20px;object-fit:contain;"> Server Settings — ${name}`;
    }
    
    // Instant persistent cache population (0ms even after client restart)
    if (serverStatusCache[ip]) {
        populateServerSettingsForm(serverStatusCache[ip]);
    } else {
        // Fallback default state so form is never blank
        populateServerSettingsForm({
            status: "ok",
            metrics: { cpu_temp: "--", ram_usage: "--", uptime: "--", kernel: "--" },
            config: { enable_tls: true, enable_discovery: true, enable_auth: false, enable_subnet_filter: false, auto_rebind_on_boot: true, startup_power_cycle: false, vbus_off_delay: 2.5, enable_wake_on_lan: false },
            blacklist: []
        });
    }
    
    document.getElementById("server-settings-modal").style.display = "flex";
    
    try {
        const data = await API.getServerStatus(ip);
        if (data && data.status === "ok") {
            serverStatusCache[ip] = data;
            saveServerStatusCache();
            populateServerSettingsForm(data);
        }
    } catch (e) {
        console.error("Error loading server status:", e);
    }
}

function closeServerSettingsModal() {
    document.getElementById("server-settings-modal").style.display = "none";
    activeServerSettingsIp = null;
}

async function saveServerSettings() {
    if (!activeServerSettingsIp) return;
    const discEl = document.getElementById("srv-opt-discovery");
    const cfgPayload = {
        enable_discovery: discEl ? discEl.checked : true,
        enable_auth: document.getElementById("srv-opt-auth").checked,
        auth_token: document.getElementById("srv-opt-token").value.trim(),
        enable_tls: document.getElementById("srv-opt-tls") ? document.getElementById("srv-opt-tls").checked : true,
        enable_subnet_filter: document.getElementById("srv-opt-subnet").checked,
        auto_bind: document.getElementById("srv-opt-rebind").checked,
        startup_power_cycle: document.getElementById("srv-opt-startup-power") ? document.getElementById("srv-opt-startup-power").checked : true,
        vbus_off_delay: parseFloat(document.getElementById("srv-opt-vbus-delay")?.value || 2.5),
        enable_wake_on_lan: document.getElementById("srv-opt-wol") ? document.getElementById("srv-opt-wol").checked : false,
        auto_rebind_on_boot: document.getElementById("srv-opt-rebind").checked
    };
    try {
        const res = await API.saveServerConfig(activeServerSettingsIp, cfgPayload);
        if (res.status === "ok") {
            showToast("Server settings saved successfully.");
            closeServerSettingsModal();
        }
    } catch (e) {
        alert("Failed to save server settings: " + e);
    }
}

async function restartServerDaemon() {
    if (!activeServerSettingsIp) return;
    const ip = activeServerSettingsIp;
    if (confirm("Restart the background server daemon on this remote device?")) {
        pendingRestartServers[ip] = { text: "Restarting...", timestamp: Date.now(), timeout: 12000 };
        renderServers();
        closeServerSettingsModal();
        try {
            await API.restartServerDaemon(ip);
            showToast("Server daemon restarting...");
        } catch (e) {
            console.error(e);
        }
    }
}

async function rebootServerSystem() {
    if (!activeServerSettingsIp) return;
    const ip = activeServerSettingsIp;
    if (confirm("REBOOT the entire remote device (e.g. Raspberry Pi)?")) {
        pendingRestartServers[ip] = { text: "Rebooting System...", timestamp: Date.now(), timeout: 35000 };
        renderServers();
        closeServerSettingsModal();
        try {
            await API.rebootServerSystem(ip);
            showToast("System reboot initiated...");
        } catch (e) {
            console.error(e);
        }
    }
}

// Global Enter Key Listeners for Modals
document.addEventListener("DOMContentLoaded", () => {
    fetchStatus();
    setInterval(fetchStatus, 3000);

    const srvInputs = ["add-srv-ip", "add-srv-port", "add-srv-name", "add-srv-token"];
    srvInputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener("keydown", (e) => {
                if (e.key === "Enter") {
                    e.preventDefault();
                    submitAddServer();
                }
            });
        }
    });

    const nickInput = document.getElementById("nick-input");
    if (nickInput) {
        nickInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                saveNickname();
            }
        });
    }
});

async function toggleTouchpadMouse(port, enabled) {
    try {
        const res = await API.toggleTouchpadMouse(port, enabled);
        if (res && res.status === "ok") {
            showToast(`Trackpad mouse ${res.touchpad_mouse_enabled ? 'enabled' : 'disabled (gaming mode)'}`);
            await fetchStatus();
        } else {
            showToast("Failed to toggle trackpad mouse", "error");
        }
    } catch (e) {
        showToast("Error toggling trackpad mouse: " + e, "error");
    }
}
window.toggleTouchpadMouse = toggleTouchpadMouse;
window.updateStatus = fetchStatus;

function toggleLanUrlDisplay(enabled) {
    const infoEl = document.getElementById("lan-url-info");
    const urlEl = document.getElementById("opt-lan-url");
    if (!infoEl || !urlEl) return;
    if (enabled) {
        const hostIp = currentStatus.local_ip || window.location.hostname || "127.0.0.1";
        const port = currentStatus.web_port || 3242;
        urlEl.textContent = `http://${hostIp}:${port}/`;
        infoEl.style.display = "block";
    } else {
        infoEl.style.display = "none";
    }
}
