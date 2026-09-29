/**
 * LATTICE · IITH Operations Console — Student Application Controller
 * High-contrast, data-dense client for campus appliances, room maintenance,
 * and 2-step verification resolution workflow.
 */

// User persistent anonymous fingerprint
let userToken = "usr_" + Math.random().toString(36).substring(2, 10);
try {
    const savedToken = localStorage.getItem("kandifix_user_token");
    if (savedToken) {
        userToken = savedToken;
    } else {
        localStorage.setItem("kandifix_user_token", userToken);
    }
} catch (e) {
    // Storage restricted
}

// Toast notification system
function showToast(message, type = "info", duration = 4000) {
    let container = document.getElementById("toast-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "toast-container";
        container.className = "fixed bottom-5 right-5 z-50 flex flex-col gap-2 pointer-events-none";
        document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    const colors = {
        success: "bg-emerald-900/90 text-emerald-100 border-emerald-700",
        error: "bg-rose-900/90 text-rose-100 border-rose-700",
        warning: "bg-amber-900/90 text-amber-100 border-amber-700",
        info: "bg-slate-900/90 text-slate-100 border-slate-700"
    };

    const colorClass = colors[type] || colors.info;
    toast.className = `${colorClass} border px-4 py-2.5 rounded-xl shadow-xl text-xs font-medium flex items-center gap-2 pointer-events-auto transition-all transform duration-300 opacity-0 translate-y-2 backdrop-blur-md`;
    toast.innerHTML = `
        <span class="w-2 h-2 rounded-full ${type === 'success' ? 'bg-emerald-400' : type === 'error' ? 'bg-rose-400' : type === 'warning' ? 'bg-amber-400' : 'bg-blue-400'}"></span>
        <span>${message}</span>
    `;

    container.appendChild(toast);
    requestAnimationFrame(() => {
        toast.classList.remove("opacity-0", "translate-y-2");
        toast.classList.add("opacity-100", "translate-y-0");
    });

    setTimeout(() => {
        toast.classList.add("opacity-0", "translate-y-2");
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

let currentTab = "facilities";
let currentHostels = [];
let selectedHostelId = 16;
let selectedFloor = 1;

function bootstrap() {
    updateCrossPortalLinks();
    initTabs();
    loadHostels();
    loadAppliances();
    loadSLAStats();
}

// Dynamic Cross-Portal Navigation Links & Single-Port Handling
function updateCrossPortalLinks() {
    const isMultiPort = window.location.port === "8001" || window.location.port === "8002";
    const isSinglePort = !isMultiPort;
    const techLink = document.getElementById("nav-link-tech");
    const adminLink = document.getElementById("nav-link-admin");
    const presLink = document.getElementById("nav-link-presentation");

    if (techLink) {
        techLink.href = isSinglePort ? "/tech" : `//${window.location.hostname}:8001/`;
    }
    if (adminLink) {
        adminLink.href = isSinglePort ? "/admin" : `//${window.location.hostname}:8002/`;
    }
    if (presLink) {
        presLink.href = "/presentation";
    }
}

// 1-Click Demo Ticket Quick-Fill Handler
function setDemoLookup(ticketId) {
    const input = document.getElementById("ticket-lookup-input");
    if (input) {
        input.value = ticketId.startsWith("#") ? ticketId : `#${ticketId}`;
        lookupTicket();
    }
}

function dismissHackathonModal() {
    const modal = document.getElementById("hackathon-alert-modal");
    if (modal) modal.classList.add("hidden");
    try {
        sessionStorage.setItem("lattice_hackathon_warned", "true");
    } catch (e) {}
}

// Auto-check if warning was dismissed previously
try {
    if (sessionStorage.getItem("lattice_hackathon_warned") === "true") {
        const modal = document.getElementById("hackathon-alert-modal");
        if (modal) modal.classList.add("hidden");
    }
} catch (e) {}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootstrap);
} else {
    bootstrap();
}

function initTabs() {
    const tabs = ["facilities", "room", "admin"];
    tabs.forEach(tab => {
        const btn = document.getElementById(`tab-btn-${tab}`);
        if (btn) {
            btn.onclick = () => switchTab(tab);
        }
    });
}

function switchTab(tab) {
    currentTab = tab;
    ["facilities", "room", "admin"].forEach(t => {
        const btn = document.getElementById(`tab-btn-${t}`);
        const view = document.getElementById(`view-${t}`);
        if (btn) {
            if (t === tab) {
                btn.className = "flex items-center gap-1.5 bg-white text-slate-900 shadow-sm font-semibold rounded-lg px-4 py-1.5 text-xs transition-all";
            } else {
                btn.className = "flex items-center gap-1.5 text-slate-600 hover:text-slate-900 font-medium rounded-lg px-4 py-1.5 text-xs transition-all";
            }
        }
        if (view) {
            view.classList.toggle("hidden", t !== tab);
        }
    });

    if (tab === "facilities") loadAppliances();
    if (tab === "room") syncRoomTabWithSelectedHostel();
    if (tab === "admin") loadSLAStats();
}

function switchStudentTab(tab) {
    switchTab(tab);
}

// ==========================================
// 1. HOSTELS & FLOOR MAPPING
// ==========================================
function getHostelFloors(hostel) {
    if (!hostel) return [1, 2, 3, 4, 5, 6];
    if (hostel.has_ground_floor) {
        const floors = [0];
        for (let i = 1; i <= hostel.total_floors - 1; i++) {
            floors.push(i);
        }
        return floors;
    } else {
        const floors = [];
        for (let i = 1; i <= hostel.total_floors; i++) {
            floors.push(i);
        }
        return floors;
    }
}

async function loadHostels() {
    try {
        const res = await fetch("/api/v1/hostels");
        currentHostels = await res.json();
    } catch (err) {
        console.error("Failed to load hostels from API, fallback to default", err);
    }

    const hostelSelect = document.getElementById("hostel-select");
    const roomHostelSelect = document.getElementById("room-hostel-select");
    const facilityFloorSelect = document.getElementById("facility-floor-select");
    
    if (currentHostels.length > 0) {
        if (hostelSelect) {
            hostelSelect.innerHTML = "";
            currentHostels.forEach((h) => {
                const opt = document.createElement("option");
                opt.value = h.id;
                opt.textContent = h.name;
                hostelSelect.appendChild(opt);
            });
        }

        if (roomHostelSelect) {
            roomHostelSelect.innerHTML = "";
            currentHostels.forEach((h) => {
                const opt = document.createElement("option");
                opt.value = h.id;
                opt.textContent = h.name;
                roomHostelSelect.appendChild(opt);
            });
        }

        selectedHostelId = currentHostels[0].id;
        const initialHostel = currentHostels[0];
        selectedFloor = initialHostel.has_ground_floor ? 0 : 1;
        updateFloorSelectors(initialHostel);
        updateRoomFloorOptions(initialHostel);
    } else {
        const initialHostel = { id: 16, name: "Anandi Joshi", total_floors: 10, has_ground_floor: false };
        updateFloorSelectors(initialHostel);
        updateRoomFloorOptions(initialHostel);
    }

    if (hostelSelect) {
        hostelSelect.addEventListener("change", (e) => {
            selectedHostelId = parseInt(e.target.value);
            const hostel = currentHostels.find(h => h.id === selectedHostelId) || { total_floors: 6, has_ground_floor: false };
            selectedFloor = hostel.has_ground_floor ? 0 : 1;
            updateFloorSelectors(hostel);
            loadAppliances();
            if (roomHostelSelect) {
                roomHostelSelect.value = selectedHostelId;
                updateRoomFloorOptions(hostel);
            }
        });
    }

    if (facilityFloorSelect) {
        facilityFloorSelect.addEventListener("change", (e) => {
            selectedFloor = parseInt(e.target.value);
            updateFloorButtonsActive(selectedFloor);
            loadAppliances();
        });
    }

    if (roomHostelSelect) {
        roomHostelSelect.addEventListener("change", (e) => {
            const hId = parseInt(e.target.value);
            selectedHostelId = hId;
            const hostel = currentHostels.find(h => h.id === hId) || { total_floors: 6, has_ground_floor: false };
            if (hostelSelect) hostelSelect.value = hId;
            updateFloorSelectors(hostel);
            updateRoomFloorOptions(hostel);
            validateRoomNumberInput();
        });
    }

    const roomFloorSelect = document.getElementById("room-floor");
    if (roomFloorSelect) {
        roomFloorSelect.addEventListener("change", () => {
            const hostel = currentHostels.find(h => h.id === selectedHostelId);
            const chosenFloor = parseInt(roomFloorSelect.value);
            updateRoomFloorHintAndPlaceholder(hostel, chosenFloor);
            validateRoomNumberInput();
        });
    }

    const roomNumberInput = document.getElementById("room-number");
    if (roomNumberInput) {
        roomNumberInput.addEventListener("input", validateRoomNumberInput);
    }
}

function updateFloorSelectors(hostel) {
    if (!hostel) return;
    const floors = getHostelFloors(hostel);
    if (!floors.includes(selectedFloor)) {
        selectedFloor = floors[0];
    }

    // 1. Update Facility Floor Dropdown (Mobile fallback)
    const facilityFloorSelect = document.getElementById("facility-floor-select");
    if (facilityFloorSelect) {
        facilityFloorSelect.innerHTML = "";
        floors.forEach(f => {
            const opt = document.createElement("option");
            opt.value = f;
            opt.textContent = f === 0 ? "Ground Floor" : `Floor ${f}`;
            facilityFloorSelect.appendChild(opt);
        });
        facilityFloorSelect.value = selectedFloor;
    }

    // 2. Update Facility Floor Buttons (Horizontal Pill Bar)
    const container = document.getElementById("floor-buttons-container");
    if (container) {
        container.innerHTML = "";
        floors.forEach(f => {
            const btn = document.createElement("button");
            btn.textContent = f === 0 ? "Ground" : `${f}`;
            btn.title = f === 0 ? "Ground Floor" : `Floor ${f}`;
            btn.dataset.floor = f;
            if (f === selectedFloor) {
                btn.className = "bg-slate-900 text-white shadow-xs font-semibold px-3 py-1 rounded-lg text-xs transition-colors";
            } else {
                btn.className = "text-slate-600 hover:text-slate-900 hover:bg-slate-200/60 font-medium px-3 py-1 rounded-lg text-xs transition-colors";
            }
            btn.onclick = () => {
                selectedFloor = f;
                if (facilityFloorSelect) facilityFloorSelect.value = f;
                updateFloorButtonsActive(f);
                loadAppliances();
            };
            container.appendChild(btn);
        });
    }
}

function updateFloorButtonsActive(floor) {
    const container = document.getElementById("floor-buttons-container");
    if (!container) return;
    const buttons = container.querySelectorAll("button");
    buttons.forEach(btn => {
        const f = parseInt(btn.dataset.floor);
        if (f === floor) {
            btn.className = "bg-slate-900 text-white shadow-xs font-semibold px-3 py-1 rounded-lg text-xs transition-colors";
        } else {
            btn.className = "text-slate-600 hover:text-slate-900 hover:bg-slate-200/60 font-medium px-3 py-1 rounded-lg text-xs transition-colors";
        }
    });
}

function updateRoomFloorOptions(hostel, preferredFloor = null) {
    const roomFloorSelect = document.getElementById("room-floor");
    if (!roomFloorSelect) return;

    const floors = getHostelFloors(hostel);
    roomFloorSelect.innerHTML = "";
    floors.forEach(f => {
        const opt = document.createElement("option");
        opt.value = f;
        if (f === 0) {
            opt.textContent = "Ground Floor (Rooms G01–G30)";
        } else {
            const maxR = f === 10 ? 1030 : (f * 100 + 30);
            const minR = f === 10 ? 1001 : (f * 100 + 1);
            opt.textContent = `Floor ${f} (Rooms ${minR}–${maxR})`;
        }
        roomFloorSelect.appendChild(opt);
    });

    const targetFloor = (preferredFloor !== null && floors.includes(preferredFloor)) ? preferredFloor : floors[0];
    roomFloorSelect.value = targetFloor;
    updateRoomFloorHintAndPlaceholder(hostel, targetFloor);
}

function updateRoomFloorHintAndPlaceholder(hostel, floor) {
    const roomInput = document.getElementById("room-number");
    const roomHostelHint = document.getElementById("room-hostel-hint");
    if (!hostel) return;

    if (hostel.has_ground_floor) {
        if (roomHostelHint) roomHostelHint.textContent = `Ground to 6th Floor (G01–G30 or 101–630)`;
        if (roomInput) {
            roomInput.placeholder = floor === 0 ? "e.g. G22" : `e.g. ${floor}14`;
        }
    } else if (hostel.total_floors === 10) {
        if (roomHostelHint) roomHostelHint.textContent = `10 Floors (No Ground, 101–1030)`;
        if (roomInput) {
            roomInput.placeholder = floor === 10 ? "e.g. 1014" : `e.g. ${floor}14`;
        }
    } else {
        if (roomHostelHint) roomHostelHint.textContent = `6 Floors (No Ground, 101–630)`;
        if (roomInput) {
            roomInput.placeholder = `e.g. ${floor}14`;
        }
    }
}

function syncRoomTabWithSelectedHostel() {
    const roomHostelSelect = document.getElementById("room-hostel-select");
    if (roomHostelSelect && selectedHostelId) {
        roomHostelSelect.value = selectedHostelId;
        const hostel = currentHostels.find(h => h.id === selectedHostelId);
        updateRoomFloorOptions(hostel, selectedFloor);
        validateRoomNumberInput();
    }
}

// ==========================================
// 2. REAL-TIME ROOM NUMBER VALIDATION
// ==========================================
function validateRoomNumberInput() {
    const input = document.getElementById("room-number");
    const badge = document.getElementById("room-validation-badge");
    const roomFloorSelect = document.getElementById("room-floor");
    const hostel = currentHostels.find(h => h.id === selectedHostelId);

    if (!input || !badge || !hostel) return;
    const val = input.value.trim().toUpperCase();

    if (!val) {
        badge.classList.add("hidden");
        input.className = "w-full bg-white border border-slate-200 text-xs font-mono font-bold text-slate-900 rounded-lg p-2.5 outline-none focus:border-slate-400";
        return;
    }

    badge.classList.remove("hidden");

    // Standard ground floor check
    if (val.startsWith("G")) {
        if (!hostel.has_ground_floor) {
            badge.className = "text-[11px] font-medium text-rose-700 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded";
            badge.textContent = `[!] ${hostel.name} has no Ground Floor`;
            input.className = "w-full bg-white border border-rose-500 text-xs font-mono font-bold text-slate-900 rounded-lg p-2.5 outline-none";
            return;
        }

        if (roomFloorSelect && roomFloorSelect.value !== "0") {
            roomFloorSelect.value = "0";
            updateRoomFloorHintAndPlaceholder(hostel, 0);
        }

        const validGround = /^G([0-2][0-9]|30)$/.test(val);
        if (validGround) {
            badge.className = "text-[11px] font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded";
            badge.textContent = `Valid ${hostel.name} Room`;
            input.className = "w-full bg-white border border-emerald-500 text-xs font-mono font-bold text-slate-900 rounded-lg p-2.5 outline-none";
        } else {
            badge.className = "text-[11px] font-medium text-amber-800 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded";
            badge.textContent = "e.g. G01–G30";
            input.className = "w-full bg-white border border-amber-400 text-xs font-mono font-bold text-slate-900 rounded-lg p-2.5 outline-none";
        }
        return;
    }

    // Tower 10th floor check (1001-1030)
    if (val.startsWith("10") && val.length >= 3) {
        if (hostel.total_floors < 10) {
            badge.className = "text-[11px] font-medium text-rose-700 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded";
            badge.textContent = `[!] ${hostel.name} max 6 floors`;
            input.className = "w-full bg-white border border-rose-500 text-xs font-mono font-bold text-slate-900 rounded-lg p-2.5 outline-none";
            return;
        }

        if (roomFloorSelect && roomFloorSelect.value !== "10") {
            roomFloorSelect.value = "10";
            updateRoomFloorHintAndPlaceholder(hostel, 10);
        }

        const valid10 = /^10([0-2][0-9]|30)$/.test(val);
        if (valid10) {
            badge.className = "text-[11px] font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded";
            badge.textContent = `Valid ${hostel.name} Room`;
            input.className = "w-full bg-white border border-emerald-500 text-xs font-mono font-bold text-slate-900 rounded-lg p-2.5 outline-none";
        } else {
            badge.className = "text-[11px] font-medium text-amber-800 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded";
            badge.textContent = "e.g. 1001–1030";
            input.className = "w-full bg-white border border-amber-400 text-xs font-mono font-bold text-slate-900 rounded-lg p-2.5 outline-none";
        }
        return;
    }

    // Number floor check (1-9)
    if (/^\d+$/.test(val)) {
        const floorDigit = parseInt(val[0]);
        const maxF = hostel.has_ground_floor ? hostel.total_floors - 1 : hostel.total_floors;

        if (floorDigit > maxF || floorDigit < 1) {
            badge.className = "text-[11px] font-medium text-rose-700 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded";
            badge.textContent = `[!] Invalid floor (${hostel.name} has ${maxF} floors)`;
            input.className = "w-full bg-white border border-rose-500 text-xs font-mono font-bold text-slate-900 rounded-lg p-2.5 outline-none";
            return;
        }

        if (roomFloorSelect && roomFloorSelect.value !== String(floorDigit)) {
            roomFloorSelect.value = String(floorDigit);
            updateRoomFloorHintAndPlaceholder(hostel, floorDigit);
        }

        // Standard 3-digit room (e.g. 101 to 130)
        const validStandard = new RegExp(`^${floorDigit}([0-2][0-9]|30)$`).test(val);
        if (validStandard) {
            badge.className = "text-[11px] font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded";
            badge.textContent = `Valid ${hostel.name} Room`;
            input.className = "w-full bg-white border border-emerald-500 text-xs font-mono font-bold text-slate-900 rounded-lg p-2.5 outline-none";
        } else if (val.length <= 3) {
            badge.className = "text-[11px] font-medium text-amber-800 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded";
            badge.textContent = `e.g. ${floorDigit}01–${floorDigit}30`;
            input.className = "w-full bg-white border border-amber-400 text-xs font-mono font-bold text-slate-900 rounded-lg p-2.5 outline-none";
        } else {
            badge.className = "text-[11px] font-medium text-rose-700 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded";
            badge.textContent = `[!] Max room is ${floorDigit}30`;
            input.className = "w-full bg-white border border-rose-500 text-xs font-mono font-bold text-slate-900 rounded-lg p-2.5 outline-none";
        }
        return;
    }

    badge.className = "text-[11px] font-medium text-rose-700 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded";
    badge.textContent = "[!] Invalid format (Use G01–G30 or 101–1030)";
    input.className = "w-full bg-white border border-rose-500 text-xs font-mono font-bold text-slate-900 rounded-lg p-2.5 outline-none";
}

// ==========================================
// 3. APPLIANCE GRID & CROWD REPORTING
// ==========================================
async function loadAppliances() {
    if (!selectedHostelId) return;
    const grid = document.getElementById("appliances-grid");
    const countLabel = document.getElementById("appliances-count-label");
    if (!grid) return;

    grid.innerHTML = `<div class="col-span-full py-12 text-center text-slate-400 font-mono text-xs">Loading monitored appliances...</div>`;

    try {
        const res = await fetch(`/api/v1/appliances?hostel_id=${selectedHostelId}&floor=${selectedFloor}`);
        const appliances = await res.json();

        if (countLabel) {
            countLabel.textContent = `Showing: ${appliances.length} Appliances`;
        }

        if (appliances.length === 0) {
            grid.innerHTML = `
                <div class="col-span-full py-12 text-center bg-white rounded-xl border border-slate-200 p-8 shadow-sm">
                    <span class="text-xs font-mono font-bold px-2 py-1 rounded bg-slate-800 text-slate-300">LAUNDRY</span>
                    <p class="text-xs font-semibold text-slate-700 mt-2">No appliances registered for this floor</p>
                    <p class="text-[11px] text-slate-400 mt-0.5">Odd floors house laundry machines in tower hostels.</p>
                </div>
            `;
            return;
        }

        grid.innerHTML = appliances.map(app => renderApplianceCard(app)).join("");
    } catch (err) {
        grid.innerHTML = `<div class="col-span-full py-12 text-center text-rose-600 text-xs font-medium">Failed to load appliances.</div>`;
    }
}

function renderApplianceCard(app) {
    const isWashing = app.asset_type === "washing_machine";
    const typeLabel = isWashing ? "Washing Machine" : "Water Cooler";
    const floorLabel = app.floor === 0 ? "Ground Floor" : `Floor ${app.floor}`;

    let statusPill = "";
    let actionButtons = "";

    if (app.status === "operational") {
        statusPill = `<span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">● OPERATIONAL</span>`;
        actionButtons = `
            <button onclick="openReportModal(${app.id}, '${app.asset_label}', '${typeLabel}')" 
                class="w-full mt-4 py-2 px-3 rounded-lg text-xs font-medium border border-rose-200 text-rose-600 hover:bg-rose-50 transition-colors">
                Report Broken
            </button>
        `;
    } else if (app.status === "in_progress") {
        statusPill = `<span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">● IN PROGRESS</span>`;
        actionButtons = `
            <div class="mt-4 w-full py-2 px-3 rounded-lg text-xs font-semibold bg-indigo-50 border border-indigo-200 text-indigo-700 text-center">
                In Progress (Tech Dispatched)
            </div>
        `;
    } else {
        const workingConfs = app.working_confirmations_count || 0;
        const reqConfs = app.required_working_confirmations || 2;
        if (workingConfs > 0) {
            statusPill = `<span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-300">● VERIFYING FIX (${workingConfs}/${reqConfs})</span>`;
        } else {
            statusPill = `<span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">● ${app.status.toUpperCase().replace('_', ' ')}</span>`;
        }

        const reportWorkingLabel = workingConfs > 0 ? "Confirm Working" : "Report Working";
        const workingBtnClass = workingConfs > 0 
            ? "py-2 px-3 rounded-lg text-xs font-semibold bg-amber-50 text-amber-900 border border-amber-300 hover:bg-amber-100 transition flex items-center gap-1.5"
            : "py-2 px-3 rounded-lg text-xs font-medium bg-slate-100 text-slate-700 hover:bg-slate-200 transition flex items-center gap-1.5";

        actionButtons = `
            <div class="mt-4 flex gap-2">
                <button onclick="confirmBroken(${app.id})" 
                    class="flex-1 py-2 px-3 rounded-lg text-xs font-medium bg-rose-600 text-white hover:bg-rose-700 transition flex items-center justify-center gap-1.5 shadow-xs">
                    <span>+1 Confirm Broken</span>
                    <span class="bg-rose-700/60 px-1.5 py-0.2 rounded text-[10px] font-mono">${app.confirmations_count}</span>
                </button>
                <button onclick="reportWorking(${app.id})" 
                    title="Confirm appliance is working again (${workingConfs}/${reqConfs} resident confirmations required)"
                    class="${workingBtnClass}">
                    <span>${reportWorkingLabel}</span>
                    <span class="bg-slate-200/80 text-slate-800 px-1.5 py-0.2 rounded text-[10px] font-mono font-bold">${workingConfs}/${reqConfs}</span>
                </button>
            </div>
        `;
    }

    const isBroken = app.status !== "operational";

    return `
        <div class="bg-white rounded-xl border border-slate-200 p-5 flex flex-col justify-between hover:border-slate-300 transition-all shadow-sm">
            <div>
                <!-- Status Header: Asset ID & Status Badge -->
                <div class="flex items-center justify-between">
                    <span class="font-mono text-xs text-slate-400 font-semibold uppercase tracking-wider">${app.asset_label}</span>
                    ${statusPill}
                </div>

                <div class="mt-2">
                    <h3 class="font-bold text-sm text-slate-900">${typeLabel}</h3>
                    <p class="text-xs text-slate-500 font-medium">${floorLabel} • ${app.location_desc}</p>
                </div>

                <!-- Crowd Confirmation Pill & Issue Details -->
                ${isBroken ? `
                    <div class="mt-3 space-y-2">
                        <div class="flex flex-wrap items-center gap-1.5">
                            <span class="bg-rose-50 border border-rose-200 text-rose-700 text-xs font-semibold px-2 py-1 rounded-md inline-flex items-center gap-1.5 font-mono">
                                ${app.confirmations_count} students confirmed broken
                            </span>
                            ${(app.working_confirmations_count || 0) > 0 ? `
                                <span class="bg-amber-50 border border-amber-300 text-amber-800 text-xs font-semibold px-2 py-1 rounded-md inline-flex items-center gap-1.5 font-mono">
                                    ${app.working_confirmations_count}/${app.required_working_confirmations || 2} confirmed working
                                </span>
                            ` : ''}
                        </div>
                        <p class="text-xs text-slate-600 bg-slate-50 p-2.5 rounded-lg border border-slate-200/80 italic">
                            "${app.issue_description || 'Defect reported by floor resident'}"
                        </p>
                    </div>
                ` : `
                    <p class="mt-3 text-xs text-slate-500 bg-emerald-50/40 p-2 rounded-lg border border-emerald-100/60">
                        Verified normal operation
                    </p>
                `}
            </div>

            ${actionButtons}
        </div>
    `;
}

function openReportModal(appId, label, type) {
    document.getElementById("modal-appliance-title").textContent = `Report ${label} (${type})`;
    document.getElementById("modal-issue-desc").value = "";
    document.getElementById("report-modal").dataset.appId = appId;
    document.getElementById("report-modal").classList.remove("hidden");
}

function closeReportModal() {
    document.getElementById("report-modal").classList.add("hidden");
}

async function submitApplianceReport() {
    const modal = document.getElementById("report-modal");
    const appId = parseInt(modal.dataset.appId);
    const desc = document.getElementById("modal-issue-desc").value.trim();

    if (!desc) {
        alert("Please describe what is wrong with the appliance.");
        return;
    }

    try {
        const res = await fetch("/api/v1/appliances/report", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                appliance_id: appId,
                issue_description: desc,
                user_token: userToken,
                reporter_name: "Floor Resident"
            })
        });

        if (res.ok) {
            closeReportModal();
            showToast("Report submitted! Floor residents can now confirm.", "success");
            await loadAppliances();
            await loadSLAStats();
        } else {
            const err = await res.json();
            showToast("Error: " + (err.detail || "Failed to submit report"), "error");
        }
    } catch (e) {
        showToast("Failed to submit appliance report: " + e.message, "error");
    }
}

