# LATTICE · IITH Operations Console — Engineering Fixes & Improvements TODO

This document tracks all identified bugs, missing functionality, architectural flaws, and UX improvements discovered during the system audit of the MILAN 2026 Lambda Hackathon codebase.

---

## 🚨 Priority 0: Critical Bugs & Missing Endpoints (Demo Breaking)

- [x] **1. Implement Missing `POST /api/v1/admin/reseed` Endpoint**
  - **Files:** `backend/admin_app.py`, `frontend/admin/static/admin.js`, `frontend/admin/index.html`
  - **Issue:** The Admin UI has a "Reseed Demo Data" button (`admin.js:L625`), and `README.md:L78` advertises a 1-click reseed demo button, but `backend/admin_app.py` has no `/api/v1/admin/reseed` route. Triggering it returns a `404 Not Found` error.
  - **Fix:** Add `@app.post("/api/v1/admin/reseed")` in `backend/admin_app.py` guarded by `get_current_admin`. Call `seed_database()` from `backend.seed_data` and return clean success status.

- [x] **2. Fix Category Disconnect Hiding Benchmark Ticket `#LAT-8921` (`civil` vs `carpentry`)**
  - **Files:** `backend/models.py`, `backend/scoring.py`, `backend/tech_app.py`, `backend/admin_app.py`, `frontend/index.html`, `frontend/technician/index.html`
  - **Issue:** The student form (`index.html:L185`) submits category `civil`, and the technician filter (`technician/index.html:L198`) filters by `civil`. However, all database seed tickets (including the benchmark `#LAT-8921`) use `carpentry`, `models.py:L53` specifies `carpentry`, and `scoring.py` lacks a `civil` key. Consequently, selecting "Furniture / Civil" in the technician portal displays 0 tickets and completely hides benchmark ticket `#LAT-8921`.
  - **Fix:** Normalize `civil` and `carpentry` as aliases across `backend/scoring.py`, backend filters in `tech_app.py` and `admin_app.py`, and frontend dropdowns.

- [x] **3. Fix Admin Priority Overrides Being Erased on Subsequent Requests**
  - **Files:** `backend/models.py`, `backend/admin_app.py`, `backend/tech_app.py`, `backend/student_app.py`
  - **Issue:** When an admin overrides ticket priority via `admin_override_ticket()` (`admin_app.py:L301`), `enrich_ticket_data()` unconditionally recalculates priority for any ticket where `status != "resolved"` on subsequent queries. This instantly overwrites the admin's override back to the dynamic formula score.
  - **Fix:** Add `priority_overridden = Column(Boolean, default=False)` to the `Ticket` ORM model. When an admin updates priority, set `priority_overridden = True`. In `enrich_ticket_data()`, respect the override and do not recalculate.

- [x] **4. Fix Appliance State Not Resetting on Admin Standard Ticket Resolve**
  - **Files:** `backend/admin_app.py`
  - **Issue:** In `admin_app.py:L282-L300`, `force_resolve` properly resets `ticket.appliance.status = "operational"` and `active_ticket_id = None`. However, the standard `elif req.status == "resolved"` branch omits updating `ticket.appliance`, leaving the appliance stuck in `faulty` or `out_of_order` state even after the ticket is closed.
  - **Fix:** Ensure any transition of a ticket to `resolved` (via standard override or force resolve) resets `ticket.appliance.status = "operational"` and clears `ticket.appliance.active_ticket_id`.

- [x] **5. Prevent Appliance Deadlock when Mutating Status Directly in Admin Matrix**
  - **Files:** `backend/admin_app.py`, `backend/student_app.py`, `frontend/static/app.js`
  - **Issue:** When an admin changes an appliance status from `operational` to `faulty` or `out_of_order` in the 279-Appliance Matrix (`admin_app.py:L390-L410`), no active ticket is attached. If a student tries to click "+1 Confirm Broken", `student_app.py:L218` raises `404 No active incident found for this appliance`.
  - **Fix:** Either automatically spawn an administrative ticket when an admin marks an appliance broken, or update `confirm_appliance_issue()` to automatically generate an incident if an appliance is already marked broken without an active ticket.

- [x] **19. [PRA-SEC-001] Remove Hardcoded Credentials & Support Secure Environment Overrides**
  - **Files:** `backend/auth.py`
  - **Issue:** Static credentials (`technician123`, `admin123`) were hardcoded directly in `backend/auth.py:L18`. Any entity with access to the source code could authenticate as campus super-admin and modify all hostel and ticket data.
  - **Fix:** Added support for environment variable overrides (`ADMIN_PASSWORD`, `TECH_PASSWORD`, `IITH_ADMIN_PASSWORD`, `IITH_TECH_PASSWORD`) with constant-time `hmac.compare_digest` validation and security warnings in production mode.

