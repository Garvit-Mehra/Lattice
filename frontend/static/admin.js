/**
 * LATTICE · IITH Operations Console - Estate Office Super-Admin Panel Controller
 * High-Density Operations Console for Campus SLA Governance,
 * Master Ticket Overrides, and 279-Unit Appliance Infrastructure.
 */

let currentAdmin = null;
let activeAdminTab = "dashboard";
let adminHostelsList = [];
let pendingOverrideTicketId = null;
let pendingForceResolveTicketId = null;
let adminTicketsCache = [];

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
            btnElement.classList.add("text-emerald-700", "font-bold");
            setTimeout(() => {
                btnElement.innerHTML = original;
                btnElement.classList.remove("text-emerald-700", "font-bold");
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
    const techLink = document.getElementById("nav-link-tech");
    const presLink = document.getElementById("nav-link-presentation");

    if (studentLink) {
        studentLink.href = isSinglePort ? "/" : `//${window.location.hostname}:8000/`;
    }
    if (techLink) {
        techLink.href = isSinglePort ? "/tech" : `//${window.location.hostname}:8001/`;
    }
    if (presLink) {
        presLink.href = "/presentation";
    }
}

// Modal Backdrop Click & Escape Dismissal (Task 33)
document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
        closeModalForceResolve();
        closeModalOverride();
    }
});

function getAdminApiBase() {
    if (window.location.pathname.startsWith("/admin")) {
        return "/admin";
    }
    return "";
}

function getAdminAuthHeader() {
    const token = localStorage.getItem("kandifix_admin_token");
    return token ? { "Authorization": `Bearer ${token}` } : {};
}

function getHostelFloorRange(name) {
    if (["Vivekananda", "SN Bose", "Kalpana Chawla"].includes(name)) {
        return "Ground – 6";
    }
    if (["Sarojini Naidu", "Anandi Joshi", "Kalam", "Raman", "Bhabha", "Ramanujan", "Visweswaraya"].includes(name)) {
        return "1 – 10";
    }
    return "1 – 6";
}

// ==========================================
// 1. INITIALIZATION & AUTHENTICATION
// ==========================================
document.addEventListener("DOMContentLoaded", async () => {
    updateCrossPortalLinks();
    setupAdminAuthForm();
    await loadAdminHostels();
    await verifyAdminSession();
    initAdminAutoRefresh();
});

function initAdminAutoRefresh() {
    setInterval(() => {
        if (!currentAdmin) return;
        if (activeAdminTab === "dashboard") {
            loadDashboardStats();
        } else if (activeAdminTab === "tickets") {
            loadAdminTickets();
        } else if (activeAdminTab === "appliances") {
            loadAdminAppliances();
        }
    }, 15000);
}

function setupAdminAuthForm() {
    const form = document.getElementById("admin-login-form");
    if (form) {
        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            const username = document.getElementById("admin-username").value.trim();
            const password = document.getElementById("admin-password").value.trim();
            await loginAdmin(username, password);
        });
    }
}

function fillDemoAdmin(username, password) {
    document.getElementById("admin-username").value = username;
    document.getElementById("admin-password").value = password;
    loginAdmin(username, password);
}