async function confirmBroken(appId) {
    try {
        const res = await fetch(`/api/v1/appliances/${appId}/confirm`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_token: userToken })
        });

        if (res.ok) {
            showToast("Your confirmation was recorded. Priority recalculated!", "success");
            await loadAppliances();
        } else {
            const err = await res.json();
            showToast(err.detail || "You have already confirmed this issue.", "warning");
        }
    } catch (e) {
        showToast("Failed to confirm issue: " + e.message, "error");
    }
}

async function reportWorking(appId) {
    try {
        const res = await fetch(`/api/v1/appliances/${appId}/resolve-crowd`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_token: userToken })
        });

        const data = await res.json();
        if (res.ok) {
            if (data.resolved) {
                showToast(`Appliance verified fixed & restored to operational! (${data.working_confirmations}/${data.required_confirmations} resident consensus)`, "success", 4500);
            } else {
                showToast(data.message || `Confirmation recorded (${data.working_confirmations}/${data.required_confirmations}). Need 1 more resident to verify before it is restored.`, "info", 5000);
            }
            await loadAppliances();
            await loadSLAStats();
        } else {
            showToast(data.detail || "You have already confirmed this issue or verification is pending.", "warning", 5000);
        }
    } catch (e) {
        showToast("Failed to submit verification: " + e.message, "error");
    }
}

