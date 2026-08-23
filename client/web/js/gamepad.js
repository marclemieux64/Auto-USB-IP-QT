
// --------------------------------------------------------------------------
// Kenney Input Prompts Asset Resolvers
// --------------------------------------------------------------------------
function getKenneyButtonPrompt(family, buttonIndex, label, alt) {
    const fam = (family || "generic").toLowerCase();
    const l = (label || "").toLowerCase();
    const a = (alt || "").toLowerCase();
    const idx = parseInt(buttonIndex, 10);

    // PlayStation Family (DualSense, PS4, PS3)
    if (fam.includes("playstation") || fam.includes("sony") || fam.includes("dualsense")) {
        const basePath = "/assets/kenney_input/PlayStation%20Series/Vector/";
        if (l.includes("cross") || l === "x" || idx === 0) return basePath + "playstation_button_color_cross.svg";
        if (l.includes("circle") || idx === 1) return basePath + "playstation_button_color_circle.svg";
        if (l.includes("square") || idx === 2) return basePath + "playstation_button_color_square.svg";
        if (l.includes("triangle") || idx === 3) return basePath + "playstation_button_color_triangle.svg";
        if (l.includes("l1") || idx === 4) return basePath + "playstation_trigger_l1.svg";
        if (l.includes("r1") || idx === 5) return basePath + "playstation_trigger_r1.svg";
        if (l.includes("l2") || idx === 6) return basePath + "playstation_trigger_l2.svg";
        if (l.includes("r2") || idx === 7) return basePath + "playstation_trigger_r2.svg";
        if (l.includes("share") || l.includes("create") || idx === 8) return basePath + "playstation5_button_create.svg";
        if (l.includes("options") || l.includes("start") || idx === 9) return basePath + "playstation5_button_options.svg";
        if (l.includes("ps") || l.includes("home") || idx === 10) return null; // Custom ultra-bold PS badge
        if (l.includes("l3") || l.includes("left stick") || idx === 11) return basePath + "playstation_button_l3.svg";
        if (l.includes("r3") || l.includes("right stick") || idx === 12) return basePath + "playstation_button_r3.svg";
        if (l.includes("touchpad") && !l.includes("mic")) return basePath + "playstation5_touchpad.svg";
        if (l.includes("mute") || l.includes("mic") || idx === 13) return basePath + "playstation5_button_mute.svg";
        return basePath + "playstation_button_color_cross.svg";
    }

    // Xbox Family
    if (fam.includes("xbox") || fam.includes("microsoft") || fam.includes("xinput")) {
        const basePath = "/assets/kenney_input/Xbox%20Series/Vector/";
        
        // Exact button label matching:
        if (l === "a" || l.includes("btn_a") || l.includes("button a")) return basePath + "xbox_button_color_a.png";
        if (l === "b" || l.includes("btn_b") || l.includes("button b")) return basePath + "xbox_button_color_b.png";
        if (l === "x" || l.includes("btn_x") || l.includes("button x")) return basePath + "xbox_button_color_x.png";
        if (l === "y" || l.includes("btn_y") || l.includes("button y")) return basePath + "xbox_button_color_y.png";
        if (l === "lb" || l.includes("left bumper") || l.includes("l1")) return basePath + "xbox_lb.png";
        if (l === "rb" || l.includes("right bumper") || l.includes("r1")) return basePath + "xbox_rb.png";
        if (l === "lt" || l.includes("left trigger") || l.includes("l2")) return basePath + "xbox_lt.png";
        if (l === "rt" || l.includes("right trigger") || l.includes("r2")) return basePath + "xbox_rt.png";
        if (l.includes("view") || l.includes("back") || l.includes("select")) return basePath + "xbox_button_view.png";
        if (l.includes("menu") || l.includes("start")) return basePath + "xbox_button_menu.png";
        if (l.includes("guide") || l === "xbox" || l.includes("home")) return basePath + "xbox_guide.png";
        if (l.includes("ls") || l.includes("l3") || l.includes("left stick") || l.includes("thumbl")) return basePath + "xbox_ls.png";
        if (l.includes("rs") || l.includes("r3") || l.includes("right stick") || l.includes("thumbr")) return basePath + "xbox_rs.png";
        if (l.includes("share") || l.includes("capture")) return basePath + "xbox_button_share.png";

        // Linux xpad driver index fallback:
        // 0: A, 1: B, 2: X, 3: Y, 4: LB, 5: RB, 6: View/Back, 7: Menu/Start, 8: Xbox Guide, 9: LS, 10: RS, 11: Share
        const xpadOrder = [
            "xbox_button_color_a.png",     // 0: A
            "xbox_button_color_b.png",     // 1: B
            "xbox_button_color_x.png",     // 2: X
            "xbox_button_color_y.png",     // 3: Y
            "xbox_lb.png",                 // 4: LB
            "xbox_rb.png",                 // 5: RB
            "xbox_button_view.png",        // 6: View / Back
            "xbox_button_menu.png",        // 7: Menu / Start
            "xbox_guide.png",              // 8: Xbox Guide
            "xbox_ls.png",                 // 9: LS (Left Stick Click)
            "xbox_rs.png",                 // 10: RS (Right Stick Click)
            "xbox_button_share.png"        // 11: Share
        ];
        if (idx < xpadOrder.length) {
            return basePath + xpadOrder[idx];
        }
        return basePath + "xbox_button_color_a.png";
    }

    // Nintendo Family (Switch, NES, SNES, Wii, Gamecube)
    if (fam.includes("nintendo") || fam.includes("switch") || fam.includes("nes") || fam.includes("snes") || fam.includes("wii") || fam.includes("gamecube")) {
        const basePath = "/assets/kenney_input/Nintendo%20Switch/Vector/";
        
        // Exact label matching:
        if (l === "a" || l === "btn_a" || l === "button a") return basePath + "switch_button_a.png";
        if (l === "b" || l === "btn_b" || l === "button b") return basePath + "switch_button_b.png";
        if (l === "x" || l === "btn_x" || l === "button x" || l.includes("turbo a")) return basePath + "switch_button_x.png";
        if (l === "y" || l === "btn_y" || l === "button y" || l.includes("turbo b")) return basePath + "switch_button_y.png";
        if (l === "l" || l.includes("left bumper") || l.includes("l1")) return basePath + "switch_button_l.png";
        if (l === "r" || l.includes("right bumper") || l.includes("r1")) return basePath + "switch_button_r.png";
        if (l === "zl" || l.includes("left trigger") || l.includes("l2")) return basePath + "switch_button_zl.png";
        if (l === "zr" || l.includes("right trigger") || l.includes("r2")) return basePath + "switch_button_zr.png";
        if (l.includes("minus") || l.includes("select") || l.includes("back") || l === "-") return basePath + "switch_button_minus.png";
        if (l.includes("plus") || l.includes("start") || l === "+") return basePath + "switch_button_plus.png";
        if (l.includes("home") || l.includes("guide")) return basePath + "switch_button_home.png";
        if (l.includes("capture") || l.includes("share") || l.includes("screenshot")) return basePath + "switch_button_capture.png";
        if (l.includes("ls") || l.includes("l3") || l.includes("left stick")) return basePath + "switch_stick_l_press.png";
        if (l.includes("rs") || l.includes("r3") || l.includes("right stick")) return basePath + "switch_stick_r_press.png";

        // NES / SNES 4-button layout (matching USB encoder hardware pinout):
        if (fam.includes("nes") || fam.includes("retro") || fam.includes("gembird")) {
            if (idx === 0) return basePath + "switch_button_x.png"; // 0: X (Top)
            if (idx === 1) return basePath + "switch_button_a.png"; // 1: A (Right)
            if (idx === 2) return basePath + "switch_button_b.png"; // 2: B (Bottom)
            if (idx === 3) return basePath + "switch_button_y.png"; // 3: Y (Left)
            if (idx === 8) return basePath + "switch_button_minus.png"; // Select
            if (idx === 9) return basePath + "switch_button_plus.png";  // Start
            return null; // Unwired pins (B4-B7, B10) render as clean numeric labels
        }

        // Switch Pro standard layout fallback:
        const switchOrder = [
            "switch_button_b.png",      // 0: B
            "switch_button_a.png",      // 1: A
            "switch_button_y.png",      // 2: Y
            "switch_button_x.png",      // 3: X
            "switch_button_l.png",      // 4: L
            "switch_button_r.png",      // 5: R
            "switch_button_zl.png",     // 6: ZL
            "switch_button_zr.png",     // 7: ZR
            "switch_button_minus.png",  // 8: Minus (-)
            "switch_button_plus.png",   // 9: Plus (+)
            "switch_stick_l_press.png", // 10: LS
            "switch_stick_r_press.png", // 11: RS
            "switch_button_home.png",   // 12: Home
            "switch_button_capture.png" // 13: Capture
        ];
        if (idx < switchOrder.length) {
            return basePath + switchOrder[idx];
        }
        return null;
    }

    // Generic Fallback
    const genPath = "/assets/kenney_input/Generic/Vector/";
    if (idx <= 3) return genPath + "generic_button_circle.png";
    if (idx <= 7) return genPath + "generic_button_trigger_a.png";
    return genPath + "generic_button.png";
}

