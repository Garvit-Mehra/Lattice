/**
 * LATTICE · IITH Operations Console - Technician Portal Controller
 * Supports Tab 1 (Washing Machines & Water Coolers),
 * Tab 2 (Room Maintenance Queries), and Step 1 of the 2-Step Verification Workflow.
 */

let currentTech = null;
let activeTab = "appliances"; // 'appliances' or 'rooms'
let hostelsList = [];
let pendingCompleteTicketId = null;
let pendingApplianceId = null;
let selectedResolutionTag = "";
let selectedPartsList = [];
let roomTicketsCache = [];

// ==========================================
// TOAST NOTIFICATION UTILITY (Task 31)
// ==========================================
function showToast(message, type = "info", duration = 4000) {
    let container = document.getElementById("toast-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "toast-container";
        document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    toast.className = `toast-item toast-${type}`;

    let icon = "ℹ";
    if (type === "success") icon = "✓";
    if (type === "error") icon = "✕";

    toast.innerHTML = `
        <span class="font-bold font-mono text-sm leading-none">${icon}</span>
        <div class="flex-1 font-medium text-xs break-words">${message}</div>
        <button type="button" class="text-xs opacity-60 hover:opacity-100 transition-opacity ml-1 font-mono">✕</button>
    `;

    toast.querySelector("button").onclick = () => removeToast(toast);
    container.appendChild(toast);

    const timer = setTimeout(() => removeToast(toast), duration);

    function removeToast(el) {
        clearTimeout(timer);
        el.classList.add("toast-hiding");
        setTimeout(() => el.remove(), 250);
    }
}

// 1-Click Copy-to-Clipboard (Task 35)
async function copyToClipboard(text, btnElement) {
    try {
        await navigator.clipboard.writeText(text);
        if (btnElement) {
            const original = btnElement.innerHTML;
            btnElement.innerHTML = "Copied ✓";
            btnElement.classList.add("text-amber-400", "font-bold");
            setTimeout(() => {
                btnElement.innerHTML = original;
                btnElement.classList.remove("text-amber-400", "font-bold");
            }, 1800);
        }
        showToast(`Copied ${text} to clipboard!`, "success", 2000);
    } catch (e) {
        showToast(`Failed to copy: ${text}`, "error");
    }
}

// Dynamic Cross-Portal Navigation Links
function updateCrossPortalLinks() {
    const isMultiPort = window.location.port === "8001" || window.location.port === "8002";
    const isSinglePort = !isMultiPort;
    const studentLink = document.getElementById("nav-link-student");
    const adminLink = document.getElementById("nav-link-admin");
    const presLink = document.getElementById("nav-link-presentation");

    if (studentLink) {
        studentLink.href = isSinglePort ? "/" : `//${window.location.hostname}:8000/`;
    }
    if (adminLink) {
        adminLink.href = isSinglePort ? "/admin" : `//${window.location.hostname}:8002/`;
    }
    if (presLink) {
        presLink.href = "/presentation";
    }
}

// Modal Backdrop Click & Escape Dismissal (Task 33)
document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
        closeModalRoomComplete();
        closeModalAppStatus();
    }
});

// Determine API Base URL dynamically (works on port 8001 or mounted at /tech on port 8000)
function getApiBase() {
    if (window.location.pathname.startsWith("/tech")) {
        return "/tech";
    }
    return "";
}

function getAuthHeader() {
    const token = localStorage.getItem("kandifix_tech_token");
    return token ? { "Authorization": `Bearer ${token}` } : {};
}

function selectResolutionTag(btn, tag) {
    selectedResolutionTag = tag;
    document.querySelectorAll(".res-tag-btn").forEach(b => {
        b.className = "res-tag-btn p-2 rounded-lg bg-slate-800 border border-slate-700 text-xs text-left text-slate-300 hover:border-amber-500";
    });
    btn.className = "res-tag-btn p-2 rounded-lg bg-amber-500/20 border border-amber-500 text-xs text-left text-amber-300 font-bold";
}

function togglePartChip(btn, part) {
    const idx = selectedPartsList.indexOf(part);
    if (idx > -1) {
        selectedPartsList.splice(idx, 1);
        btn.className = "px-2.5 py-1 rounded-md text-[11px] font-mono bg-slate-800 text-slate-300 border border-slate-700 hover:border-amber-500";
    } else {
        selectedPartsList.push(part);
        btn.className = "px-2.5 py-1 rounded-md text-[11px] font-mono bg-amber-500/20 text-amber-300 border border-amber-500 font-bold";
    }
}