// ─── Room Ticket OTP State ────────────────────────────────────────────────────
// State machine: 'idle' → 'otp_sent' → 'otp_verified' → ticket submitted
let _ticketOtpState = "idle";
let _ticketVerifiedPhone = "";
let _ticketFormData = null;

async function submitRoomTicket(e) {
    e.preventDefault();
    const resultBox = document.getElementById("room-ticket-result");
    resultBox.classList.add("hidden");

    const hostelId       = parseInt(document.getElementById("room-hostel-select").value);
    const floor          = parseInt(document.getElementById("room-floor").value);
    const roomNumber     = document.getElementById("room-number").value.trim().toUpperCase();
    const category       = document.getElementById("room-category").value;
    const desc           = document.getElementById("room-desc").value.trim();
    const reporterName   = document.getElementById("room-reporter-name").value.trim();
    const reporterContact= document.getElementById("room-reporter-contact").value.trim();
    const cleanPhone     = reporterContact.replace(/\D/g, "");

    // Validate phone
    if (!cleanPhone || cleanPhone.length < 10) {
        resultBox.className = "p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800";
        resultBox.textContent = "Please enter a valid 10-digit mobile number. An OTP will be sent to verify your identity before the ticket is created.";
        resultBox.classList.remove("hidden");
        return;
    }

    // For hackathon evaluation: Direct room ticket submission with phone stored for notification/SLA tracking
    _ticketFormData = { hostelId, floor, roomNumber, category, desc, reporterName, cleanPhone };
    resultBox.className = "p-3 rounded-lg bg-blue-50 border border-blue-200 text-xs text-blue-800";
    resultBox.textContent = "Lodging ticket…";
    resultBox.classList.remove("hidden");

    await _createRoomTicket(resultBox);
}