function getKenneyDpadPrompt(family, direction) {
    const fam = (family || "generic").toLowerCase();
    const dir = direction.toLowerCase();
    if (fam.includes("playstation") || fam.includes("sony") || fam.includes("dualsense")) {
        return `/assets/kenney_input/PlayStation%20Series/Vector/playstation_dpad_${dir}.svg`;
    }
    if (fam.includes("xbox") || fam.includes("microsoft")) {
        return `/assets/kenney_input/Xbox%20Series/Vector/xbox_dpad_${dir}.svg`;
    }
    if (fam.includes("nintendo") || fam.includes("switch") || fam.includes("nes") || fam.includes("wii")) {
        return `/assets/kenney_input/Nintendo%20Switch/Vector/switch_dpad_${dir}.svg`;
    }
    return `/assets/kenney_input/Generic/Vector/generic_stick_${dir}.svg`;
}

// Unified Kenney Controller Hero Resolver (shared with Dashboard)
if (typeof getKenneyControllerHero !== "function") {
    window.getKenneyControllerHero = function(family, cleanName, controllerType, desc) {
        const text = [family, cleanName, controllerType, desc].filter(Boolean).join(" ").toLowerCase();
        if (text.includes("dualsense") || text.includes("054c:0ce6") || text.includes("054c:0df2") || text.includes("ps5")) {
            return "/assets/kenney_input/PlayStation%20Series/Vector/controller_playstation5.svg";
        }
        if (text.includes("dualshock 4") || text.includes("054c:05c4") || text.includes("054c:09cc") || text.includes("ps4")) {
            return "/assets/kenney_input/PlayStation%20Series/Vector/controller_playstation4.svg";
        }
        if (text.includes("playstation") || text.includes("sony") || text.includes("054c:")) {
            return "/assets/kenney_input/PlayStation%20Series/Vector/controller_playstation5.svg";
        }
        if (text.includes("series") || text.includes("rematch") || text.includes("0e6f:034a")) {
            return "/assets/kenney_input/Xbox%20Series/Vector/controller_xboxseries.svg";
        }
        if (text.includes("xbox 360")) {
            return "/assets/kenney_input/Xbox%20Series/Vector/controller_xbox360.svg";
        }
        if (text.includes("xbox") || text.includes("xpad")) {
            return "/assets/kenney_input/Xbox%20Series/Vector/controller_xboxone.svg";
        }
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
        return "/assets/kenney_input/Flairs/Vector/controller_generic.svg";
    };
}