// ==========================================
// 1. INITIALIZATION & AUTHENTICATION
// ==========================================
document.addEventListener("DOMContentLoaded", async () => {
    updateCrossPortalLinks();
    setupAuthForm();
    await loadHostels();
    await verifyCurrentSession();
    initTechAutoRefresh();
});

function initTechAutoRefresh() {
    setInterval(() => {
        if (!currentTech) return;
        if (activeTab === "appliances") {
            loadFaultyAppliances();
        } else if (activeTab === "rooms") {
            loadRoomTickets();
        }
    }, 15000);
}

function setupAuthForm() {
    const form = document.getElementById("tech-login-form");
    if (form) {
        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            const username = document.getElementById("tech-username").value.trim();
            const password = document.getElementById("tech-password").value.trim();
            await loginTechnician(username, password);
        });
    }
}

function fillDemoTech(username, password) {
    document.getElementById("tech-username").value = username;
    document.getElementById("tech-password").value = password;
    loginTechnician(username, password);
}

async function loginTechnician(username, password) {
    const errBox = document.getElementById("login-error");
    const submitBtn = document.getElementById("btn-login-submit");
    if (errBox) errBox.classList.add("hidden");
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = "Verifying...";
    }

    try {
        const res = await fetch(`${getApiBase()}/api/v1/tech/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Invalid technician credentials.");
        }

        const data = await res.json();
        localStorage.setItem("kandifix_tech_token", data.token);
        currentTech = data;
        updateNavProfile();
        document.getElementById("login-modal").classList.add("hidden");
        
        // Load initial data
        loadFaultyAppliances();
        loadRoomTickets();
    } catch (err) {
        if (errBox) {
            errBox.textContent = err.message;
            errBox.classList.remove("hidden");
        }
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = "Sign In to Duty Console";
        }
    }
}

async function verifyCurrentSession() {
    const token = localStorage.getItem("kandifix_tech_token");
    if (!token) {
        document.getElementById("login-modal").classList.remove("hidden");
        return;
    }

    try {
        const res = await fetch(`${getApiBase()}/api/v1/tech/me`, {
            headers: getAuthHeader()
        });

        if (!res.ok) {
            localStorage.removeItem("kandifix_tech_token");
            document.getElementById("login-modal").classList.remove("hidden");
            return;
        }

        currentTech = await res.json();
        updateNavProfile();
        document.getElementById("login-modal").classList.add("hidden");
        loadFaultyAppliances();
        loadRoomTickets();
    } catch (err) {
        document.getElementById("login-modal").classList.remove("hidden");
    }
}

function updateNavProfile() {
    if (!currentTech) return;
    const nameEl = document.getElementById("nav-tech-name");
    const roleEl = document.getElementById("nav-tech-role");
    if (nameEl) nameEl.textContent = currentTech.name;
    if (roleEl) roleEl.textContent = currentTech.username;
}

async function techLogout() {
    try {
        await fetch(`${getApiBase()}/api/v1/tech/logout`, {
            method: "POST",
            headers: getAuthHeader()
        });
    } catch (e) {}

    localStorage.removeItem("kandifix_tech_token");
    currentTech = null;
    document.getElementById("login-modal").classList.remove("hidden");
}

async function loadHostels() {
    try {
        let res = await fetch(`${getApiBase()}/api/v1/hostels`);
        if (!res.ok) res = await fetch(`/api/v1/hostels`);
        if (res.ok) {
            hostelsList = await res.json();
            populateHostelDropdowns();
        }
    } catch (e) {
        console.warn("Could not fetch hostel list from primary endpoint", e);
    }
}

function populateHostelDropdowns() {
    const appFilter = document.getElementById("tech-app-hostel-filter");
    const roomFilter = document.getElementById("tech-room-hostel-filter");

    const options = hostelsList.map(h => `<option value="${h.id}">${h.name}</option>`).join("");
    
    if (appFilter) {
        appFilter.innerHTML = `<option value="">All 21 Hostels</option>` + options;
    }
    if (roomFilter) {
        roomFilter.innerHTML = `<option value="">All 21 Hostels</option>` + options;
    }
}

// ==========================================
// 2. TAB SWITCHING
// ==========================================
function switchTechTab(tab) {
    activeTab = tab;
    const btnApp = document.getElementById("tab-btn-appliances");
    const btnRooms = document.getElementById("tab-btn-rooms");
    const viewApp = document.getElementById("view-tech-appliances");
    const viewRooms = document.getElementById("view-tech-rooms");

    if (tab === "appliances") {
        btnApp.className = "flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-amber-500 text-slate-950 shadow-lg shadow-amber-500/25 transition";
        btnRooms.className = "flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800/60 transition";
        viewApp.classList.remove("hidden");
        viewRooms.classList.add("hidden");
        loadFaultyAppliances();
    } else {
        btnRooms.className = "flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-amber-500 text-slate-950 shadow-lg shadow-amber-500/25 transition";
        btnApp.className = "flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800/60 transition";
        viewRooms.classList.remove("hidden");
        viewApp.classList.add("hidden");
        loadRoomTickets();
    }
}

// ==========================================
// 3. TAB 1: COMMON APPLIANCES CONTROLLER
// ==========================================
async function loadFaultyAppliances() {
    const listContainer = document.getElementById("tech-appliances-list");
    const badgeCount = document.getElementById("badge-faulty-count");
    if (!listContainer) return;

    const hostelId = document.getElementById("tech-app-hostel-filter").value;
    const assetType = document.getElementById("tech-app-type-filter").value;

    let url = `${getApiBase()}/api/v1/tech/appliances/faulty?`;
    if (hostelId) url += `hostel_id=${hostelId}&`;
    if (assetType) url += `asset_type=${assetType}&`;

    try {
        const res = await fetch(url, { headers: getAuthHeader() });
        if (!res.ok) {
            if (res.status === 401) {
                document.getElementById("login-modal").classList.remove("hidden");
                return;
            }
            throw new Error("Failed to load appliance complaints");
        }

        const data = await res.json();
        if (badgeCount) badgeCount.textContent = data.length;

        if (data.length === 0) {
            listContainer.innerHTML = `
                <div class="p-12 text-center rounded-2xl glass-card text-slate-400">
                    <span class="font-mono text-xs font-bold text-slate-400">[ALL OPERATIONAL]</span>
                    <h3 class="mt-2 font-bold text-white text-sm">No Active Appliance Breakdowns</h3>
                    <p class="text-xs text-slate-400 mt-1">All washing machines and water coolers are reported operational.</p>
                </div>
            `;
            return;
        }

        listContainer.innerHTML = data.map(app => {
            const isCooler = app.asset_type === "water_cooler";
            const icon = isCooler ? "WC" : "WM";
            const badgeClass = app.priority_tier === "CRITICAL" ? "badge-critical" : (app.priority_tier === "HIGH" ? "badge-high" : (app.priority_tier === "MEDIUM" ? "badge-medium" : "badge-low"));
            const floorLabel = app.floor === 0 ? "Ground Floor" : `Floor ${app.floor}`;
            // Task 13: CRITICAL priority threshold aligns with backend scoring (>= 50.0)
            const isCriticalPrio = app.priority_tier === "CRITICAL" || (app.priority_score || 0) >= 50.0;
            const prioRing = isCriticalPrio ? "ring-2 ring-rose-500/50 animate-pulse" : "";

            return `
                <div class="bg-[#0f172a] rounded-xl p-5 border border-slate-800 hover:border-slate-700 transition flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                    <div class="flex items-start gap-4 flex-1">
                        <div class="w-12 h-12 rounded-xl bg-slate-800/80 border border-slate-700 flex items-center justify-center text-2xl flex-shrink-0">
                            <span class="text-xs font-mono font-bold text-slate-300">${icon}</span>
                        </div>
                        <div class="space-y-1.5">
                            <div class="flex flex-wrap items-center gap-2">
                                <span class="font-bold text-white text-base tracking-tight">${app.asset_label}</span>
                                <span class="px-2.5 py-1 rounded-full text-[11px] font-mono font-bold ${badgeClass} ${prioRing}">
                                    ${app.priority_tier} (Score ${app.priority_score})
                                </span>
                                ${app.confirmations_count > 1 ? `
                                    <span class="px-2.5 py-0.5 rounded-full text-[11px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                                        ${app.confirmations_count} Confirmations
                                    </span>
                                ` : ''}
                                <span class="px-2.5 py-0.5 rounded-full text-[11px] font-mono font-semibold ${app.status === 'in_progress' ? 'bg-indigo-950/60 text-indigo-300 border border-indigo-700' : 'bg-rose-950/60 text-rose-300 border border-rose-800'}">
                                    ${app.status.toUpperCase().replace('_', ' ')}
                                </span>
                            </div>
                            <p class="text-xs text-slate-300 font-medium">
                                <span class="text-white font-bold">${app.hostel_name}</span> • ${floorLabel} • <span class="text-slate-400 font-mono">${app.location_desc}</span>
                            </p>
                            <p class="text-xs text-slate-300 bg-[#020617] p-2.5 rounded-lg border border-slate-800 mt-2">
                                <span class="font-semibold text-slate-400">Reported Issue:</span> ${app.issue_description || 'Appliance malfunctioning'}
                            </p>
                        </div>
                    </div>

                    <div class="flex flex-row md:flex-col gap-2 w-full md:w-52 flex-shrink-0">
                        ${app.status !== 'in_progress' ? `
                            <button onclick="markApplianceInProgress(${app.id})" class="touch-target min-h-[48px] flex-1 py-2 px-3 rounded-xl text-xs font-bold bg-indigo-600 hover:bg-indigo-500 text-white border border-indigo-500/40 transition flex items-center justify-center">
                                Claim & Dispatch
                            </button>
                        ` : ''}
                        <button onclick="openModalAppStatus(${app.id}, '${app.asset_label}', '${app.hostel_name}', '${floorLabel}')" class="touch-target min-h-[48px] flex-1 py-2 px-3 rounded-xl text-xs font-bold bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-md shadow-amber-500/20 transition flex items-center justify-center">
                            Mark Repaired
                        </button>
                    </div>
                </div>
            `;
        }).join("");

    } catch (err) {
        listContainer.innerHTML = `<div class="p-6 rounded-xl bg-red-950/30 text-red-300 text-xs">Error loading appliances: ${err.message}</div>`;
    }
}

async function markApplianceInProgress(appId) {
    try {
        const res = await fetch(`${getApiBase()}/api/v1/tech/appliances/${appId}/status`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...getAuthHeader()
            },
            body: JSON.stringify({ status: "in_progress", notes: "Technician claimed & dispatched to floor." })
        });
        if (res.ok) {
            showToast("Appliance claimed & dispatched to floor!", "success");
            loadFaultyAppliances();
        } else {
            showToast("Failed to mark appliance in-progress.", "error");
        }
    } catch (e) {
        showToast("Failed to mark appliance in-progress: " + e.message, "error");
    }
}

function openModalAppStatus(appId, label, hostel, floor) {
    pendingApplianceId = appId;
    selectedResolutionTag = "";
    document.querySelectorAll(".res-tag-btn").forEach(b => {
        b.className = "res-tag-btn p-2 rounded-lg bg-slate-800 border border-slate-700 text-xs text-left text-slate-300 hover:border-amber-500";
    });
    document.getElementById("modal-app-title").textContent = `Mark Repaired: ${label}`;
    document.getElementById("modal-app-sub").textContent = `${hostel} • ${floor}`;
    const statusSelect = document.getElementById("modal-app-status-select");
    if (statusSelect) statusSelect.value = "operational";
    document.getElementById("modal-app-notes").value = "";
    document.getElementById("modal-appliance-status").classList.remove("hidden");
}

function closeModalAppStatus() {
    pendingApplianceId = null;
    selectedResolutionTag = "";
    const modal = document.getElementById("modal-appliance-status");
    if (modal) modal.classList.add("hidden");
}

async function submitAppStatusUpdate() {
    if (!pendingApplianceId) return;
    const statusSelect = document.getElementById("modal-app-status-select");
    const newStatus = statusSelect ? statusSelect.value : "operational";
    let notes = document.getElementById("modal-app-notes").value.trim();
    if (selectedResolutionTag) {
        notes = `[Resolution: ${selectedResolutionTag}] ${notes}`.trim();
    }

    try {
        const res = await fetch(`${getApiBase()}/api/v1/tech/appliances/${pendingApplianceId}/status`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...getAuthHeader()
            },
            body: JSON.stringify({ status: newStatus, notes: notes || "Restored to operational status." })
        });

        if (res.ok) {
            closeModalAppStatus();
            showToast("Appliance marked repaired successfully!", "success");
            loadFaultyAppliances();
        } else {
            const err = await res.json();
            showToast("Error: " + (err.detail || "Failed to update appliance status"), "error");
        }
    } catch (e) {
        showToast("Failed to update status: " + e.message, "error");
    }
}

// ==========================================
// 4. TAB 2: ROOM MAINTENANCE (2-STEP VERIFICATION)
// ==========================================
async function loadRoomTickets() {
    const listContainer = document.getElementById("tech-rooms-list");
    const badgeCount = document.getElementById("badge-room-count");
    if (!listContainer) return;

    const statusFilter = document.getElementById("tech-room-status-filter").value;
    const categoryFilter = document.getElementById("tech-room-category-filter").value;
    const hostelId = document.getElementById("tech-room-hostel-filter").value;

    let url = `${getApiBase()}/api/v1/tech/tickets/room?status_filter=${statusFilter}&`;
    if (categoryFilter) url += `category=${categoryFilter}&`;
    if (hostelId) url += `hostel_id=${hostelId}&`;

    try {
        const res = await fetch(url, { headers: getAuthHeader() });
        if (!res.ok) {
            if (res.status === 401) {
                document.getElementById("login-modal").classList.remove("hidden");
                return;
            }
            throw new Error("Failed to load room tickets");
        }

        const tickets = await res.json();
        roomTicketsCache = tickets;
        if (badgeCount) badgeCount.textContent = tickets.length;
        filterRoomTicketsLive();

    } catch (err) {
        listContainer.innerHTML = `<div class="p-6 rounded-xl bg-red-950/30 text-red-300 text-xs">Error loading room complaints: ${err.message}</div>`;
    }
}

// Real-Time Search Filter (Task 36)
function filterRoomTicketsLive() {
    const query = (document.getElementById("tech-room-search-input")?.value || "").toLowerCase().trim();
    if (!query) {
        renderRoomTickets(roomTicketsCache);
        return;
    }
    const filtered = roomTicketsCache.filter(t => {
        const code = (t.ticket_code || "").toLowerCase();
        const desc = (t.description || "").toLowerCase();
        const room = (t.room_number || "").toLowerCase();
        const title = (t.title || "").toLowerCase();
        const contact = (t.reporter_contact || "").toLowerCase();
        const resident = (t.reporter_name || "").toLowerCase();
        const category = (t.category || "").toLowerCase();
        return code.includes(query) || desc.includes(query) || room.includes(query) || title.includes(query) || contact.includes(query) || resident.includes(query) || category.includes(query);
    });
    renderRoomTickets(filtered);
}

function renderRoomTickets(tickets) {
    const listContainer = document.getElementById("tech-rooms-list");
    if (!listContainer) return;

    if (tickets.length === 0) {
        listContainer.innerHTML = `
            <div class="p-12 text-center rounded-2xl glass-card text-slate-400">
                <span class="font-mono text-xs font-bold text-slate-400">[NO TICKETS]</span>
                <h3 class="mt-2 font-bold text-white text-sm">No Room Tickets Found</h3>
                <p class="text-xs text-slate-400 mt-1">There are no matching room maintenance complaints for the active filter/search.</p>
            </div>
        `;
        return;
    }

    listContainer.innerHTML = tickets.map(t => {
        const badgeClass = t.priority_tier === "CRITICAL" ? "badge-critical" : (t.priority_tier === "HIGH" ? "badge-high" : (t.priority_tier === "MEDIUM" ? "badge-medium" : "badge-low"));
        const floorLabel = t.floor === 0 ? "Ground Floor" : `Floor ${t.floor}`;
        
        // 2-Step Verification Progress States
        const step1Done = t.tech_completed;
        const step2Done = t.student_verified;
        const isAwaitingStudent = t.status === "awaiting_student_verification";
        const isFullyResolved = t.status === "resolved";

        return `
            <div class="bg-[#0f172a] rounded-xl p-6 border ${isAwaitingStudent ? 'border-amber-500/80 shadow-lg shadow-amber-500/10' : 'border-slate-800'} space-y-4 overflow-hidden">
                <!-- Top Row -->
                <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-3">
                    <div class="flex flex-wrap items-center gap-2">
                        <span class="font-mono text-xs font-bold text-amber-400 bg-amber-950/60 px-2.5 py-0.5 rounded-full border border-amber-800/50">
                            Ticket Reference: #${t.ticket_code}
                        </span>
                        <button type="button" onclick="copyToClipboard('${t.ticket_code}', this)" class="text-xs px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 font-mono transition-colors" title="Copy Ticket Reference">
                            📋 Copy
                        </button>
                        <span class="px-2.5 py-0.5 rounded-full text-[11px] font-mono font-bold ${badgeClass}">
                            ${t.priority_tier} (Score: ${t.computed_priority})
                        </span>
                        <span class="px-2.5 py-0.5 rounded-full text-[11px] font-mono font-semibold bg-slate-800 text-slate-300 uppercase">
                            ${t.category}
                        </span>
                    </div>
                    <div class="text-xs font-mono text-slate-400">
                        Reported: <span class="text-slate-300 font-medium">${new Date(t.created_at).toLocaleDateString()} ${new Date(t.created_at).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}</span>
                    </div>
                </div>

                <!-- Room & Resident Details vs 2-Step Verification -->
                <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
                    <!-- Left Column: Details & Complaint Description -->
                    <div class="lg:col-span-6 space-y-3 min-w-0">
                        <div>
                            <h3 class="text-base font-bold text-white tracking-tight leading-snug">${t.title}</h3>
                            <p class="text-xs text-slate-300 font-medium mt-1">
                                <span class="text-white font-bold">${t.hostel_name}</span> • ${floorLabel} • <span class="text-amber-400 font-mono font-bold">Room ${t.room_number || 'N/A'}</span>
                            </p>
                        </div>

                        <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400 pt-0.5">
                            <span>Resident: <span class="text-slate-200 font-semibold">${t.reporter_name || 'Anonymous Resident'}</span></span>
                            ${t.reporter_contact ? `
                                <span class="text-slate-600">•</span>
                                <span class="inline-flex items-center gap-1.5 text-xs text-amber-400 font-mono font-bold">
                                    <a href="tel:${t.reporter_contact}" class="hover:underline" title="Call student">+91 ${t.reporter_contact}</a>
                                    <a href="sms:${t.reporter_contact}" class="ml-1 px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-[10px] font-mono">SMS</a>
                                </span>
                            ` : ''}
                        </div>

                        <div class="text-xs text-slate-300 bg-[#020617] p-3.5 rounded-xl border border-slate-800 mt-2">
                            <span class="font-semibold text-slate-400 block mb-1">Complaint Details:</span>
                            <p class="leading-relaxed text-slate-300 break-words">${t.description}</p>
                        </div>
                    </div>

                    <!-- Right Column: 2-Step Verification Progress Box -->
                    <div class="lg:col-span-6 bg-[#020617] p-5 rounded-xl border border-slate-800 space-y-3.5 min-w-0">
                        <div class="flex items-center justify-between text-xs font-mono font-bold border-b border-slate-800/80 pb-2">
                            <span class="text-slate-400">2-STEP VERIFICATION</span>
                            <span class="${isFullyResolved ? 'text-emerald-400' : (isAwaitingStudent ? 'text-amber-400 animate-pulse' : 'text-slate-400')}">
                                ${isFullyResolved ? 'VERIFIED & CLOSED' : (isAwaitingStudent ? 'STEP 1 COMPLETE' : 'IN PROGRESS')}
                            </span>
                        </div>

                        <!-- Step 1 Status -->
                        <div class="flex items-start gap-2.5 text-xs">
                            <div class="w-5 h-5 rounded-full flex items-center justify-center font-bold text-[10px] flex-shrink-0 mt-0.5 ${step1Done ? 'bg-emerald-500 text-slate-950 font-black' : 'bg-slate-800 text-slate-400 border border-slate-700'}">
                                ${step1Done ? 'DONE' : '1'}
                            </div>
                            <div class="flex-1 min-w-0">
                                <p class="font-bold ${step1Done ? 'text-emerald-300' : 'text-slate-300'}">
                                    ${step1Done ? 'STEP 1: TECH WORK DONE' : 'Step 1: Physical Work in Progress'}
                                </p>
                                <p class="text-[11px] text-slate-400 font-mono">
                                    ${step1Done ? `Completed by ${t.tech_assigned_to || 'Assigned Tech'}` : 'Requires on-site inspection'}
                                </p>
                                ${t.tech_notes ? `<p class="text-[11px] text-slate-300 italic mt-1 bg-slate-900/80 p-2 rounded-lg border border-slate-800 break-words">"${t.tech_notes}"</p>` : ''}
                            </div>
                        </div>

                        <!-- Step 2 Status -->
                        <div class="flex items-start gap-2.5 text-xs">
                            <div class="w-5 h-5 rounded-full flex items-center justify-center font-bold text-[10px] flex-shrink-0 mt-0.5 ${step2Done ? 'bg-emerald-500 text-slate-950 font-black' : (isAwaitingStudent ? 'bg-amber-500 text-slate-950 animate-pulse font-black' : 'bg-slate-800 text-slate-400 border border-slate-700')}">
                                ${step2Done ? 'DONE' : '2'}
                            </div>
                            <div class="flex-1 min-w-0">
                                <p class="font-bold ${step2Done ? 'text-emerald-300' : (isAwaitingStudent ? 'text-amber-300' : 'text-slate-500')}">
                                    ${step2Done ? 'STEP 2: RESIDENT VERIFIED' : (isAwaitingStudent ? 'STEP 2: RESIDENT VERIFICATION PENDING' : 'Step 2: Resident Verification Pending')}
                                </p>
                                <p class="text-[11px] text-slate-400 font-mono">
                                    ${step2Done ? 'Resident confirmed resolution' : (isAwaitingStudent ? 'Waiting for resident 2-step sign-off' : 'Pending Step 1 completion')}
                                </p>
                                ${t.student_feedback ? `<p class="text-[11px] text-emerald-400 italic mt-1 bg-emerald-950/40 p-2 rounded-lg border border-emerald-800/40 break-words">"${t.student_feedback}"</p>` : ''}
                            </div>
                        </div>

                        <!-- Action Buttons inside box (Min 48px Touch Targets) -->
                        <div class="pt-2 border-t border-slate-800/80">
                            ${!step1Done ? `
                                <div class="space-y-2">
                                    ${!t.tech_assigned_to ? `
                                        <button onclick="claimRoomTicket(${t.id})" class="touch-target min-h-[48px] w-full py-2 px-3 rounded-xl text-xs font-bold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition flex items-center justify-center">
                                            Claim Ticket
                                        </button>
                                    ` : ''}
                                    <button onclick="openModalRoomComplete(${t.id}, '${t.ticket_code}', '${t.hostel_name}', '${t.room_number || ''}', '${t.reporter_contact || ''}')" class="touch-target min-h-[48px] w-full py-2 px-3 rounded-xl text-xs font-bold bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-md shadow-amber-500/20 transition flex items-center justify-center">
                                        Mark Completed (Step 1)
                                    </button>
                                </div>
                            ` : (isAwaitingStudent ? `
                                <div class="text-center p-3 rounded-xl bg-amber-950/30 border border-amber-800/60 text-xs text-amber-300 font-mono font-semibold space-y-1">
                                    <div>Waiting for resident verification in Room ${t.room_number || ''}</div>
                                    ${t.reporter_contact ? `<div class="text-[10px] text-amber-400/80">SMS notification sent to +91 ${t.reporter_contact}</div>` : ''}
                                </div>
                            ` : `
                                <div class="text-center p-3 rounded-xl bg-emerald-950/30 border border-emerald-800/60 text-xs text-emerald-300 font-mono font-semibold">
                                    Both steps confirmed & ticket closed
                                </div>
                            `)}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join("");
}

async function claimRoomTicket(ticketId) {
    try {
        const res = await fetch(`${getApiBase()}/api/v1/tech/tickets/${ticketId}/assign`, {
            method: "POST",
            headers: getAuthHeader()
        });
        if (res.ok) {
            showToast("Room ticket claimed!", "success");
            loadRoomTickets();
        } else {
            showToast("Failed to claim ticket.", "error");
        }
    } catch (e) {
        showToast("Failed to claim ticket: " + e.message, "error");
    }
}

let pendingResidentPhone = "";

function openModalRoomComplete(ticketId, code, hostel, room, contact) {
    pendingCompleteTicketId = ticketId;
    pendingResidentPhone = contact || "";
    selectedPartsList = [];
    const container = document.getElementById("chip-parts-container");
    if (container) {
        container.querySelectorAll("button").forEach(b => {
            b.className = "px-2.5 py-1 rounded-md text-[11px] font-mono bg-slate-800 text-slate-300 border border-slate-700 hover:border-amber-500";
        });
    }
    const phoneNotice = contact ? ` • Mobile: +91 ${contact}` : '';
    document.getElementById("modal-room-ticket-sub").textContent = `Ticket Reference: #${code} • ${hostel} • Room ${room}${phoneNotice}`;
    document.getElementById("modal-tech-notes").value = "";
    document.getElementById("modal-room-complete").classList.remove("hidden");
}

function closeModalRoomComplete() {
    pendingCompleteTicketId = null;
    pendingResidentPhone = "";
    selectedPartsList = [];
    const modal = document.getElementById("modal-room-complete");
    if (modal) modal.classList.add("hidden");
}

async function submitRoomWorkComplete() {
    if (!pendingCompleteTicketId) return;
    let notes = document.getElementById("modal-tech-notes").value.trim();
    if (selectedPartsList.length > 0) {
        notes = `${notes} [Parts: ${selectedPartsList.join(", ")}]`.trim();
    }
    if (!notes) {
        showToast("Please describe what work was completed or select parts used.", "error");
        return;
    }

    try {
        const res = await fetch(`${getApiBase()}/api/v1/tech/tickets/${pendingCompleteTicketId}/complete`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...getAuthHeader()
            },
            body: JSON.stringify({
                tech_notes: notes,
                tech_name: currentTech ? currentTech.name : "Technician"
            })
        });

        if (res.ok) {
            const phoneInfo = pendingResidentPhone ? ` to +91 ${pendingResidentPhone}` : '';
            showToast(`Step 1 Completed! Automated SMS dispatched${phoneInfo} to resident.`, "success", 5000);
            closeModalRoomComplete();
            loadRoomTickets();
        } else {
            const err = await res.json();
            showToast("Error: " + (err.detail || "Failed to mark completion"), "error");
        }
    } catch (e) {
        showToast("Failed to complete ticket: " + e.message, "error");
    }
}