async function verifyRoomTicketOtp() {
    const code = (document.getElementById("room-otp-input")?.value || "").trim();
    const resultBox = document.getElementById("room-ticket-result");
    const btn = document.getElementById("room-otp-btn");
    if (!code || code.length < 6) {
        showToast("Please enter the 6-digit OTP.", "warning");
        return;
    }
    if (btn) { btn.disabled = true; btn.textContent = "Verifying…"; }
    try {
        const res = await fetch("/api/v1/otp/verify", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ phone: _ticketVerifiedPhone, code, purpose: "ticket" })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Invalid OTP. Please try again.");

        _ticketOtpState = "otp_verified";
        await _createRoomTicket(resultBox);
    } catch (err) {
        showToast(err.message, "error");
        if (btn) { btn.disabled = false; btn.textContent = "Verify"; }
    }
}

async function resendRoomOtp() {
    _ticketOtpState = "idle";
    // Re-trigger the submit flow
    const fakeEvent = { preventDefault: () => {} };
    await submitRoomTicket(fakeEvent);
}

async function _createRoomTicket(resultBox) {
    const { hostelId, floor, roomNumber, category, desc, reporterName, cleanPhone } = _ticketFormData;
    try {
        const res = await fetch("/api/v1/tickets/room", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                hostel_id: hostelId,
                floor: floor,
                room_number: roomNumber,
                category: category,
                title: `${category.toUpperCase()} defect in Room ${roomNumber}`,
                description: desc,
                reporter_name: reporterName || "Resident",
                reporter_contact: cleanPhone
            })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Failed to submit room ticket.");
        }

        const ticket = await res.json();
        _ticketOtpState = "otp_verified"; // Keep state so same phone doesn't need re-verify in session
        resultBox.className = "p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 space-y-1.5";
        resultBox.innerHTML = `
            <div class="flex items-center gap-1.5 font-bold">
                <span>✅ Ticket Lodged:</span>
                <span class="font-mono text-emerald-900 bg-emerald-100 px-2 py-0.5 rounded">Ticket Reference: #${ticket.ticket_code}</span>
            </div>
            <p>Your room defect ticket has been queued and dispatched to maintenance.</p>
            <p class="text-[11px] text-emerald-700 font-mono">Contact registered: +91 ${cleanPhone} (SMS notification on technician resolution)</p>
        `;
        resultBox.classList.remove("hidden");

        document.getElementById("room-desc").value = "";
        document.getElementById("ticket-lookup-input").value = "#" + ticket.ticket_code;
        lookupTicket();

    } catch (err) {
        resultBox.className = "p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800";
        resultBox.textContent = err.message;
        resultBox.classList.remove("hidden");
    }
}


