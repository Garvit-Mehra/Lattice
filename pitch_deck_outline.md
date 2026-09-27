# Pitch Deck: LATTICE — IITH Operations Console
**Event:** MILAN 2026 Lambda Hackathon Finals  
**Theme:** Smart Campus Solutions for IIT Hyderabad (IITH)  
**Target:** Panel of Faculty Judges & Student Representatives  
**Time Limit:** 5-7 Minutes + Q&A

---

### Slide 1: Title & Hook
* **Title:** LATTICE · IITH Operations Console
* **Tagline:** Turning Campus Maintenance from an Opaque Bureaucracy into a Real-Time Crowd-Triaged Network.
* **Team Members & Hostel Affiliation.**

### Slide 2: The Ground Reality at IITH (The "Broken Cooler Dilemma")
* Picture this: It is 38°C in Kandi. The water cooler on Floor 2 stops cooling.
* What happens today?
  1. Student complains in a 500-member WhatsApp group.
  2. Begs the Hostel Representative (HR) to compose an email.
  3. HR emails the Estate Office.
  4. 15 other students email separately or assume someone else handled it.
  5. The complaint languishes for 14 days in an email inbox.

### Slide 3: The Problem We Solve
* **Zero Real-Time Visibility:** Students carry laundry down 4 floors only to find all washing machines dead.
* **High Administrative Overhead:** Estate technicians receive hundreds of unstructured, duplicate emails with no clear priority.
* **Lack of Accountability:** Physical paper registers offer zero transparency on resolution turnaround.
* **"Phantom Fixes":** Work marked completed by technicians without resident in-room verification.

### Slide 4: Introducing LATTICE
* A mobile-first, smart facility management platform tailored for the IITH campus.
* Three pillars:
  1. **Common Facility Live Matrix:** Live status of 279 washing machines and water coolers across all 21 hostels.
  2. **Direct Room Maintenance Portal:** Frictionless ticketing with unique tracking codes (`Ticket Reference: #LAT-8921`).
  3. **Estate Dispatch & SLA Dashboard:** Automated queue ranking, 2-step work confirmation, and public hostel turnaround metrics.

### Slide 5: The USP — Dynamic Crowd-Escalation Engine (25% Weight)
* How do we prevent duplicate tickets while surfacing critical issues?
  $$\text{Priority} = \text{BaseSeverity} + (3.5 \times \text{Confirmations}) + (1.2 \times \text{HoursPending})$$
* **The "+1 Confirm Broken" Button:**
  Instead of emailing, affected students tap "+1". The ticket surges dynamically from *Low* $\to$ *Medium* $\to$ *High* $\to$ *CRITICAL*.
* **2-Step Verification Contract:** Both technician (Step 1) and student (Step 2) must sign off before room complaints close.
* **Automated SMS Alerts:** Students receive instant SMS notifications upon technician Step 1 completion so they never forget to verify.

### Slide 6: Live Product Demo Walkthrough
* *Demo Step 1:* View Raman Hostel Floor 8 $\longrightarrow$ See Water Cooler marked faulty with 8 student confirmations.
* *Demo Step 2:* Lodge a Room Maintenance ticket with required phone number $\longrightarrow$ Get trackable code `Ticket Reference: #LAT-8921`.
* *Demo Step 3:* Switch to Technician Console $\longrightarrow$ Watch Step 1 completion trigger automated SMS alert to resident.
* *Demo Step 4:* Verify on Student Portal $\longrightarrow$ Complete Step 2 resident sign-off to officially close ticket.
* *Demo Step 5:* View Estate SLA Governance Scoreboard across all 21 hostels.

### Slide 7: Technical Architecture (20% Weight)
* **Backend:** FastAPI (Python 3.11) with sub-10ms response times.
* **Data Model:** SQLAlchemy ORM with relational integrity between Hostels, Appliances, Tickets, and Votes.
* **Storage:** SQLite with WAL mode (`PRAGMA journal_mode=WAL`) for concurrent multi-portal reads/writes.
* **Frontend:** PWA-style Single Page App with Tailwind CSS. Zero build dependency (`npm`-free), instantly executable by judges.

### Slide 8: Expected Impact on the IITH Community
* **85% Reduction in Redundant Emails** sent to HRs, wardens, and estate staff.
* **Faster Emergency Triage:** Critical community outages (water coolers, MCB trips) escalated within minutes.
* **Zero Phantom Fixes:** Mandatory 2-step sign-off ensures verified repairs.
* **Administrative Accountability:** Public hostel SLA leaderboard incentivizes faster contractor turnaround.

### Slide 9: Scalability & Future Roadmap
* **QR Code Tags:** Physical QR codes on every washing machine, cooler, and room door for 1-second instant reporting.
* **Inventory & Spare Part Integration:** Linking tickets to campus store parts (e.g. capacitors, tap washers).
* **Zulip / Telegram Bot Webhooks:** Real-time push alerts to hostel maintenance teams.

### Slide 10: Conclusion & Q&A
* LATTICE: Scalable, data-driven, and built for the real day-to-day life of IITH students.
* Zero phantom fixes, transparent estate SLA metrics, and crowd-prioritized facility repair.
* Live Demo URL: http://localhost:8000
* Thank you!