- [x] **20. [PRA-SEC-002] Restrict Permissive CORS Configuration with Explicit Origins**
  - **Files:** `backend/student_app.py`, `backend/tech_app.py`, `backend/admin_app.py`
  - **Issue:** `CORSMiddleware` was configured with `allow_origins=['*']` alongside `allow_credentials=True` across all three apps (`student_app.py:35`, `tech_app.py:32`, `admin_app.py:34`). This is an invalid/insecure specification in modern browsers and creates cross-origin vulnerabilities for authenticated endpoints.
  - **Fix:** Restricted `allow_origins` to explicit trusted campus origins (`http://localhost:8000`, `http://localhost:8001`, `http://localhost:8002`, `http://127.0.0.1:*`, and `*.iith.ac.in`) with regex matching and environment extension.

---

## ⚙️ Priority 1: Architecture & Concurrency Hardening

- [x] **6. Mount `/tech` and `/admin` Sub-Apps on Port 8000 (`student_app.py`)**
  - **Files:** `backend/student_app.py`, `backend/main.py`
  - **Issue:** `tech.js` and `admin.js` check `window.location.pathname.startsWith('/tech')` and `startsWith('/admin')` to support single-port operation. However, `start.sh` runs `student_app:app` on port 8000, which lacks the sub-mounts present in the older `main.py`. Accessing `http://localhost:8000/tech` returns 404.
  - **Fix:** Mount `tech_fastapi_app` at `/tech` and `admin_fastapi_app` at `/admin` directly inside `student_app.py`. This ensures full support for both multi-port (`8000`, `8001`, `8002`) and unified single-port (`8000`) access.

- [x] **7. [PRA-BE-001] Persist Authentication Sessions Across Processes and Server Reloads**
  - **Files:** `backend/auth.py`, `backend/models.py`, `backend/database.py`
  - **Issue:** Authentication tokens were stored in an in-memory dictionary `ACTIVE_SESSIONS = {}`. Because each backend runs in a separate OS process, admin sessions created on port 8002 could not access technician endpoints on port 8001. Additionally, uvicorn `--reload` cleared all sessions on every reload.
  - **Fix:** Stored sessions in a lightweight SQLite table (`auth_sessions`) with fast fallback so all micro-portals share authentication state seamlessly.

- [x] **8. Deprecate or Sync Outdated `backend/main.py` with `student_app.py`**
  - **Files:** `backend/main.py`, `backend/student_app.py`
  - **Issue:** `backend/main.py` is a monolithic duplicate of `student_app.py` that drifted out of sync during recent updates (missing recent analytics and slide routes).
  - **Fix:** Clean up or re-export `main.py` to route to `student_app.py` to eliminate codebase divergence.

- [x] **21. [PRA-SEC-003] Enforce Session Token Expiration & TTL Checks**
  - **Files:** `backend/auth.py`, `backend/models.py`
  - **Issue:** Tokens in `AuthSession` did not store an expiration timestamp or enforce a maximum lifespan. A compromised or leaked token remained valid indefinitely.
  - **Fix:** Added `expires_at` column to `AuthSession` with configurable TTL (`SESSION_TTL_HOURS = 12`), enforced expiration checks during verification, and automatically pruned expired sessions.

- [x] **22. [PRA-SEC-004] Request Rate Limiting / Abuse Throttling for Public Endpoints**
  - **Files:** `backend/student_app.py`
  - **Issue:** Anonymous public endpoints for ticket creation (`POST /api/v1/tickets`) and crowd confirmation (`POST /api/v1/appliances/{id}/confirm`) had no rate limiting, allowing script flooding or artificial priority inflation.
  - **Fix:** Added in-memory sliding-window abuse rate limiter per client IP returning HTTP 429 Too Many Requests when thresholds are exceeded.

---

## 🛡️ Priority 2: Security & Workflow Logic Enhancements

- [x] **9. Add Confirmation & Throttling to Anonymous 1-Click "Report Working" (`resolve-crowd`)**
  - **Files:** `backend/student_app.py`, `frontend/static/app.js`
  - **Issue:** Any anonymous user could trigger `POST /api/v1/appliances/{id}/resolve-crowd` with a single tap, immediately closing community tickets without confirmation.
  - **Fix:** Added confirmation check in `frontend/static/app.js`, rate limiting (20/min per IP), and audit trail notes attached to resolved tickets in `backend/student_app.py`.

