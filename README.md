# LATTICE · IITH Operations Console
**Event:** MILAN 2026 Lambda Hackathon  
**Theme:** Smart Campus Solutions for IIT Hyderabad (IITH)  
**Submission:** Final Evaluation & Presentation Build  
**Benchmark Ticket Reference:** `#LAT-8921`

---

## 1. Executive Summary & Ground Reality at IITH
At IIT Hyderabad, hostel facility maintenance and appliance downtime (washing machines and water coolers) is a constant, frustrating bottleneck:
1. **The Bureaucratic Loop:** Broken fixtures currently require complaining in WhatsApp groups, begging Hostel Representatives (HRs) to send emails, or writing in physical paper registers that languish for weeks without accountability.
2. **Duplicate Spam vs. Lost Tickets:** When a common water cooler breaks, the Estate Office receives 20 scattered, angry emails with zero coordination, or worse, none at all because students assume someone else emailed.
3. **The "Laundry Gamble":** Students haul heavy laundry bags down multiple floors only to discover machines are broken, occupied with abandoned clothes, or out-of-order.
4. **"Phantom Fixes":** Technicians close maintenance complaints without checking with the student in the room, leading to unresolved defects marked as "resolved".

**LATTICE · IITH Operations Console** solves this by converting campus maintenance into a real-time, crowd-triaged network powered by a **mathematical priority escalation algorithm** and a **binding 2-step verification contract**.

---

## 2. Multi-Portal Architecture & 3 Dedicated Micro-Backends

LATTICE operates on **three distinct backends** connected concurrently to the same high-performance SQLite database (configured with **WAL mode** and `PRAGMA busy_timeout=10000` for zero-lock concurrency across student, technician, and administrative operations):

```
                                  ┌────────────────────────────────┐
                                  │   Shared SQLite Database       │
                                  │   (kandifix.db with WAL mode)  │
                                  └──────────────┬─────────────────┘
                   ┌─────────────────────────────┼─────────────────────────────┐
                   ▼                             ▼                             ▼
       ┌───────────────────────┐    ┌───────────────────────┐    ┌───────────────────────────┐
       │   Student Backend     │    │  Technician Backend   │    │    Estate Admin Backend   │
       │   (Port 8000)         │    │  (Port 8001)          │    │    (Port 8002)            │
       │   NO LOGIN REQUIRED   │    │  LOGIN REQUIRED       │    │    LOGIN REQUIRED         │
       └───────────┬───────────┘    └───────────┬───────────┘    └─────────────┬─────────────┘
                   │                             │                             │
                   ▼                             ▼                             ▼
       ┌───────────────────────┐    ┌───────────────────────┐    ┌───────────────────────────┐
       │ Common Facilities  │    │ Washing & Coolers  │    │ Campus KPI Overview    │
       │ Room Maintenance   │    │ Room Queries       │    │ Hostel SLA Scoreboard  │
       │ Status Tracker     │    │ Step 1 Tech Repair │    │ Master Ticket Control  │
       │ Step 2 Verification │    │ (Does NOT disappear   │    │ 279 Appliance Matrix   │
       │ (Ticket #LAT-xxxx)    │    │  until student signs) │    │ Super-Admin Overrides  │
       └───────────────────────┘    └───────────────────────┘    └───────────────────────────┘
```