async function loginAdmin(username, password) {
    const errBox = document.getElementById("admin-login-error");
    const submitBtn = document.getElementById("btn-admin-login-submit");
    if (errBox) errBox.classList.add("hidden");
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = "Authenticating...";
    }

    try {
        const res = await fetch(`${getAdminApiBase()}/api/v1/admin/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Invalid administrator credentials.");
        }

        const data = await res.json();
        localStorage.setItem("kandifix_admin_token", data.token);
        currentAdmin = data;
        document.getElementById("admin-login-modal").classList.add("hidden");

        // Load dashboard views
        loadDashboardStats();
        loadAdminTickets();
        loadAdminAppliances();
    } catch (err) {
        if (errBox) {
            errBox.textContent = err.message;
            errBox.classList.remove("hidden");
        }
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = "Sign In to Operations Console";
        }
    }
}

async function verifyAdminSession() {
    const token = localStorage.getItem("kandifix_admin_token");
    if (!token) {
        document.getElementById("admin-login-modal").classList.remove("hidden");
        return;
    }

    try {
        const res = await fetch(`${getAdminApiBase()}/api/v1/admin/me`, {
            headers: getAdminAuthHeader()
        });

        if (!res.ok) {
            localStorage.removeItem("kandifix_admin_token");
            document.getElementById("admin-login-modal").classList.remove("hidden");
            return;
        }

        currentAdmin = await res.json();
        document.getElementById("admin-login-modal").classList.add("hidden");
        loadDashboardStats();
        loadAdminTickets();
        loadAdminAppliances();
    } catch (err) {
        document.getElementById("admin-login-modal").classList.remove("hidden");
    }
}

async function adminLogout() {
    try {
        await fetch(`${getAdminApiBase()}/api/v1/admin/logout`, {
            method: "POST",
            headers: getAdminAuthHeader()
        });
    } catch (e) {}

    localStorage.removeItem("kandifix_admin_token");
    currentAdmin = null;
    document.getElementById("admin-login-modal").classList.remove("hidden");
}

async function loadAdminHostels() {
    try {
        let res = await fetch(`${getAdminApiBase()}/api/v1/hostels`);
        if (!res.ok) res = await fetch(`/api/v1/hostels`);
        if (res.ok) {
            adminHostelsList = await res.json();
            populateAdminHostelDropdowns();
        }
    } catch (e) {
        console.warn("Could not fetch hostel list for admin", e);
    }
}

function populateAdminHostelDropdowns() {
    const tHostel = document.getElementById("admin-ticket-hostel-filter");
    const aHostel = document.getElementById("admin-app-hostel-filter");
    const options = adminHostelsList.map(h => `<option value="${h.id}">${h.name}</option>`).join("");
    
    if (tHostel) tHostel.innerHTML = `<option value="">All 21 Hostels</option>` + options;
    if (aHostel) aHostel.innerHTML = `<option value="">All 21 Hostels</option>` + options;
}

// ==========================================
// 2. TAB SWITCHING
// ==========================================
function switchAdminTab(tab) {
    activeAdminTab = tab;
    const btnDash = document.getElementById("admin-tab-btn-dashboard");
    const btnTickets = document.getElementById("admin-tab-btn-tickets");
    const btnApps = document.getElementById("admin-tab-btn-appliances");

    const viewDash = document.getElementById("view-admin-dashboard");
    const viewTickets = document.getElementById("view-admin-tickets");
    const viewApps = document.getElementById("view-admin-appliances");

    const inactiveClass = "flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-600 hover:text-slate-900 transition";
    const activeClass = "flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-white text-slate-900 shadow-sm border border-slate-200 transition";

    btnDash.className = tab === "dashboard" ? activeClass : inactiveClass;
    btnTickets.className = tab === "tickets" ? activeClass : inactiveClass;
    btnApps.className = tab === "appliances" ? activeClass : inactiveClass;

    viewDash.classList.toggle("hidden", tab !== "dashboard");
    viewTickets.classList.toggle("hidden", tab !== "tickets");
    viewApps.classList.toggle("hidden", tab !== "appliances");

    if (tab === "dashboard") loadDashboardStats();
    if (tab === "tickets") loadAdminTickets();
    if (tab === "appliances") loadAdminAppliances();
}

// ==========================================
// 3. TAB 1: DASHBOARD & HIGH-DENSITY SLA TABLE
// ==========================================
async function loadDashboardStats() {
    try {
        const res = await fetch(`${getAdminApiBase()}/api/v1/admin/dashboard/stats`, {
            headers: getAdminAuthHeader()
        });

        if (!res.ok) {
            if (res.status === 401) {
                document.getElementById("admin-login-modal").classList.remove("hidden");
                return;
            }
            throw new Error("Failed to load dashboard metrics");
        }

        const data = await res.json();
        document.getElementById("stat-active-tickets").textContent = data.total_active_tickets;
        document.getElementById("stat-critical-tickets").textContent = data.critical_tickets;
        document.getElementById("stat-operational-pct").textContent = `${data.operational_appliance_pct}%`;
        document.getElementById("stat-avg-resolution").textContent = `${data.avg_resolution_time_hrs} hrs`;

        const badgeTotal = document.getElementById("badge-total-tickets");
        if (badgeTotal) badgeTotal.textContent = data.total_active_tickets;

        const tableBody = document.getElementById("admin-sla-table-body");
        if (tableBody && data.sla_metrics) {
            tableBody.innerHTML = data.sla_metrics.map(m => {
                const isBreached = m.avg_resolution_hours > 8.0;
                const rowHighlight = isBreached ? "bg-amber-50/60" : "hover:bg-slate-50";
                const floorRange = getHostelFloorRange(m.hostel_name);

                return `
                    <tr class="${rowHighlight} border-b border-slate-100 transition-colors">
                        <td class="font-bold text-slate-900">${m.hostel_name}</td>
                        <td class="font-mono text-slate-500">${floorRange}</td>
                        <td class="text-center font-mono font-bold ${m.open_incidents > 0 ? 'text-rose-600' : 'text-slate-500'}">
                            ${m.open_incidents}
                        </td>
                        <td class="text-center font-mono text-emerald-700 font-semibold">${m.resolved_count}</td>
                        <td class="text-center font-mono font-bold ${isBreached ? 'text-amber-700' : 'text-slate-800'}">
                            ${m.avg_resolution_hours}h
                        </td>
                        <td class="text-center">
                            ${isBreached ? `
                                <span class="inline-block px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-amber-100 text-amber-800 border border-amber-300">
                                    BREACHED (>8h)
                                </span>
                            ` : `
                                <span class="inline-block px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                    WITHIN SLA
                                </span>
                            `}
                        </td>
                    </tr>
                `;
            }).join("");
        }

    } catch (e) {
        console.error("Dashboard stats error:", e);
    }
}

// ==========================================
// 4. TAB 2: MASTER TICKET CONTROL (SUPER-ADMIN OVERRIDES)
// ==========================================
let allAdminTickets = [];

async function loadAdminTickets() {
    const tableBody = document.getElementById("admin-tickets-table-body");
    const emptyState = document.getElementById("admin-tickets-empty");
    if (!tableBody) return;

    const typeFilter = document.getElementById("admin-ticket-type-filter").value;
    const statusFilter = document.getElementById("admin-ticket-status-filter").value;
    const hostelId = document.getElementById("admin-ticket-hostel-filter").value;

    let url = `${getAdminApiBase()}/api/v1/admin/tickets?status_filter=${statusFilter}&`;
    if (typeFilter) url += `ticket_type=${typeFilter}&`;
    if (hostelId) url += `hostel_id=${hostelId}&`;

    try {
        const res = await fetch(url, { headers: getAdminAuthHeader() });
        if (!res.ok) {
            if (res.status === 401) {
                document.getElementById("admin-login-modal").classList.remove("hidden");
                return;
            }
            throw new Error("Failed to load tickets");
        }

        allAdminTickets = await res.json();
        filterAdminTicketsLive();
    } catch (err) {
        tableBody.innerHTML = `<tr><td colspan="7" class="p-6 text-center text-xs text-rose-600 font-mono">Error loading tickets: ${err.message}</td></tr>`;
    }
}

function filterAdminTicketsLive() {
    const query = (document.getElementById("admin-ticket-search-input")?.value || "").toLowerCase().trim();
    if (!query) {
        renderAdminTickets(allAdminTickets);
        return;
    }
    const filtered = allAdminTickets.filter(t => {
        const ref = (t.ticket_code || "").toLowerCase();
        const title = (t.title || "").toLowerCase();
        const desc = (t.description || "").toLowerCase();
        const hostel = (t.hostel_name || "").toLowerCase();
        const room = String(t.room_number || "").toLowerCase();
        const tech = (t.tech_assigned_to || "").toLowerCase();
        const contact = (t.reporter_contact || "").toLowerCase();
        return ref.includes(query) || title.includes(query) || desc.includes(query) ||
               hostel.includes(query) || room.includes(query) || tech.includes(query) || contact.includes(query);
    });
    renderAdminTickets(filtered);
}

function renderAdminTickets(tickets) {
    const tableBody = document.getElementById("admin-tickets-table-body");
    const emptyState = document.getElementById("admin-tickets-empty");
    if (!tableBody) return;

    if (!tickets || tickets.length === 0) {
        tableBody.innerHTML = "";
        if (emptyState) emptyState.classList.remove("hidden");
        return;
    }

    if (emptyState) emptyState.classList.add("hidden");

    tableBody.innerHTML = tickets.map(t => {
        const floorLabel = t.floor === 0 ? "Ground Floor" : `Floor ${t.floor}`;
        const isResolved = t.status === "resolved";
        const isAwaiting = t.status === "awaiting_student_verification";
        const isCritical = t.priority_tier === "CRITICAL" || (t.computed_priority || 0) >= 50.0;

        let statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-slate-100 text-slate-700 border border-slate-200 uppercase">${t.status.replace(/_/g, ' ')}</span>`;
        if (isResolved) {
            statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">RESOLVED</span>`;
        } else if (isAwaiting) {
            statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-amber-50 text-amber-700 border border-amber-200 animate-pulse">AWAITING RESIDENT</span>`;
        } else if (t.status === "in_progress") {
            statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">IN PROGRESS</span>`;
        } else if (t.status === "submitted") {
            statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-rose-50 text-rose-700 border border-rose-200">SUBMITTED</span>`;
        }

        return `
            <tr class="hover:bg-slate-50 transition-colors border-b border-slate-100">
                <!-- REF ID -->
                <td class="whitespace-nowrap">
                    <div class="flex items-center gap-1 font-mono text-xs font-bold text-slate-900">
                        <span>#${t.ticket_code}</span>
                        <button onclick="copyToClipboard('${t.ticket_code}', this)" class="text-[10px] text-slate-400 hover:text-indigo-600 transition px-1" title="Copy Ticket Reference">📋</button>
                    </div>
                    <span class="inline-block mt-0.5 px-2 py-0.2 rounded-full text-[10px] font-mono font-bold ${isCritical ? 'bg-rose-50 text-rose-700 border border-rose-200' : 'bg-slate-100 text-slate-600'}">
                        ${t.priority_tier} (${t.computed_priority})
                    </span>
                </td>

                <!-- LOCATION -->
                <td>
                    <div class="font-bold text-xs text-slate-900">${t.hostel_name}</div>
                    <div class="text-[11px] text-slate-500 font-mono">${floorLabel} • ${t.room_number ? 'Room ' + t.room_number : 'Common'}</div>
                    ${t.reporter_contact ? `<div class="text-[10px] text-slate-600 font-mono mt-0.5">Mobile: +91 ${t.reporter_contact}</div>` : ''}
                </td>

                <!-- CATEGORY -->
                <td class="whitespace-nowrap">
                    <span class="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-slate-100 text-slate-700 uppercase">
                        ${t.category}
                    </span>
                </td>

                <!-- ISSUE SUMMARY -->
                <td class="max-w-xs">
                    <div class="font-bold text-xs text-slate-900 truncate" title="${t.title}">${t.title}</div>
                    <p class="text-[11px] text-slate-500 truncate" title="${t.description}">${t.description}</p>
                    ${t.confirmations_count > 1 ? `
                        <span class="inline-block text-[10px] font-mono font-bold text-amber-600">
                            ${t.confirmations_count} resident confirmations
                        </span>
                    ` : ''}
                </td>

                <!-- STATUS -->
                <td class="whitespace-nowrap">
                    ${statusBadge}
                </td>

                <!-- ASSIGNED -->
                <td class="whitespace-nowrap text-xs font-mono text-slate-700">
                    ${t.tech_assigned_to ? `<span class="font-bold text-slate-900">${t.tech_assigned_to}</span>` : '<span class="text-slate-400 italic">— Unassigned —</span>'}
                </td>

                <!-- OVERRIDES -->
                <td class="whitespace-nowrap text-right">
                    <div class="flex items-center justify-end gap-1.5">
                        ${!isResolved ? `
                            <button onclick="openModalForceResolve(${t.id}, '${t.ticket_code}')" class="px-2.5 py-1 rounded-lg text-xs font-bold bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 transition" title="Force resolve ticket with mandatory justification code">
                                Force Resolve
                            </button>
                        ` : ''}
                        <button onclick="openModalOverride(${t.id}, '${t.ticket_code}', '${t.status}', '${t.priority_tier}', '${t.tech_assigned_to || ''}')" class="px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 transition" title="Edit priority, status, or assignment">
                            Edit
                        </button>
                        <button onclick="adminDeleteTicket(${t.id}, '${t.ticket_code}')" class="px-2 py-1 rounded-lg text-xs text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition" title="Delete Ticket">
                            Delete
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join("");
}

// ==========================================
// 5. MODAL 1: FORCE RESOLVE (MANDATORY JUSTIFICATION)
// ==========================================
function openModalForceResolve(ticketId, code) {
    pendingForceResolveTicketId = ticketId;
    document.getElementById("modal-force-resolve-code").textContent = `Ticket Reference: #${code}`;
    document.getElementById("force-resolve-reason-code").selectedIndex = 0;
    document.getElementById("force-resolve-notes").value = "";
    document.getElementById("modal-force-resolve").classList.remove("hidden");
}

function closeModalForceResolve() {
    pendingForceResolveTicketId = null;
    document.getElementById("modal-force-resolve").classList.add("hidden");
}

async function submitForceResolve() {
    if (!pendingForceResolveTicketId) return;
    const reasonCode = document.getElementById("force-resolve-reason-code").value;
    const notes = document.getElementById("force-resolve-notes").value.trim();
    const finalReason = notes ? `${reasonCode} - ${notes}` : reasonCode;

    try {
        const res = await fetch(`${getAdminApiBase()}/api/v1/admin/tickets/${pendingForceResolveTicketId}/override`, {
            method: "PATCH",
            headers: {
                "Content-Type": "application/json",
                ...getAdminAuthHeader()
            },
            body: JSON.stringify({
                force_resolve: true,
                override_reason: finalReason
            })
        });

        if (res.ok) {
            closeModalForceResolve();
            showToast("Ticket force-resolved successfully.", "success");
            loadAdminTickets();
            loadDashboardStats();
        } else {
            const err = await res.json();
            showToast("Error: " + (err.detail || "Failed to force resolve ticket."), "error");
        }
    } catch (e) {
        showToast("Error: " + e.message, "error");
    }
}

// ==========================================
// 6. MODAL 2: SUPER-ADMIN TICKET OVERRIDE & EDIT
// ==========================================
function openModalOverride(ticketId, code, status, priority, tech) {
    pendingOverrideTicketId = ticketId;
    document.getElementById("modal-override-ticket-code").textContent = `Ticket Reference: #${code}`;
    document.getElementById("override-status-select").value = status;
    document.getElementById("override-priority-select").value = priority || "KEEP";
    document.getElementById("override-tech-name").value = tech;
    document.getElementById("override-reason").value = "";
    document.getElementById("modal-ticket-override").classList.remove("hidden");
}

function closeModalOverride() {
    pendingOverrideTicketId = null;
    document.getElementById("modal-ticket-override").classList.add("hidden");
}

async function submitTicketOverride() {
    if (!pendingOverrideTicketId) return;
    const status = document.getElementById("override-status-select").value;
    const prioVal = document.getElementById("override-priority-select").value;
    const tech = document.getElementById("override-tech-name").value.trim();
    const reason = document.getElementById("override-reason").value.trim();

    let computedPriority = undefined;
    if (prioVal === "CRITICAL") computedPriority = 95.0;
    else if (prioVal === "HIGH") computedPriority = 75.0;
    else if (prioVal === "MEDIUM") computedPriority = 50.0;
    else if (prioVal === "LOW") computedPriority = 20.0;

    try {
        const res = await fetch(`${getAdminApiBase()}/api/v1/admin/tickets/${pendingOverrideTicketId}/override`, {
            method: "PATCH",
            headers: {
                "Content-Type": "application/json",
                ...getAdminAuthHeader()
            },
            body: JSON.stringify({
                status: status,
                computed_priority: computedPriority,
                tech_assigned_to: tech || undefined,
                override_reason: reason || "Estate Office Administrative Override"
            })
        });

        if (res.ok) {
            closeModalOverride();
            showToast("Ticket overrides applied successfully.", "success");
            loadAdminTickets();
            loadDashboardStats();
        } else {
            const err = await res.json();
            showToast("Error: " + (err.detail || "Failed to override ticket"), "error");
        }
    } catch (e) {
        showToast("Failed to apply override: " + e.message, "error");
    }
}

async function adminDeleteCurrentTicket() {
    if (!pendingOverrideTicketId) return;
    if (!confirm("Are you sure you want to permanently delete this ticket?")) return;
    await adminDeleteTicket(pendingOverrideTicketId, "");
    closeModalOverride();
}

async function adminDeleteTicket(ticketId, code) {
    if (code && !confirm(`Permanently delete ticket #${code}?`)) return;

    try {
        const res = await fetch(`${getAdminApiBase()}/api/v1/admin/tickets/${ticketId}`, {
            method: "DELETE",
            headers: getAdminAuthHeader()
        });

        if (res.ok) {
            showToast("Ticket deleted successfully.", "success");
            loadAdminTickets();
            loadDashboardStats();
        } else {
            showToast("Failed to delete ticket.", "error");
        }
    } catch (e) {
        showToast("Error deleting ticket: " + e.message, "error");
    }
}

// ==========================================
// 7. TAB 3: 279 APPLIANCES MASTER MATRIX (4-COLUMN CARD GRID)
// ==========================================
async function loadAdminAppliances() {
    const grid = document.getElementById("admin-appliances-grid");
    if (!grid) return;

    const hostelId = document.getElementById("admin-app-hostel-filter").value;
    const assetType = document.getElementById("admin-app-type-filter").value;
    const status = document.getElementById("admin-app-status-filter").value;

    let url = `${getAdminApiBase()}/api/v1/admin/appliances?`;
    if (hostelId) url += `hostel_id=${hostelId}&`;
    if (assetType) url += `asset_type=${assetType}&`;
    if (status) url += `status=${status}&`;

    try {
        const res = await fetch(url, { headers: getAdminAuthHeader() });
        if (!res.ok) {
            if (res.status === 401) {
                document.getElementById("admin-login-modal").classList.remove("hidden");
                return;
            }
            throw new Error("Failed to load appliances");
        }

        const apps = await res.json();
        if (apps.length === 0) {
            grid.innerHTML = `<div class="col-span-full p-8 text-center text-slate-500 bg-white border border-slate-200 rounded-xl">No appliances match the filter.</div>`;
            return;
        }

        grid.innerHTML = apps.map(a => {
            const isCooler = a.asset_type === "water_cooler";
            const icon = isCooler ? "WC" : "WM";
            const floorLabel = a.floor === 0 ? "Ground Floor" : `Floor ${a.floor}`;

            let statusPill = `<span class="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">OPERATIONAL</span>`;
            if (a.status === "faulty") statusPill = `<span class="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-rose-50 text-rose-700 border border-rose-200">FAULTY</span>`;
            else if (a.status === "in_progress") statusPill = `<span class="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">IN PROGRESS</span>`;
            else if (a.status === "out_of_order") statusPill = `<span class="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-slate-100 text-slate-700 border border-slate-200">OUT OF ORDER</span>`;

            return `
                <div class="bg-white rounded-xl p-4 border border-slate-200 shadow-xs flex flex-col justify-between space-y-3 hover:border-slate-300 transition-colors">
                    <div class="space-y-1.5">
                        <div class="flex items-start justify-between gap-2">
                            <div class="flex items-center gap-2.5">
                                <span class="text-xl"><span class="text-xs font-mono font-bold text-slate-700">${icon}</span></span>
                                <div>
                                    <h4 class="text-xs font-bold text-slate-900">${a.asset_label}</h4>
                                    <p class="text-[11px] text-slate-500">${a.hostel_name} • ${floorLabel}</p>
                                </div>
                            </div>
                            ${statusPill}
                        </div>
                        <p class="text-[11px] text-slate-600 truncate" title="${a.location_desc}">${a.location_desc}</p>
                    </div>

                    <!-- Direct Status Selector with Zero-Latency Mutation -->
                    <div class="pt-2.5 border-t border-slate-100 flex items-center justify-between text-xs">
                        <span class="text-[10px] text-slate-500 font-mono font-bold uppercase">STATUS:</span>
                        <select onchange="updateApplianceStatusDirect(${a.id}, this.value)" class="bg-slate-50 border border-slate-300 text-[11px] text-slate-800 rounded-md px-2 py-1 outline-none font-medium">
                            <option value="operational" ${a.status === 'operational' ? 'selected' : ''}>Operational</option>
                            <option value="faulty" ${a.status === 'faulty' ? 'selected' : ''}>Faulty</option>
                            <option value="in_progress" ${a.status === 'in_progress' ? 'selected' : ''}>In Progress</option>
                            <option value="out_of_order" ${a.status === 'out_of_order' ? 'selected' : ''}>Out of Order</option>
                        </select>
                    </div>
                </div>
            `;
        }).join("");

    } catch (e) {
        grid.innerHTML = `<div class="col-span-full p-4 text-rose-600 text-xs">Error loading appliances: ${e.message}</div>`;
    }
}

async function updateApplianceStatusDirect(applianceId, newStatus) {
    try {
        const res = await fetch(`${getAdminApiBase()}/api/v1/admin/appliances/${applianceId}/status`, {
            method: "PATCH",
            headers: {
                "Content-Type": "application/json",
                ...getAdminAuthHeader()
            },
            body: JSON.stringify({ status: newStatus })
        });

        if (res.ok) {
            showToast("Appliance status updated.", "success");
            loadDashboardStats();
            loadAdminAppliances();
        } else {
            showToast("Failed to update appliance status.", "error");
        }
    } catch (e) {
        showToast("Error updating status: " + e.message, "error");
    }
}

// ==========================================
// 8. RESEED DEMO DATA
// ==========================================
async function reseedDatabase() {
    if (!confirm("Reseed demo data across campus? This will refresh all active test tickets and status indicators.")) return;

    try {
        const res = await fetch(`${getAdminApiBase()}/api/v1/admin/reseed`, {
            method: "POST",
            headers: getAdminAuthHeader()
        });

        if (res.ok) {
            showToast("Database reseeded successfully with realistic IITH sample incidents!", "success");
            loadDashboardStats();
            loadAdminTickets();
            loadAdminAppliances();
        } else {
            showToast("Failed to reseed database.", "error");
        }
    } catch (e) {
        showToast("Error reseeding: " + e.message, "error");
    }
}