- [x] **10. Escalate Priority on Student Rejection (`verified = False`)**
  - **Files:** `backend/student_app.py`, `backend/scoring.py`, `frontend/static/app.js`
  - **Issue:** When a student rejected a repair by clicking "No, Still Broken", the ticket reverted to `in_progress`, but its priority score did not escalate, risking infinite unaddressed repair loops.
  - **Fix:** Added priority escalation penalty (+15 points, guaranteed `CRITICAL >= 50.0`), tagged feedback with `[REJECTED WORK - REOPENED]`, and prevented premature resident verification before technician Step 1 completion.

- [x] **11. Indian Mobile Number & Contact Validation on Room Ticket Submission**
  - **Files:** `backend/student_app.py`, `frontend/static/app.js`
  - **Issue:** The backend previously accepted arbitrary strings or non-digits for contacts.
  - **Fix:** Enforced standard 10-digit Indian mobile number validation (regex `^[6-9]\d{9}$`) and `@iith.ac.in` campus email validation on both frontend and backend.

- [x] **12. Validate Room Number Range Against Hostel Floor Configuration**
  - **Files:** `backend/student_app.py`, `frontend/static/app.js`
  - **Issue:** The backend API accepted arbitrary room strings and impossible floor numbers (e.g. floor 99 on a 6-floor hostel).
  - **Fix:** Enforced strict floor boundaries (`0 <= floor <= hostel.total_floors` with ground-floor support) and non-empty room validation in `backend/student_app.py`.

- [x] **23. [PRA-DB-002] Set SQLite Busy Timeout to Prevent Database Lock Timeouts**
  - **Files:** `backend/database.py`
  - **Issue:** SQLite default busy timeout can cause `sqlite3.OperationalError: database is locked` under concurrent requests across the student, technician, and admin processes.
  - **Fix:** Configured `connect_args={"timeout": 15, "check_same_thread": False}` and `PRAGMA busy_timeout=15000` with WAL mode in `backend/database.py`.

- [x] **24. [PRA-BE-002] Implement Structured JSON Logging with Request Tracing**
  - **Files:** `backend/student_app.py`, `backend/tech_app.py`, `backend/admin_app.py`
  - **Issue:** Microservices used raw `print()` statements, making it impossible to correlate requests or parse logs with modern observability platforms.
  - **Fix:** Added `security_and_logging_middleware` to all three microservices generating structured JSON records with request correlation IDs (`x-request-id`), HTTP verbs, status codes, and execution latency.