// ==========================================
// 8. TECHNICIAN PHONE OTP AUTHENTICATION
// ==========================================
let _techOtpPhone = "";

function switchLoginTab(mode) {
    const tabPwd = document.getElementById("tab-pwd");
    const tabOtp = document.getElementById("tab-otp");
    const panelPwd = document.getElementById("panel-pwd");
    const panelOtp = document.getElementById("panel-otp");
    const errBox = document.getElementById("login-error");
    if (errBox) errBox.classList.add("hidden");

    if (mode === "otp") {
        tabPwd.className = "flex-1 py-2 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition-colors";
        tabOtp.className = "flex-1 py-2 rounded-lg text-xs font-semibold bg-amber-500 text-slate-950 transition-colors";
        panelPwd.classList.add("hidden");
        panelOtp.classList.remove("hidden");
    } else {
        tabPwd.className = "flex-1 py-2 rounded-lg text-xs font-semibold bg-amber-500 text-slate-950 transition-colors";
        tabOtp.className = "flex-1 py-2 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition-colors";
        panelPwd.classList.remove("hidden");
        panelOtp.classList.add("hidden");
    }
}

function resetOtpStep() {
    document.getElementById("otp-step-phone").classList.remove("hidden");
    document.getElementById("otp-step-code").classList.add("hidden");
    document.getElementById("tech-otp-code").value = "";
    const errBox = document.getElementById("login-error");
    if (errBox) errBox.classList.add("hidden");
}