let activeGamepadPort = null;
let gamepadInterval = null;
let activeGamepadConfig = null;
let activeDsColor = { r: 0, g: 100, b: 255 };
let activeDsPlayer = 1;
let activeDsMute = false;
let activeTriggerMode = "off";
let activeTriggerTarget = "both";

const TRIGGER_DESCRIPTIONS = {
    "off": "Standard trigger without resistance.",
    "gun": "Two-stage pull with a distinct break point.",
    "machine_gun": "Pulsing recoil during trigger pull.",
    "bow": "Progressive tension increasing through the pull.",
    "abs": "High-frequency vibration under heavy pull.",
    "heavy": "Continuous heavy resistance through full travel."
};

async function openGamepadTesterModal(port, titleEnc) {
    const title = decodeURIComponent(titleEnc);
    activeGamepadPort = port;
    activeGamepadConfig = null;

    // 1. Immediately reset and hide all capability sections from any previously tested gamepad
    const dynamicSections = [
        "gp-triggers-section",
        "gp-sticks-section",
        "gp-lstick-box",
        "gp-rstick-box",
        "gp-motion-section",
        "gp-touchpad-section",
        "gp-ps-controls"
    ];
    dynamicSections.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = "none";
    });

    // 2. Pre-detect layout hints from title so hero icon and sub-badges match instantly
    const lowerTitle = (title || "").toLowerCase();
    const isPs = lowerTitle.includes("dualsense") || lowerTitle.includes("ps5") || lowerTitle.includes("ps4") || lowerTitle.includes("playstation");
    const isSnes = lowerTitle.includes("snes") || lowerTitle.includes("nes") || lowerTitle.includes("retrolink") || lowerTitle.includes("tomee") || lowerTitle.includes("gembird");
    const isXbox = lowerTitle.includes("xbox");

    let guessedFamily = "generic";
    if (isPs) guessedFamily = "playstation";
    else if (isXbox) guessedFamily = "xbox";
    else if (isSnes) guessedFamily = "nintendo";

    const heroImg = getKenneyControllerHero(guessedFamily, title, "", "");
    document.getElementById("modal-gamepad-title").innerHTML = `<img id="modal-gamepad-hero-icon" src="${heroImg}" style="height:26px;width:auto;max-width:40px;object-fit:contain;margin-right:6px;"> Gamepad Tester — ${title}`;
    document.getElementById("modal-gamepad-sub").innerHTML = `<span class="badge" style="background:#2563eb; color:#fff; font-weight:600;"><img src="${heroImg}" style="width:14px;height:14px;object-fit:contain;margin-right:5px;vertical-align:middle;">${isPs ? 'PlayStation Controller' : (isSnes ? 'Retro Controller' : 'Gamepad')}</span> <span class="badge">Loading layout...</span>`;
    const featEl = document.getElementById("modal-gamepad-features");
    if (featEl) { featEl.innerHTML = ""; featEl.style.display = "none"; }

    // 3. Reset visualizers
    document.getElementById("lt-fill").style.width = "0%";
    document.getElementById("rt-fill").style.width = "0%";
    document.getElementById("lt-val").textContent = "0%";
    document.getElementById("rt-val").textContent = "0%";
    document.getElementById("ls-dot").style.left = "50%";
    document.getElementById("ls-dot").style.top = "50%";
    document.getElementById("rs-dot").style.left = "50%";
    document.getElementById("rs-dot").style.top = "50%";
    document.getElementById("ls-coords").textContent = "X: +0.00  Y: +0.00";
    document.getElementById("rs-coords").textContent = "X: +0.00  Y: +0.00";
    ["up", "down", "left", "right"].forEach(dir => {
        const d = document.getElementById("dpad-" + dir);
        if (d) d.classList.remove("active");
    });
    document.getElementById("gamepad-buttons-grid").innerHTML = '<div style="grid-column: 1/-1; text-align:center; font-size:0.8rem; color:var(--text-muted); padding:10px;">Loading button layout...</div>';

    // 4. Fetch initial hardware state FIRST before revealing modal to guarantee exact layout on frame 1
    try {
        await pollGamepadState();
    } catch (e) {
        console.error("Initial gamepad state poll failed:", e);
    }

    // 5. Reveal modal with the exact right layout rendered instantly
    document.getElementById("gamepad-modal").style.display = "flex";
    updateModalAudioState();

    // 6. Explicitly reset physical trigger motors to smooth/off on modal start
    setDualSenseTriggerMode("off");
    API.sendGamepadControl({ port, action: "set_trigger", trigger_mode: "off", trigger_target: "both" });

    // 7. Start continuous 50ms polling interval
    if (gamepadInterval) clearInterval(gamepadInterval);
    gamepadInterval = setInterval(pollGamepadState, 50);
}