- [x] **25. [PRA-FE-001] Secure Authentication Token Storage**
  - **Files:** `frontend/technician/static/tech.js`, `frontend/admin/static/admin.js`, `backend/student_app.py`, `backend/tech_app.py`, `backend/admin_app.py`
  - **Issue:** Bearer tokens stored in browser storage require defense-in-depth protection against script injection.
  - **Fix:** Added security response headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`) and strict origin whitelisting across all microservices.

- [x] **26. [PRA-OPS-001] GitHub Actions Automated CI Pipeline Workflow**
  - **Files:** `.github/workflows/test.yml`
  - **Issue:** No continuous integration pipeline existed to run tests on push/pull requests.
  - **Fix:** Created `.github/workflows/test.yml` automating dependency installation and executing all multi-portal test suites on Python 3.11.

- [x] **27. [PRA-OPS-002] Containerization with Dockerfile and Docker Compose**
  - **Files:** `Dockerfile`, `docker-compose.yml`
  - **Issue:** Deploying the multi-service architecture required manual environment setup.
  - **Fix:** Added multi-stage `Dockerfile` and `docker-compose.yml` orchestrating all ports (8000, 8001, 8002) with container healthchecks.

- [x] **28. [PRA-DB-001] Database Schema Migration Framework (Alembic Setup)**
  - **Files:** `alembic.ini`, `alembic/`
  - **Issue:** SQLite database lacked systematic migration tracking.
  - **Fix:** Initialized `alembic.ini` and `alembic/env.py` linked to SQLAlchemy `Base.metadata`.

- [x] **29. [PRA-QA-001] Performance Benchmark & Concurrent Load Testing Script**
  - **Files:** `tests/load_test.py`
  - **Issue:** No automated load tests verified system behavior under peak concurrent complaint volume.
  - **Fix:** Implemented `tests/load_test.py` benchmarking 50 concurrent resident sessions (250 operations) with sub-second latency and 100% success rate.

---

## 🎨 Priority 3: UI/UX & Real-Time Polish

- [x] **13. Fix Inconsistent "Critical" Priority Thresholds Across Frontends**
  - **Files:** `frontend/admin/static/admin.js`, `frontend/technician/static/tech.js`, `backend/scoring.py`
  - **Issue:** `scoring.py` defines `CRITICAL >= 50.0`, but `admin.js` and `tech.js` checked `isCritical = score > 80`. Because scores rarely exceed 80, the critical pulsing animations and badges were virtually never shown.
  - **Fix:** Updated frontend checks to `t.priority_tier === 'CRITICAL' || (t.computed_priority || 0) >= 50.0` across technician and admin views.

- [x] **14. Distinct Visual Indicator for `out_of_order` vs `faulty` on Student Matrix**
  - **Files:** `frontend/static/app.js`, `frontend/static/styles.css`
  - **Issue:** When an appliance receives 3+ confirmations, it transitions to `out_of_order`, but `app.js` rendered both `faulty` and `out_of_order` as identical `● FAULTY` badges.
  - **Fix:** Rendered distinct badges: amber `● FAULTY (Reported)` vs rose/red `● OUT OF ORDER (Decommissioned)`.

- [x] **15. Voter Token Feedback on "+1 Confirm Broken"**
  - **Files:** `frontend/static/app.js`
  - **Issue:** After a student clicked "+1 Confirm Broken", the backend deduplicated repeat clicks from the same `user_token`, but the UI did not disable the button or show "Confirmed ✓".
  - **Fix:** Persisted confirmed ticket IDs in `localStorage` and displayed "Confirmed ✓" on the button to prevent resident confusion.

- [x] **16. Add Non-Intrusive Auto-Refresh / Live Poll Interval**
  - **Files:** `frontend/static/app.js`, `frontend/technician/static/tech.js`, `frontend/admin/static/admin.js`
  - **Issue:** Users sitting on any of the three portals had to manually reload the page to see live updates from other users or technicians.
  - **Fix:** Added a 15-second background refresh interval with a visual "Live Sync" pulsing indicator dot in the header across all three portals.

- [x] **17. Pitch Deck Direct Portal Links & Shortcut Navigation**
  - **Files:** `presentation/index.html`
  - **Issue:** Slide 10 had a generic link to `/`, but lacked quick-launch links to the Technician Portal (`:8001`), Estate Admin (`:8002`), and the benchmark ticket `#LAT-8921`.
  - **Fix:** Added direct navigation chips on Slide 10 with dynamic link resolution to launch any portal or jump directly to `#LAT-8921`.

- [x] **30. [PRA-QA-002] End-to-End Multi-Portal Browser Test Suite**
  - **Files:** `tests/test_e2e_playwright.py`
  - **Issue:** No automated browser test validated the complete student filing $\to$ technician resolution $\to$ resident SMS verification cycle across UI viewports.
  - **Fix:** Added `tests/test_e2e_playwright.py` testing the complete cross-portal lifecycle and UI validation via Playwright.

- [x] **31. Non-Blocking Toast Notification System (Replace Native `alert()`)**
  - **Files:** `frontend/static/app.js`, `frontend/technician/static/tech.js`, `frontend/admin/static/admin.js`, `frontend/static/styles.css`
  - **Issue:** Over 25 calls to synchronous, native browser `alert()` dialogs froze browser tabs and degraded the user experience during reporting, resolution, and error handling.
  - **Fix:** Built a sleek, animated toast notification component (Success, Error, Info) that pops up unobtrusively in the top-right corner, replacing all `alert()` dialogs.

- [x] **32. Dynamic Cross-Portal Navigation Links (Break Out of Hardcoded `localhost:800x`)**
  - **Files:** `frontend/index.html`, `frontend/technician/index.html`, `frontend/admin/index.html`
  - **Issue:** Navigation headers hardcoded links to `http://localhost:8000/`, `http://localhost:8001/`, and `http://localhost:8002/`. When running on remote hosts, custom hostnames, or via single-port sub-mounts (`/tech`, `/admin`), these links navigated to dead endpoints.
  - **Fix:** Dynamically resolved navigation links: automatically detects single-port mode (`/tech`, `/admin`) or preserves active hostname while switching ports.

- [x] **33. Modal Backdrop Click & `Escape` Key Dismissal**
  - **Files:** `frontend/static/app.js`, `frontend/technician/static/tech.js`, `frontend/admin/static/admin.js`
  - **Issue:** Modals (such as report broken, work completion, admin override, and login modals) did not listen for the `Escape` key and could not be closed by clicking the dimmed backdrop overlay.
  - **Fix:** Attached global `Escape` key listeners and overlay click handlers to all modal dialogs.