async function techSendOtp() {
    const phoneInput = document.getElementById("tech-otp-phone");
    const errBox = document.getElementById("login-error");
    const btn = document.getElementById("btn-otp-send");
    const raw = (phoneInput?.value || "").trim().replace(/\D/g, "");

    if (errBox) errBox.classList.add("hidden");

    if (!raw || raw.length < 10) {
        if (errBox) {
            errBox.textContent = "Please enter a valid 10-digit mobile number.";
            errBox.classList.remove("hidden");
        }
        return;
    }

    _techOtpPhone = raw;
    if (btn) { btn.disabled = true; btn.textContent = "Sending OTP..."; }

    try {
        const res = await fetch(`${getApiBase()}/api/v1/tech/otp/send`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ phone: _techOtpPhone })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to send OTP.");

        if (data.master_bypass) {
            // Master number bypass — auto log in
            await techCompleteOtpLogin(_techOtpPhone, "000000");
            return;
        }

        // Switch to OTP code entry step
        document.getElementById("otp-step-phone").classList.add("hidden");
        document.getElementById("otp-step-code").classList.remove("hidden");
        document.getElementById("otp-sent-to").textContent = `***${_techOtpPhone.slice(-4)}`;

        if (data.dev_code) {
            const codeInput = document.getElementById("tech-otp-code");
            if (codeInput) codeInput.value = data.dev_code;
            showToast(`[DEV DEMO] OTP auto-filled: ${data.dev_code}`, "info", 5000);
        }
    } catch (err) {
        if (errBox) {
            errBox.textContent = err.message;
            errBox.classList.remove("hidden");
        }
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = "Send OTP"; }
    }
}