function closeGamepadModal() {
    document.getElementById("gamepad-modal").style.display = "none";
    if (gamepadInterval) {
        clearInterval(gamepadInterval);
        gamepadInterval = null;
    }
    if (activeGamepadPort) {
        API.sendGamepadControl({ port: activeGamepadPort, action: "set_trigger", trigger_mode: "off", trigger_target: "both" });
    }
    activeTriggerMode = "off";
    activeGamepadPort = null;
    activeGamepadConfig = null;

    // Clear dynamic sections on close so previous state is immediately sanitized
    const dynamicSections = [
        "gp-triggers-section",
        "gp-sticks-section",
        "gp-lstick-box",
        "gp-rstick-box",
        "gp-motion-section",
        "gp-touchpad-section",
        "gp-ps-controls"
    ];
    dynamicSections.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = "none";
    });
    document.getElementById("gamepad-buttons-grid").innerHTML = "";
}

async function pollGamepadState() {
    if (!activeGamepadPort) return;
    try {
        const data = await API.getGamepadState(activeGamepadPort);
        if (!data) return;

        // 1. Initial adaptive configuration build
        if (!activeGamepadConfig || activeGamepadConfig.family !== data.family || activeGamepadConfig.clean_name !== data.clean_name) {
            activeGamepadConfig = data;
            
            // Sync hero header icon with live detected family & controller type
            const heroIcon = getKenneyControllerHero(data.family, data.clean_name, data.controller_type, data.raw_desc || "");
            const heroElem = document.getElementById("modal-gamepad-hero-icon");
            if (heroElem) {
                heroElem.src = heroIcon;
            }
            
            // Line 1: Controller Profile, Battery, Polling Latency
            let infoBadges = [
                `<span class="badge" style="background:#2563eb; color:#fff; font-weight:600;"><img src="${heroIcon}" style="width:14px;height:14px;object-fit:contain;margin-right:5px;vertical-align:middle;">${data.controller_type || 'Gamepad'}</span>`
            ];
            if (data.battery) infoBadges.push(`<span class="badge badge-battery"><img src="/icons/badge-battery.png"> Battery: ${data.battery}</span>`);
            infoBadges.push(`<span class="badge badge-latency" id="modal-gp-latency-badge" style="background:rgba(56,189,248,0.18); color:#38bdf8; border:1px solid rgba(56,189,248,0.3);"><img src="/icons/badge-latency.png"> <span id="modal-gp-latency-text">Polling: ${data.latency_str || 'Measuring...'}</span></span>`);
            document.getElementById("modal-gamepad-sub").innerHTML = infoBadges.join(" ");

            // Line 2: Independent Hardware Features on their own dedicated row
            let featBadges = [];
            if (data.has_touchpad) featBadges.push(`<span class="badge" style="background:rgba(59,130,246,0.2); color:#60a5fa;">Touchpad</span>`);
            if (data.has_accel) featBadges.push(`<span class="badge" style="background:rgba(16,185,129,0.2); color:#34d399;">Accelerometer</span>`);
            if (data.has_gyro) featBadges.push(`<span class="badge" style="background:rgba(20,184,166,0.2); color:#2dd4bf;">Gyroscope</span>`);
            if (data.has_adaptive_triggers || data.is_dualsense) featBadges.push(`<span class="badge" style="background:rgba(245,158,11,0.2); color:#fbbf24;">Adaptive Triggers</span>`);
            if (data.has_rgb_led || data.is_dualsense || data.family === "playstation") featBadges.push(`<span class="badge" style="background:rgba(168,85,247,0.2); color:#c084fc;">RGB Lightbar</span>`);

            const featContainer = document.getElementById("modal-gamepad-features");
            if (featContainer) {
                if (featBadges.length > 0) {
                    featContainer.innerHTML = featBadges.join(" ");
                    featContainer.style.display = "flex";
                } else {
                    featContainer.innerHTML = "";
                    featContainer.style.display = "none";
                }
            }

            // Dynamically show/hide sections based on physical hardware capabilities from SDL DB
            const trigSec = document.getElementById("gp-triggers-section");
            if (trigSec) trigSec.style.display = data.has_triggers ? "flex" : "none";

            const sticksSec = document.getElementById("gp-sticks-section");
            if (sticksSec) sticksSec.style.display = (data.has_left_stick || data.has_right_stick) ? "flex" : "none";

            const lstickBox = document.getElementById("gp-lstick-box");
            if (lstickBox) lstickBox.style.display = data.has_left_stick ? "block" : "none";

            const rstickBox = document.getElementById("gp-rstick-box");
            if (rstickBox) rstickBox.style.display = data.has_right_stick ? "block" : "none";

            const dpadSec = document.getElementById("gp-dpad-section");
            if (dpadSec) dpadSec.style.display = data.has_dpad !== false ? "block" : "none";

            const motionSec = document.getElementById("gp-motion-section");
            if (motionSec) motionSec.style.display = data.has_motion ? "block" : "none";

            // Show / Hide Touchpad
            const tpSec = document.getElementById("gp-touchpad-section");
            if (tpSec) {
                tpSec.style.display = data.has_touchpad ? "block" : "none";
            }

            // Sync Touchpad Mouse Mode button state
            const tpMouseBtn = document.getElementById("btn-modal-touchpad-mouse");
            const tpMouseLbl = document.getElementById("lbl-modal-touchpad-mouse");
            if (tpMouseBtn && tpMouseLbl && data.has_touchpad) {
                const isMouseOn = (data.touchpad_mouse_enabled !== false);
                tpMouseLbl.textContent = isMouseOn ? "On" : "Off (Gaming)";
                tpMouseBtn.style.background = isMouseOn ? "rgba(37, 99, 235, 0.2)" : "rgba(239, 68, 68, 0.2)";
                tpMouseBtn.style.borderColor = isMouseOn ? "rgba(37, 99, 235, 0.4)" : "rgba(239, 68, 68, 0.4)";
                tpMouseBtn.style.color = isMouseOn ? "#60a5fa" : "#f87171";
            }



            // Show / Hide PlayStation Hardware Controls
            const psControls = document.getElementById("gp-ps-controls");
            if (psControls) {
                psControls.style.display = (data.family === "playstation" || data.is_dualsense) ? "block" : "none";
            }

            // Update Modal Hero Graphic
            const heroImg = getKenneyControllerHero(data.family, data.clean_name);
            const titleEl = document.getElementById("modal-gamepad-title");
            if (titleEl) {
                titleEl.innerHTML = `<img src="${heroImg}" style="height:26px;width:auto;max-width:42px;object-fit:contain;"> Gamepad Tester — ${data.clean_name || 'Controller'}`;
            }

            // Update D-Pad Graphical Prompts
            const dpU = document.getElementById("dpad-up");
            const dpD = document.getElementById("dpad-down");
            const dpL = document.getElementById("dpad-left");
            const dpR = document.getElementById("dpad-right");
            if (dpU) dpU.innerHTML = `<img src="${getKenneyDpadPrompt(data.family, 'up')}">`;
            if (dpD) dpD.innerHTML = `<img src="${getKenneyDpadPrompt(data.family, 'down')}">`;
            if (dpL) dpL.innerHTML = `<img src="${getKenneyDpadPrompt(data.family, 'left')}">`;
            if (dpR) dpR.innerHTML = `<img src="${getKenneyDpadPrompt(data.family, 'right')}">`;

            // Build Adaptive Button Grid with Kenney Input Icons & SVG Vector Mic
            const btnGrid = document.getElementById("gamepad-buttons-grid");
            if (btnGrid && data.button_labels) {
                btnGrid.innerHTML = data.button_labels.map(b => {
                    const isMicBtn = (b.index === 13 || (b.label && b.label.toLowerCase().includes("mic")));
                    const tooltip = b.alt ? `${b.label} (${b.alt})` : b.label;
                    let innerContent = "";
                    if (isMicBtn && (data.is_dualsense || (data.family && data.family.toLowerCase().includes("playstation")))) {
                        innerContent = `
                            <svg class="ds-mic-svg" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
                                <path class="ds-mic-led-bar" d="M19 12 L45 12 Q47.9 12 49.95 14.05 52 16.1 52 19 52 21.9 49.95 23.95 47.9 26 45 26 L19 26 Q16.1 26 14.05 23.95 12 21.9 12 19 12 16.1 14.05 14.05 16.1 12 19 12 Z" />
                                <path class="ds-mic-glyph" d="M29 34.95 Q29 34.15 29.55 33.55 L29.9 33.3 Q30.35 33 30.95 33 L33.05 33 Q33.65 33 34.15 33.3 L34.45 33.55 Q35 34.15 35 34.95 L35 40.25 29 36 29 34.95 M24.4 38.85 Q24.05 38.6 24 38.2 23.9 37.75 24.15 37.45 24.4 37.1 24.8 37.05 L25.55 37.2 39.55 47.2 39.95 47.85 39.75 48.6 39.15 49 38.4 48.85 24.4 38.85 M36.65 51.3 L36.7 51.35 37 51.55 37 52 27 52 27 50 31 50 31 48 26.95 48 26.4 47.95 Q25.95 47.8 25.55 47.45 L25.45 47.35 Q25 46.8 25 46.05 L25 43 27 44.4 27 45.05 27.25 45.7 28 46 29.25 46 33 48.7 33 50 34.85 50 36.65 51.3 M37 40 L39 40 39 43.1 37 41.7 37 40 Z" />
                            </svg>
                        `;
                    } else {
                        const iconUrl = getKenneyButtonPrompt(data.family, b.index, b.label, b.alt);
                        innerContent = iconUrl 
                            ? `<img class="gp-btn-icon" src="${iconUrl}" alt="${b.label}">`
                            : `<div class="gp-btn-text-badge">${b.label || 'PS'}</div>`;
                    }
                    const clickAttr = isMicBtn ? `onclick="toggleDualSenseMicMute()"` : "";
                    const cursorStyle = isMicBtn ? `style="cursor:pointer;"` : "";
                    const extraClass = (isMicBtn && activeDsMute) ? " mic-led-on" : "";
                    return `
                        <div class="gp-btn${extraClass}" id="gp-btn-${b.index}" title="${tooltip}" ${clickAttr} ${cursorStyle}>
                            ${innerContent}
                        </div>
                    `;
                }).join("");
            }
        }

        // 2. Continuous telemetry updates
        const state = data.state || {};
        
        // Live controller polling latency & rate update
        const latTextEl = document.getElementById("modal-gp-latency-text");
        if (latTextEl && data.latency_str) {
            latTextEl.textContent = `Polling: ${data.latency_str}`;
        }
        
        // Triggers
        const ltVal = Math.round((state.trigger_l || 0) * 100);
        const rtVal = Math.round((state.trigger_r || 0) * 100);
        const ltFill = document.getElementById("lt-fill");
        const rtFill = document.getElementById("rt-fill");
        const ltText = document.getElementById("lt-val");
        const rtText = document.getElementById("rt-val");
        if (ltFill) ltFill.style.width = ltVal + "%";
        if (rtFill) rtFill.style.width = rtVal + "%";
        if (ltText) ltText.textContent = ltVal + "%";
        if (rtText) rtText.textContent = rtVal + "%";

        // Analog Sticks
        const lx = state.left_stick_x || 0;
        const ly = state.left_stick_y || 0;
        const rx = state.right_stick_x || 0;
        const ry = state.right_stick_y || 0;
        const lsDot = document.getElementById("ls-dot");
        const rsDot = document.getElementById("rs-dot");
        const lsCoords = document.getElementById("ls-coords");
        const rsCoords = document.getElementById("rs-coords");

        if (lsDot) {
            lsDot.style.left = ((lx + 1) / 2 * 100) + "%";
            lsDot.style.top = ((ly + 1) / 2 * 100) + "%";
        }
        if (rsDot) {
            rsDot.style.left = ((rx + 1) / 2 * 100) + "%";
            rsDot.style.top = ((ry + 1) / 2 * 100) + "%";
        }
        if (lsCoords) lsCoords.textContent = `X: ${(lx >= 0 ? "+" : "") + lx.toFixed(2)}  Y: ${(ly >= 0 ? "+" : "") + ly.toFixed(2)}`;
        if (rsCoords) rsCoords.textContent = `X: ${(rx >= 0 ? "+" : "") + rx.toFixed(2)}  Y: ${(ry >= 0 ? "+" : "") + ry.toFixed(2)}`;

        // D-Pad
        const dx = state.dpad_x || 0;
        const dy = state.dpad_y || 0;
        const dpL = document.getElementById("dpad-left");
        const dpR = document.getElementById("dpad-right");
        const dpU = document.getElementById("dpad-up");
        const dpD = document.getElementById("dpad-down");
        if (dpL) dpL.classList.toggle("active", dx < -0.5);
        if (dpR) dpR.classList.toggle("active", dx > 0.5);
        if (dpU) dpU.classList.toggle("active", dy < -0.5);
        if (dpD) dpD.classList.toggle("active", dy > 0.5);

        // Buttons & Hardware LED sync
        const btns = state.buttons || {};
        for (const k in btns) {
            const el = document.getElementById("gp-btn-" + k);
            if (el) {
                el.classList.toggle("active", !!btns[k]);
            }
        }
        // Physical Mic Mute button edge detection -> toggles hardware LED
        const isMicPhysDown = !!btns["13"];
        if (isMicPhysDown && !window._lastMicPhysDown) {
            window._lastMicPhysDown = true;
            toggleDualSenseMicMute();
        } else if (!isMicPhysDown) {
            window._lastMicPhysDown = false;
        }

        // Real-time Mic Mute Button LED Amber illumination
        updateMicMuteVisuals();


        // Motion Sensors updates
        if (data.has_motion && state.motion) {
            for (let i = 0; i < 6; i++) {
                const mVal = state.motion[i] != null ? state.motion[i] : 0.0;
                const fillEl = document.getElementById("motion-fill-" + i);
                const valEl = document.getElementById("motion-val-" + i);
                if (fillEl) fillEl.style.width = Math.min(100, Math.max(0, ((mVal + 1.0) / 2.0) * 100)) + "%";
                if (valEl) valEl.textContent = (mVal >= 0 ? "+" : "") + mVal.toFixed(2);
            }
        }

        // Multi-Touch Touchpad updates
        if (data.has_touchpad) {
            const tpDot1 = document.getElementById("tp-dot-1");
            const tpDot2 = document.getElementById("tp-dot-2");
            const tpLabel = document.getElementById("tp-coords-label");
            const tpIdle = document.getElementById("tp-idle-text");
            const tpBox = document.getElementById("tp-box");
            const tpZoneL = document.getElementById("tp-zone-left");
            const tpZoneR = document.getElementById("tp-zone-right");

            const multi = state.touchpad_multi || {};
            const f1 = multi.f1 || { x: state.touchpad_x || 0.5, y: state.touchpad_y || 0.5, active: !!state.touchpad_active };
            const f2 = multi.f2 || { x: 0.5, y: 0.5, active: false };
            const isClick = !!state.touchpad_click || !!multi.click;
            const count = multi.finger_count != null ? multi.finger_count : (f1.active ? (f2.active ? 2 : 1) : 0);
            const zone = multi.zone || (f1.active ? (f1.x < 0.45 ? "Left" : (f1.x > 0.55 ? "Right" : "Center")) : "None");

            // Finger 1 Visualizer Dot
            if (tpDot1) {
                if (f1.active) {
                    tpDot1.style.display = "block";
                    tpDot1.style.left = (f1.x * 100) + "%";
                    tpDot1.style.top = (f1.y * 100) + "%";
                    tpDot1.style.opacity = "1.0";
                    tpDot1.style.transform = "translate(-50%, -50%) scale(1.2)";
                } else {
                    tpDot1.style.display = "none";
                }
            }

            // Finger 2 Visualizer Dot
            if (tpDot2) {
                if (f2.active) {
                    tpDot2.style.display = "block";
                    tpDot2.style.left = (f2.x * 100) + "%";
                    tpDot2.style.top = (f2.y * 100) + "%";
                    tpDot2.style.opacity = "1.0";
                    tpDot2.style.transform = "translate(-50%, -50%) scale(1.2)";
                } else {
                    tpDot2.style.display = "none";
                }
            }

            // Zone Background Highlights
            if (tpZoneL) {
                tpZoneL.style.background = (f1.active && zone === "Left") ? (isClick ? "rgba(16, 185, 129, 0.2)" : "rgba(37, 99, 235, 0.15)") : "transparent";
            }
            if (tpZoneR) {
                tpZoneR.style.background = (f1.active && zone === "Right") ? (isClick ? "rgba(16, 185, 129, 0.2)" : "rgba(236, 72, 153, 0.15)") : "transparent";
            }

            // Box Styling
            if (tpBox) {
                tpBox.style.borderColor = isClick ? "var(--success-color)" : (count > 0 ? "var(--accent-color)" : "var(--border-color)");
                tpBox.style.background = isClick ? "rgba(16, 185, 129, 0.25)" : (count === 2 ? "rgba(168, 85, 247, 0.18)" : (count === 1 ? "rgba(59, 130, 246, 0.12)" : "rgba(0,0,0,0.4)"));
            }

            // Dynamic Informative Multi-Touch Coordinates Label
            if (tpLabel) {
                if (count === 2) {
                    tpLabel.textContent = `2 Fingers (F1: ${f1.x.toFixed(2)}, ${f1.y.toFixed(2)} | F2: ${f2.x.toFixed(2)}, ${f2.y.toFixed(2)})${isClick ? " — Clicked" : ""}`;
                    tpLabel.style.color = isClick ? "var(--success-color)" : "#c084fc";
                } else if (count === 1) {
                    if (isClick) {
                        tpLabel.textContent = `Click (${zone} Zone) — X: ${f1.x.toFixed(2)}, Y: ${f1.y.toFixed(2)}`;
                        tpLabel.style.color = "var(--success-color)";
                    } else {
                        tpLabel.textContent = `1 Finger (${zone} Zone) — X: ${f1.x.toFixed(2)}, Y: ${f1.y.toFixed(2)}`;
                        tpLabel.style.color = "var(--accent-color)";
                    }
                } else if (isClick) {
                    tpLabel.textContent = `Touchpad Clicked`;
                    tpLabel.style.color = "var(--success-color)";
                } else {
                    tpLabel.textContent = `Idle`;
                    tpLabel.style.color = "var(--text-muted)";
                }
            }

            if (tpIdle) tpIdle.style.opacity = count > 0 ? "0.15" : "0.5";
        }
    } catch (e) {}
}