### 1. Student Portal (Port 8000 / Public — No Login)
* **URL:** [http://localhost:8000/](http://localhost:8000/)
* **Access:** Frictionless public access without sign-in barriers.
* **Key Capabilities:**
  - View real-time status of 279 campus washing machines & water coolers across all 21 hostels.
  - Report broken appliances & 1-tap **"+1 Confirm Broken"** crowd voting.
  - Lodge personal room maintenance complaints (Hostel, Floor, Room Number auto-detection) with **mandatory mobile phone number**.
  - Track ticket progress using reference code (e.g. `Ticket Reference: #LAT-8921`).
  - **Step 2 of 2-Step Verification:** Prompted to verify technician repairs in their room (*Confirm Done* vs *Still Broken*).

### 2. Technician Portal (Port 8001 / Operations — Login Required)
* **URL:** [http://localhost:8001/](http://localhost:8001/)
* **Credentials:**
  - Username: `technician` | Password: `tech123` (or `tech_electrical`, `tech_plumbing`, `tech_carpentry`)
  - 1-Click Fast Auth buttons built directly into the login modal.
* **Key Capabilities:**
  - **Tab 1 (Common Appliances):** Prioritized list of broken washing machines and water coolers ranked by student confirmations and severity score.
  - **Tab 2 (Room Maintenance Queries):** Filter room requests by hostel, category, and status.
  - **Step 1 of 2-Step Verification:** Technicians log physical work completed with notes and replacement parts (`tech_completed = True`).
  - **Automated SMS Dispatch:** Triggers instant SMS alert simulation to the resident's mobile number (`[SMS Alert Dispatched to 9848011223 at 14:15]: LATTICE: Tech completed repairs...`). Ticket transitions to `awaiting_student_verification` and **remains in duty queue**.

### 3. Estate Office Admin Panel (Port 8002 / Super-Admin — Login Required)
* **URL:** [http://localhost:8002/](http://localhost:8002/)
* **Credentials:**
  - Username: `admin` | Password: `admin123` (or `estate_admin` / `admin123`)
  - 1-Click Fast Auth buttons built into login modal.
* **Key Capabilities:**
  - **Live Campus KPIs:** Active incidents, critical tickets, overall appliance health rate (%), average SLA turnaround.
  - **21-Hostel SLA Scoreboard:** Continuous tracking of repair turnaround times across all 21 hostel blocks.
  - **Master Ticket Overrides:** Change priority, reassign technicians, force-resolve tickets (with mandatory justification audit reason), or delete spam.
  - **279-Appliance Infrastructure Matrix:** Real-time monitoring and direct status mutation for every appliance on campus.
  - **Reseed Demo Button:** 1-click database refresh with realistic IITH sample incidents for live presentations.

---

## 3. The 2-Step Verification Resolution Contract
To eliminate "phantom fixes" and guarantee student satisfaction:
```
[Resident Lodges Ticket] ──▶ status = "submitted"
         │
         ▼
[Technician Claims Ticket] ──▶ status = "in_progress"
         │
         ▼
[Step 1: Tech Work Completed] ──▶ tech_completed = True, status = "awaiting_student_verification"
         │                        ↳ Instant SMS Alert Dispatched to Student
         ▼
[Step 2: Student In-Room Verification]
         ├── Student confirms "Work Done" ──▶ student_verified = True, status = "resolved" (Closed)
         └── Student clicks "Still Broken" ──▶ tech_completed = False, status = "in_progress" (Re-queued)
```

---

## 4. Authentic IITH Campus Mapping (21 Hostels & 279 Monitored Appliances)
* **21 Authentic Hostels:**
  - **Ground to 6th Floor (7 levels: G, 1..6; Rooms G01..G30, 101..630):** Vivekananda, SN Bose, Kalpana Chawla.
  - **1st to 6th Floor (6 levels: 1..6; Rooms 101..630):** Ramanuja, Aryabhatta, Gargi, Maitreyi, Susruta, Bhaskara, Varahamihira, Charaka, Kautilya, Vyasa, Brahmagupta.
  - **1st to 10th Floor (10 levels: 1..10; Rooms 101..1030):** Sarojini Naidu, Anandi Joshi, Kalam, Raman, Bhabha, Ramanujan, Visweswaraya.
* **Appliance Distribution (279 Units Total):**
  - **10-floor hostels:** 1 washing machine on every odd floor (1, 3, 5, 7, 9) and 1 water cooler on every floor (1 to 10).
  - **6-floor & G-6 hostels:** 1 washing machine and 1 water cooler on every floor.

---

## 5. Quickstart & 1-Command Startup

### 1-Click Launch (All 3 Portals + Shared DB)
From the project directory:
```bash
./start.sh
```
This script:
1. Detects Python 3.11 virtual environment.
2. Checks dependencies from `requirements.txt`.
3. Checks/seeds the shared SQLite database with realistic campus incidents.
4. Boots Student (8000), Technician (8001), and Estate Admin (8002) micro-portals concurrently.
5. Automatically opens all three portal dashboards in browser tabs.

### Run Automated Integration Tests (7 Suites)
```bash
env PYTHONPATH=. python tests/test_api.py
```
Verifies:
- All 21 hostels and floor-wise appliance configurations (279 units).
- Crowd reporting & dynamic priority scoring formula.
- Technician authentication and role guards.
- Full 2-step verification lifecycle.
- Estate Admin KPIs, SLA scoreboard, and executive overrides.
- Phone number validation and automated SMS notification dispatch.
- Benchmark reference `#LAT-8921` direct lookup with and without `#` prefix.

---

## 6. Benchmark Demo Verification
To verify the system during judging or grading:
* **Lookup Benchmark Ticket:** Search `Ticket Reference: #LAT-8921` on [http://localhost:8000/](http://localhost:8000/) (Room 814, Raman Hostel).
* **Interactive Pitch Deck:** Navigate to [http://localhost:8000/presentation](http://localhost:8000/presentation).
* **Interactive Swagger APIs:**
  - Student: [http://localhost:8000/docs](http://localhost:8000/docs)
  - Technician: [http://localhost:8001/docs](http://localhost:8001/docs)
  - Admin: [http://localhost:8002/docs](http://localhost:8002/docs)

---

## 7. Hackathon Rubric Alignment

| Criteria | Weight | How LATTICE Delivers |
| :--- | :---: | :--- |
| **Unique Selling Point (USP)** | 25% | Dynamic crowd-weighted priority scoring formula that converts individual complaints into prioritized community signals, combined with a 2-step work confirmation contract. |
| **Functionality & Usability** | 25% | Three dedicated portals (Student public, Technician duty, Admin governance) connected in real-time to the same live database. |
| **Technical Implementation** | 20% | SQLite WAL concurrency, FastAPI modular architecture, sub-10ms REST latency, role-based session guards. |
| **UI/UX** | 10% | Industrial Utility design tokens, high contrast dark/light themes, balanced responsive grids, touch-friendly 48px controls. |
| **Presentation** | 10% | Built-in 10-slide interactive pitch deck (`http://localhost:8000/presentation`) with keyboard navigation (`←`/`→`/Space). |
| **Completeness** | 10% | Fully functional end-to-end MVP with 279 mapped appliances, 21 IITH hostels, seed data, SMS dispatch simulation, and 1-click startup. |