async function techVerifyOtp() {
    const code = (document.getElementById("tech-otp-code")?.value || "").trim();
    const errBox = document.getElementById("login-error");
    const btn = document.getElementById("btn-otp-verify");

    if (errBox) errBox.classList.add("hidden");

    if (!code || code.length < 6) {
        if (errBox) {
            errBox.textContent = "Please enter the 6-digit OTP code.";
            errBox.classList.remove("hidden");
        }
        return;
    }

    if (btn) { btn.disabled = true; btn.textContent = "Verifying..."; }
    try {
        await techCompleteOtpLogin(_techOtpPhone, code);
    } catch (err) {
        if (errBox) {
            errBox.textContent = err.message;
            errBox.classList.remove("hidden");
        }
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = "Verify & Sign In"; }
    }
}

async function techCompleteOtpLogin(phone, code) {
    const res = await fetch(`${getApiBase()}/api/v1/tech/otp/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone, code })
    });

    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Authentication failed.");
    }

    const data = await res.json();
    localStorage.setItem("kandifix_tech_token", data.token);
    currentTech = data;
    updateNavProfile();
    document.getElementById("login-modal").classList.add("hidden");
    showToast(`Welcome, ${data.name || 'Technician'}! Logged in via Phone OTP.`, "success");

    loadFaultyAppliances();
    loadRoomTickets();
}