/* Adaptive Triggers Controls */
function setTriggerTarget(target) {
    activeTriggerTarget = target;
    const bBoth = document.getElementById("ds-trig-target-both");
    const bL2 = document.getElementById("ds-trig-target-l2");
    const bR2 = document.getElementById("ds-trig-target-r2");
    if (bBoth) bBoth.classList.toggle("active", target === "both");
    if (bL2) bL2.classList.toggle("active", target === "l2");
    if (bR2) bR2.classList.toggle("active", target === "r2");
    applyTriggerEffect();
}

function setDualSenseTriggerMode(mode) {
    activeTriggerMode = mode;
    const modes = ["off", "gun", "machine_gun", "bow", "abs", "heavy"];
    modes.forEach(m => {
        const id = m === "machine_gun" ? "ds-trig-mg" : ("ds-trig-" + m);
        const btn = document.getElementById(id);
        if (btn) btn.classList.toggle("active", mode === m);
    });

    const descEl = document.getElementById("ds-trig-desc");
    if (descEl && TRIGGER_DESCRIPTIONS[mode]) {
        descEl.textContent = TRIGGER_DESCRIPTIONS[mode];
        descEl.style.color = mode === "off" ? "var(--text-muted)" : "var(--accent-color)";
    }

    const slidersEl = document.getElementById("ds-trig-sliders");
    if (slidersEl) slidersEl.style.display = mode === "off" ? "none" : "grid";

    applyTriggerEffect();
    if (mode !== "off") {
        showToast(`Adaptive trigger set to ${mode.toUpperCase()}.`);
    }
}