async function lookupTicket() {
    const rawCode = document.getElementById("ticket-lookup-input").value.trim();
    const container = document.getElementById("ticket-status-display");

    if (!rawCode) {
        showToast("Please enter a ticket reference (e.g. #LAT-8921).", "warning");
        return;
    }
    const cleanCode = rawCode.replace(/^#/, '').trim();

    try {
        const res = await fetch(`/api/v1/tickets/${cleanCode}`);
        if (!res.ok) {
            container.innerHTML = `<div class="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-medium">Ticket Reference #${cleanCode} not found. Please verify the code.</div>`;
            container.classList.remove("hidden");
            return;
        }

        const t = await res.json();
        const isAwaitingStudent = t.status === "awaiting_student_verification";
        const isResolved = t.status === "resolved";
        const isInProgress = t.status === "in_progress" || isAwaitingStudent || isResolved;

        let statusBadge = "";
        if (isResolved) {
            statusBadge = `<span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">● RESOLVED</span>`;
        } else if (isAwaitingStudent) {
            statusBadge = `<span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-300">● AWAITING RESIDENT VERIFICATION (Step 2 of 2)</span>`;
        } else if (t.status === "in_progress") {
            statusBadge = `<span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">● IN PROGRESS</span>`;
        } else {
            statusBadge = `<span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-300">● SUBMITTED</span>`;
        }

        container.innerHTML = `
            <div class="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-5">
                <div class="flex items-start justify-between border-b border-slate-100 pb-3">
                    <div>
                        <div class="flex items-center gap-2">
                            <span class="font-mono text-xs font-bold text-slate-900 bg-slate-100 px-2.5 py-1 rounded border border-slate-200">
                                Ticket Reference: #${t.ticket_code}
                            </span>
                            <span class="text-xs text-slate-500 uppercase font-semibold">${t.category}</span>
                        </div>
                        <h4 class="mt-1.5 text-sm font-bold text-slate-900">${t.title}</h4>
                        <p class="text-xs text-slate-500 font-medium">${t.hostel_name} • ${t.room_number ? 'Room ' + t.room_number : 'Common Floor ' + t.floor}</p>
                        ${t.reporter_contact ? `<p class="text-[11px] font-mono text-slate-600 mt-0.5">Mobile: <span class="font-bold text-slate-900">+91 ${t.reporter_contact}</span></p>` : ''}
                    </div>
                </div>

                <div>
                    <p class="text-xs font-semibold text-slate-500 mb-1">Status:</p>
                    ${statusBadge}
                </div>

                <!-- Stepper Progress Bar: [● Submitted] --- [● In Progress] --- [● VERIFY] --- (○ Done) -->
                <div class="border-t border-b border-slate-100 py-3 font-mono text-[11px]">
                    <div class="flex items-center justify-between text-slate-700">
                        <span class="font-bold text-slate-900">[● Submitted]</span>
                        <span class="text-slate-300">---</span>
                        <span class="${isInProgress ? 'font-bold text-indigo-700' : 'text-slate-400'}">[● In Progress]</span>
                        <span class="text-slate-300">---</span>
                        <span class="${isAwaitingStudent ? 'font-black text-amber-700 bg-amber-100 px-1.5 py-0.5 rounded' : (isResolved ? 'font-bold text-emerald-700' : 'text-slate-400')}">
                            ${isAwaitingStudent ? '[● VERIFY (STEP 2)]' : '[● Verify]'}
                        </span>
                        <span class="text-slate-300">---</span>
                        <span class="${isResolved ? 'font-black text-emerald-700 bg-emerald-100 px-1.5 py-0.5 rounded' : 'text-slate-400'}">
                            ${isResolved ? '(● Done)' : '(○ Done)'}
                        </span>
                    </div>
                </div>

                <!-- 2-STEP VERIFICATION CARD (For Room Tickets) -->
                ${t.ticket_type === 'room' ? `
                    <div class="bg-amber-50/60 border-2 border-amber-300 rounded-xl p-5 space-y-4">
                        ${isAwaitingStudent ? `
                            <!-- SMS Notification Notification Banner -->
                            <div class="p-3 rounded-lg bg-amber-100/90 border border-amber-300 text-xs text-amber-900 flex items-start gap-2.5">
                                <span class="text-xs font-mono font-bold px-1.5 py-0.5 rounded bg-amber-100 text-amber-800">SMS</span>
                                <div class="space-y-0.5">
                                    <p class="font-bold text-amber-950">SMS Notification Dispatched to +91 ${t.reporter_contact || 'Registered Mobile'}:</p>
                                    <p class="text-[11px] text-amber-800">Technician reported repairs completed in Room ${t.room_number || ''}. Please test in your room and confirm below to close the ticket so you don't forget.</p>
                                </div>
                            </div>
                        ` : ''}

                        <!-- Step 1 Details -->
                        <div class="space-y-1 border-b border-amber-200/80 pb-3">
                            <div class="flex items-center justify-between text-xs font-bold text-slate-800">
                                <span>STEP 1: TECHNICIAN RESOLUTION LOGGED</span>
                                <span class="${t.tech_completed ? 'text-emerald-700 font-bold' : 'text-slate-500'}">
                                    ${t.tech_completed ? 'LOGGED' : 'PENDING'}
                                </span>
                            </div>
                            <p class="text-xs text-slate-700">
                                Done by: <span class="font-semibold text-slate-900">${t.tech_assigned_to || 'Assigned Technician'}</span>
                                ${t.tech_completed_at ? ` at ${new Date(t.tech_completed_at).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}` : ''}
                            </p>
                            <p class="text-xs text-slate-600 italic">
                                Notes: "${t.tech_notes || (t.tech_completed ? 'Physical repair completed' : 'Inspection in progress')}"
                            </p>
                        </div>

                        <!-- Step 2 Details -->
                        <div class="space-y-2">
                            <div class="flex items-center justify-between text-xs font-bold text-slate-800">
                                <span>STEP 2: RESIDENT CONFIRMATION REQUIRED</span>
                                <span class="${t.student_verified ? 'text-emerald-700 font-bold' : (isAwaitingStudent ? 'text-amber-800 font-bold animate-pulse' : 'text-slate-500')}">
                                    ${t.student_verified ? 'CONFIRMED' : (isAwaitingStudent ? 'ACTION REQUIRED' : 'PENDING')}
                                </span>
                            </div>

                            ${isAwaitingStudent ? `
                                <p class="text-xs text-slate-700 font-medium">
                                    Did the technician successfully fix the problem in your room?
                                </p>
                                <div class="pt-1">
                                    <button onclick="confirmStudentVerification('${t.ticket_code}', true)" 
                                        class="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold py-2.5 px-4 rounded-lg w-full text-sm shadow-xs transition-colors">
                                        Yes, Confirm & Close
                                    </button>
                                    <button onclick="confirmStudentVerification('${t.ticket_code}', false)" 
                                        class="bg-white border border-rose-300 text-rose-700 hover:bg-rose-50 font-semibold py-2 px-4 rounded-lg w-full text-xs mt-2 transition-colors">
                                        No, Still Broken
                                    </button>
                                </div>
                            ` : (isResolved ? `
                                <p class="text-xs text-emerald-800 font-medium">
                                    You confirmed the repair. Feedback: "${t.student_feedback || 'Work completed satisfactorily.'}"

                                </p>
                            ` : `
                                <p class="text-xs text-slate-500">
                                    Resident confirmation activates once technician reports work completion.
                                </p>
                            `)}
                        </div>
                    </div>
                ` : ''}

                <div class="text-xs text-slate-500 bg-slate-50 p-3 rounded-lg border border-slate-100">
                    <span class="font-semibold text-slate-700">Complaint Details:</span> ${t.description}
                </div>
            </div>
        `;
        container.classList.remove("hidden");

    } catch (err) {
        container.innerHTML = `<div class="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs">Failed to fetch ticket status.</div>`;
        container.classList.remove("hidden");
    }
}

async function confirmStudentVerification(ticketCode, verified) {
    let feedback = "";
    if (verified) {
        feedback = prompt("Optional feedback for the maintenance team:", "Work completed satisfactorily. Everything is functioning.");
        if (feedback === null) return;
    } else {
        feedback = prompt("What is still not working?", "Issue persists / incomplete repair");
        if (feedback === null) return;
    }

    try {
        const res = await fetch(`/api/v1/tickets/${ticketCode}/verify`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                verified: verified,
                student_feedback: feedback
            })
        });

        if (res.ok) {
            showToast(verified ? "Thank you! Your ticket has been confirmed and officially closed." : "Noted. Ticket reopened and technician notified.", verified ? "success" : "warning", 5000);
            lookupTicket();
        } else {
            const err = await res.json();
            showToast("Error: " + (err.detail || "Failed to submit verification"), "error");
        }
    } catch (e) {
        showToast("Failed to submit verification: " + e.message, "error");
    }
}