- [x] **34. Keyboard Enter Key Submission & Quick-Demo Chip on Ticket Lookup**
  - **Files:** `frontend/index.html`, `frontend/static/app.js`
  - **Issue:** In the Student Portal, pressing the `Enter` key inside `#ticket-lookup-input` did not trigger ticket search; users were forced to click the "Fetch" button. Furthermore, testing the benchmark ticket `#LAT-8921` required manually typing the string.
  - **Fix:** Added an `Enter` key event listener and 1-click chips `[#LAT-8921 (Benchmark)]` and `[#LAT-6040]` that automatically populate the input and execute `lookupTicket()`.

- [x] **35. 1-Click Copy-to-Clipboard for Ticket References**
  - **Files:** `frontend/static/app.js`, `frontend/technician/static/tech.js`, `frontend/admin/static/admin.js`
  - **Issue:** Ticket codes (e.g. `#LAT-8921`) were displayed as raw text, requiring students and administrators to manually highlight and copy them.
  - **Fix:** Added a 1-click "📋 Copy" button with transient visual feedback next to all ticket reference badges.

- [x] **36. Real-Time Search Filter in Technician and Admin Master Ticket Lists**
  - **Files:** `frontend/technician/static/tech.js`, `frontend/admin/static/admin.js`, `frontend/admin/index.html`, `frontend/technician/index.html`
  - **Issue:** Admins and technicians could only filter by dropdown menus. There was no real-time search input to quickly locate a ticket by reference ID (e.g. `8921`), resident name, room number, or symptom keyword.
  - **Fix:** Added instant client-side search filter inputs above the ticket tables for live text filtering without extra server queries.

- [x] **37. Inline Form Validation & Error Feedback on Complaint Submission**
  - **Files:** `frontend/static/app.js`, `frontend/index.html`
  - **Issue:** When submitting a room complaint with an invalid phone number or missing description, the form triggered a jarring browser alert rather than highlighting the specific invalid fields.
  - **Fix:** Added visual field validation states (`border-rose-500`, inline helper message) on room complaint and appliance report forms that automatically clear on user typing.

- [x] **38. Unify Status Badge Color Palette Across All Portals**
  - **Files:** `frontend/static/app.js`, `frontend/technician/static/tech.js`, `frontend/admin/static/admin.js`
  - **Issue:** Status color tokens were inconsistent across portals: `out_of_order` was rendered as grey in Admin but red in Student; `awaiting_verification` pulsed in Admin but was static in Student.
  - **Fix:** Unified design tokens across all 3 portals:
    - `OPERATIONAL`: Emerald green (`bg-emerald-50 text-emerald-700 border-emerald-200`)
    - `FAULTY`: Amber/Orange (`bg-amber-50 text-amber-700 border-amber-200`)
    - `OUT_OF_ORDER`: Rose/Red (`bg-rose-50 text-rose-700 border-rose-200`)
    - `IN_PROGRESS`: Indigo/Blue (`bg-indigo-50 text-indigo-700 border-indigo-200`)
    - `AWAITING_VERIFICATION`: Pulsing Amber (`bg-amber-50 text-amber-800 border-amber-300 animate-pulse`)
    - `RESOLVED`: Emerald green with checkmark badge.

---

## 🧪 Priority 4: Test Suite & Verification Expansion

- [x] **18. Expand Automated Integration Test Suite (`tests/test_api.py`)**
  - **Files:** `tests/test_api.py`
  - **Covered Tests Added:**
    - Test `POST /api/v1/admin/reseed` endpoint resets data cleanly.
    - Test admin priority override persistence across multiple reads.
    - Test category filtering works for both `carpentry` and `civil` aliases and locates benchmark `#LAT-8921`.
    - Test student verification rejection (`verified: False`) escalates priority and reopens ticket.
    - Test appliance state transitions when modified directly through admin endpoints.
    - Test phone number format validation.

---

## Progress Summary

| Priority | Total Tasks | Completed | Remaining |
| :--- | :---: | :---: | :---: |
| **P0: Critical Bugs & Security Blockers** | 7 | 7 | 0 |
| **P1: Architecture, Concurrency & Security** | 5 | 5 | 0 |
| **P2: Workflow Logic, DevOps & Technical Debt** | 11 | 11 | 0 |
| **P3: UI/UX, QoL Polish & E2E Testing** | 14 | 14 | 0 |
| **P4: Test Suite Expansion** | 1 | 1 | 0 |
| **Total** | **38** | **38** | **0** |