function onTriggerParamChange() {
    const force = parseInt(document.getElementById("ds-trig-force")?.value || 255);
    const pos = parseInt(document.getElementById("ds-trig-pos")?.value || 80);
    const freq = parseInt(document.getElementById("ds-trig-freq")?.value || 15);
    const fVal = document.getElementById("ds-trig-force-val");
    const pVal = document.getElementById("ds-trig-pos-val");
    const frVal = document.getElementById("ds-trig-freq-val");
    if (fVal) fVal.textContent = Math.round((force / 255) * 100) + "%";
    if (pVal) pVal.textContent = Math.round((pos / 255) * 100) + "%";
    if (frVal) frVal.textContent = freq + " Hz";
    applyTriggerEffect();
}

async function applyTriggerEffect() {
    if (!activeGamepadPort) return;
    const force = parseInt(document.getElementById("ds-trig-force")?.value || 255);
    const pos = parseInt(document.getElementById("ds-trig-pos")?.value || 80);
    const freq = parseInt(document.getElementById("ds-trig-freq")?.value || 15);
    try {
        await API.sendGamepadControl({
            port: activeGamepadPort,
            action: "set_trigger",
            trigger_mode: activeTriggerMode,
            trigger_target: activeTriggerTarget,
            force,
            start_pos: pos,
            end_pos: 224,
            freq,
            r: activeDsColor.r,
            g: activeDsColor.g,
            b: activeDsColor.b,
            player: activeDsPlayer,
            mic_mute: activeDsMute ? 1 : 0
        });
    } catch (e) {
        console.error("Error applying trigger effect:", e);
    }
}