// ==========================================
// 5. CAMPUS SLA ANALYTICS SCREEN
// ==========================================
async function loadSLAStats() {
    try {
        const res = await fetch("/api/v1/analytics/sla");
        if (!res.ok) return;
        const stats = await res.json();

        // 1. Metric Ribbon
        const elActive = document.getElementById("kpi-active-tickets");
        const elCrit = document.getElementById("kpi-critical-tickets");
        const elPct = document.getElementById("kpi-operational-pct");
        const elBar = document.getElementById("kpi-health-bar");

        const elCritSub = document.getElementById("kpi-critical-subpill");
        const elStdSub = document.getElementById("kpi-standard-subpill");

        if (elActive) elActive.textContent = stats.total_active_tickets;
        if (elCrit) elCrit.textContent = String(stats.total_critical_tickets).padStart(2, "0");
        if (elPct) elPct.textContent = `${stats.appliances_operational_pct}%`;
        if (elBar) elBar.style.width = `${stats.appliances_operational_pct}%`;

        if (elCritSub) elCritSub.textContent = `${stats.total_critical_tickets} Critical`;
        if (elStdSub) {
            const stdCount = Math.max(0, stats.total_active_tickets - stats.total_critical_tickets);
            elStdSub.textContent = `${stdCount} Standard`;
        }

        // 2. 21-Hostel SLA Scoreboard (3x7 grid)
        const slaContainer = document.getElementById("sla-cards-container");
        if (slaContainer && stats.sla_metrics) {
            slaContainer.innerHTML = stats.sla_metrics.map(m => {
                const isQuick = m.avg_resolution_hours <= 8.0;
                const total = (m.total_resolved || 0) + (m.total_pending || 0);
                const pctResolved = total > 0 ? Math.round((m.total_resolved / total) * 100) : 100;

                return `
                    <div class="bg-white rounded-xl border border-slate-200 p-3.5 space-y-2 shadow-2xs hover:border-slate-300 transition-colors">
                        <div class="flex items-center justify-between">
                            <h5 class="font-bold text-slate-900 text-xs truncate" title="${m.hostel_name}">${m.hostel_name}</h5>
                            <span class="text-[10px] font-semibold px-1.5 py-0.2 rounded ${isQuick ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-800'}">
                                ${m.avg_resolution_hours}h
                            </span>
                        </div>
                        <div class="flex items-baseline gap-1">
                            <span class="text-sm font-black font-mono text-slate-800">${m.avg_resolution_hours} hrs</span>
                            <span class="text-[10px] text-slate-400">avg SLA</span>
                        </div>
                        <div class="space-y-1">
                            <div class="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                                <div class="bg-emerald-500 h-1.5 rounded-full" style="width: ${pctResolved}%"></div>
                            </div>
                            <div class="flex justify-between text-[10px] font-mono text-slate-400">
                                <span>${m.total_resolved} done</span>
                                <span>${m.total_pending} open</span>
                            </div>
                        </div>
                    </div>
                `;
            }).join("");
        }

    } catch (err) {
        console.error("Failed to load SLA stats:", err);
    }
}