/* DualSense RGB & Haptic Functions */
async function setDualSenseColor(hex) {
    if (!activeGamepadPort) return;
    const r = parseInt(hex.slice(1, 3), 16) || 0;
    const g = parseInt(hex.slice(3, 5), 16) || 0;
    const b = parseInt(hex.slice(5, 7), 16) || 0;
    activeDsColor = { r, g, b };
    const cp = document.getElementById("ds-color-picker");
    if (cp) cp.value = hex;
    try {
        await API.sendGamepadControl({
            port: activeGamepadPort,
            action: "set_led",
            r, g, b,
            player: activeDsPlayer,
            mic_mute: activeDsMute ? 1 : 0,
            trigger_mode: activeTriggerMode,
            trigger_target: activeTriggerTarget
        });
    } catch (e) {}
}

async function setDualSensePlayer(p) {
    if (!activeGamepadPort) return;
    activeDsPlayer = p;
    for (let i = 1; i <= 5; i++) {
        const btn = document.getElementById("ds-p" + i);
        if (btn) btn.classList.toggle("active", i === p);
    }
    try {
        await API.sendGamepadControl({
            port: activeGamepadPort,
            action: "set_player",
            r: activeDsColor.r,
            g: activeDsColor.g,
            b: activeDsColor.b,
            player: p,
            mic_mute: activeDsMute ? 1 : 0,
            trigger_mode: activeTriggerMode,
            trigger_target: activeTriggerTarget
        });
    } catch (e) {}
}

function updateMicMuteVisuals() {
    const micGridBtn = document.getElementById("gp-btn-13") || Array.from(document.querySelectorAll(".gp-btn")).find(el => el.title && el.title.includes("Mic"));
    if (micGridBtn) {
        micGridBtn.classList.toggle("mic-led-on", !!activeDsMute);
        const ledBar = micGridBtn.querySelector(".ds-mic-led-bar");
        const micGlyph = micGridBtn.querySelector(".ds-mic-glyph");
        if (ledBar) {
            ledBar.style.fill = activeDsMute ? "#f59e0b" : "#475569";
            ledBar.style.opacity = activeDsMute ? "1" : "0.5";
            ledBar.style.filter = activeDsMute ? "drop-shadow(0 0 6px #f59e0b)" : "none";
        }
        if (micGlyph) {
            micGlyph.style.fill = "#cbd5e1";
            micGlyph.style.filter = "none";
        }
    }
}

async function toggleDualSenseMicMute() {
    if (!activeGamepadPort) return;
    activeDsMute = !activeDsMute;
    updateMicMuteVisuals();
    try {
        await API.sendGamepadControl({
            port: activeGamepadPort,
            action: "set_mic_led",
            r: activeDsColor.r,
            g: activeDsColor.g,
            b: activeDsColor.b,
            player: activeDsPlayer,
            mic_mute: activeDsMute ? 1 : 0,
            trigger_mode: activeTriggerMode,
            trigger_target: activeTriggerTarget
        });
    } catch (e) {}
}

async function toggleModalDeviceAudio() {
    if (!activeGamepadPort) return;
    const attached = currentStatus.attached_devices || [];
    const dev = attached.find(d => String(d.port) === String(activeGamepadPort));
    const currentlyEnabled = dev ? dev.audio_enabled !== false : true;
    await toggleDeviceAudio(activeGamepadPort, !currentlyEnabled);
    setTimeout(updateModalAudioState, 300);
}

function updateModalAudioState() {
    const btn = document.getElementById("modal-audio-toggle-btn");
    if (!btn) return;
    if (!activeGamepadPort) return;
    const attached = currentStatus.attached_devices || [];
    const dev = attached.find(d => String(d.port) === String(activeGamepadPort));
    const icon = document.getElementById("modal-audio-icon");
    const label = document.getElementById("modal-audio-label");
    if (!dev || !dev.has_audio) {
        btn.style.display = "none";
        return;
    }
    btn.style.display = "inline-flex";
    const isMuted = (dev.audio_enabled === false);
    if (isMuted) {
        btn.className = "btn btn-success";
        icon.src = "/icons/audio-volume-muted.png";
        label.textContent = "Audio: Off";
        btn.title = "Controller audio is disabled / muted. Click to enable.";
    } else {
        btn.className = "btn btn-secondary";
        icon.src = "/icons/audio-card.png";
        label.textContent = "Audio: On";
        btn.title = "Controller audio is enabled. Click to disable / mute.";
    }
}

async function testDualSenseSound() {
    if (!activeGamepadPort) return;
    try {
        const data = await API.sendGamepadControl({ port: activeGamepadPort, action: "sound_test" });
        if (data.status === "ok") {
            showToast("Played test audio on controller speaker.");
        }
    } catch (e) {}
}

async function testDualSenseRumble() {
    if (!activeGamepadPort) return;
    try {
        await API.sendGamepadControl({
            port: activeGamepadPort,
            action: "rumble_pulse",
            r: activeDsColor.r,
            g: activeDsColor.g,
            b: activeDsColor.b,
            player: activeDsPlayer,
            mic_mute: activeDsMute ? 1 : 0
        });
    } catch (e) {}
}


async function toggleModalTouchpadMouse() {
    if (!activeGamepadPort) return;
    try {
        const isCurrentOn = (activeGamepadConfig && activeGamepadConfig.touchpad_mouse_enabled !== false);
        const res = await API.toggleTouchpadMouse(activeGamepadPort, !isCurrentOn);
        if (res && res.status === "ok") {
            if (activeGamepadConfig) activeGamepadConfig.touchpad_mouse_enabled = res.touchpad_mouse_enabled;
            const tpMouseBtn = document.getElementById("btn-modal-touchpad-mouse");
            const tpMouseLbl = document.getElementById("lbl-modal-touchpad-mouse");
            if (tpMouseBtn && tpMouseLbl) {
                const isMouseOn = res.touchpad_mouse_enabled;
                tpMouseLbl.textContent = isMouseOn ? "On" : "Off (Gaming)";
                tpMouseBtn.style.background = isMouseOn ? "rgba(37, 99, 235, 0.2)" : "rgba(239, 68, 68, 0.2)";
                tpMouseBtn.style.borderColor = isMouseOn ? "rgba(37, 99, 235, 0.4)" : "rgba(239, 68, 68, 0.4)";
                tpMouseBtn.style.color = isMouseOn ? "#60a5fa" : "#f87171";
            }
        }
    } catch (e) {
        console.error("Error toggling modal touchpad mouse:", e);
    }
}
window.toggleModalTouchpadMouse = toggleModalTouchpadMouse;
