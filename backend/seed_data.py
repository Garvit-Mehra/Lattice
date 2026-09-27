"""
Database Seeding Script for LATTICE · IITH Operations Console
Populates all 21 official IIT Hyderabad hostels with exact floor configurations,
proper ground floor handling, accurate room numbering (e.g. G03, 814, 1014),
floor-wise appliances, crowd-triaged incidents, realistic room maintenance requests,
and 2-step verification simulation with mobile alerts and SLA metrics.
"""
import random
import datetime
from .database import engine, Base, SessionLocal
from .models import Hostel, Appliance, Ticket, TicketVote
from .scoring import calculate_priority


# The 21 Official IITH Hostels
IITH_HOSTELS = [
    # Hostels starting from Ground Floor up to 6th Floor (G, 1, 2, 3, 4, 5, 6 = 7 levels)
    {"name": "Vivekananda", "slug": "vivekananda", "floors": 7, "has_ground": True, "desc": "Undergraduate Hostel (Ground to 6th Floor)"},
    {"name": "SN Bose", "slug": "sn-bose", "floors": 7, "has_ground": True, "desc": "Undergraduate Hostel (Ground to 6th Floor)"},
    {"name": "Kalpana Chawla", "slug": "kalpana-chawla", "floors": 7, "has_ground": True, "desc": "Women's Campus Hostel (Ground to 6th Floor)"},

    # 6-Floor Hostels starting from 1st Floor (1 to 6)
    {"name": "Ramanuja", "slug": "ramanuja", "floors": 6, "has_ground": False, "desc": "Hostel Block (Floors 1 to 6)"},
    {"name": "Aryabhatta", "slug": "aryabhatta", "floors": 6, "has_ground": False, "desc": "Hostel Block (Floors 1 to 6)"},
    {"name": "Gargi", "slug": "gargi", "floors": 6, "has_ground": False, "desc": "Hostel Block (Floors 1 to 6)"},
    {"name": "Maitreyi", "slug": "maitreyi", "floors": 6, "has_ground": False, "desc": "Hostel Block (Floors 1 to 6)"},
    {"name": "Susruta", "slug": "susruta", "floors": 6, "has_ground": False, "desc": "Hostel Block (Floors 1 to 6)"},
    {"name": "Bhaskara", "slug": "bhaskara", "floors": 6, "has_ground": False, "desc": "Hostel Block (Floors 1 to 6)"},
    {"name": "Varahamihira", "slug": "varahamihira", "floors": 6, "has_ground": False, "desc": "Hostel Block (Floors 1 to 6)"},
    {"name": "Charaka", "slug": "charaka", "floors": 6, "has_ground": False, "desc": "Hostel Block (Floors 1 to 6)"},
    {"name": "Kautilya", "slug": "kautilya", "floors": 6, "has_ground": False, "desc": "Hostel Block (Floors 1 to 6)"},
    {"name": "Vyasa", "slug": "vyasa", "floors": 6, "has_ground": False, "desc": "Hostel Block (Floors 1 to 6)"},
    {"name": "Brahmagupta", "slug": "brahmagupta", "floors": 6, "has_ground": False, "desc": "Hostel Block (Floors 1 to 6)"},

    # 10-Floor Hostels starting from 1st Floor (1 to 10)
    {"name": "Sarojini Naidu", "slug": "sarojini-naidu", "floors": 10, "has_ground": False, "desc": "High-Rise Hostel (Floors 1 to 10)"},
    {"name": "Anandi Joshi", "slug": "anandi-joshi", "floors": 10, "has_ground": False, "desc": "High-Rise Hostel (Floors 1 to 10)"},
    {"name": "Kalam", "slug": "kalam", "floors": 10, "has_ground": False, "desc": "High-Rise Hostel (Floors 1 to 10)"},
    {"name": "Raman", "slug": "raman", "floors": 10, "has_ground": False, "desc": "High-Rise Hostel (Floors 1 to 10)"},
    {"name": "Bhabha", "slug": "bhabha", "floors": 10, "has_ground": False, "desc": "High-Rise Hostel (Floors 1 to 10)"},
    {"name": "Ramanujan", "slug": "ramanujan", "floors": 10, "has_ground": False, "desc": "High-Rise Hostel (Floors 1 to 10)"},
    {"name": "Visweswaraya", "slug": "visweswaraya", "floors": 10, "has_ground": False, "desc": "High-Rise Hostel (Floors 1 to 10)"}
]


def format_room_number(hostel, floor: int, room_idx: int) -> str:
    """Formats room numbers according to official IITH convention."""
    if hostel.has_ground_floor and floor == 0:
        return f"G{room_idx:02d}"
    return f"{floor}{room_idx:02d}"


def get_hostel_floors(hostel):
    if hostel.has_ground_floor:
        return list(range(0, hostel.total_floors))
    return list(range(1, hostel.total_floors + 1))


def seed_database():
    print("[*] Recreating database tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    now = datetime.datetime.utcnow()

    print("[*] Seeding 21 Authentic IITH Hostels...")
    hostels = []
    for h_data in IITH_HOSTELS:
        hostel = Hostel(
            name=h_data["name"],
            slug=h_data["slug"],
            total_floors=h_data["floors"],
            has_ground_floor=h_data["has_ground"],
            description=h_data["desc"]
        )
        db.add(hostel)
        hostels.append(hostel)
    db.commit()

    print("[*] Seeding Common Appliances across all floors...")
    appliances_list = []
    for h in hostels:
        floors = get_hostel_floors(h)
        is_10_floor = (h.total_floors == 10 and not h.has_ground_floor)

        for f in floors:
            floor_label = "G" if f == 0 else str(f)
            loc_label = "Ground Floor" if f == 0 else f"Floor {f}"

            # Washing Machine Rule:
            # - In 10-floor hostels: exactly 1 machine on odd floors (1, 3, 5, 7, 9)
            # - In 6-floor hostels (and G to 6): 1 machine on every floor
            if (not is_10_floor) or (is_10_floor and f % 2 != 0):
                wm = Appliance(
                    hostel_id=h.id,
                    floor=f,
                    asset_type="washing_machine",
                    asset_label=f"WM-{floor_label}01",
                    location_desc=f"{loc_label} Central Laundry",
                    status="operational"
                )
                db.add(wm)
                appliances_list.append(wm)

            # Water Cooler Rule: 1 on EVERY floor across all hostels
            wc = Appliance(
                hostel_id=h.id,
                floor=f,
                asset_type="water_cooler",
                asset_label=f"WC-{floor_label}01",
                location_desc=f"{loc_label} Central Water Station",
                status="operational"
            )
            db.add(wc)
            appliances_list.append(wc)
    db.commit()

    print("[*] Seeding Crowd-Triaged Common Appliance Incidents...")

    # Realistic Common Appliance Breakdowns across various hostels and floors
    common_incidents = [
        # 1. Raman (10-floor) - Floor 8 Water Cooler (high crowd count!)
        {
            "hostel_slug": "raman", "floor": 8, "type": "water_cooler", "label": "WC-801",
            "code": "LAT-C801", "title": "Water Cooler dispensing boiling hot water & compressor vibrating",
            "desc": "Cooler on Raman 8th floor has tripped its thermostat; students from rooms 801-825 have no cold drinking water.",
            "reporter": "Arjun Verma", "reporter_contact": "9876543210", "status": "in_progress",
            "votes": 8, "hours_ago": 14, "appliance_status": "faulty"
        },
        # 2. Vivekananda (G-6) - Floor 0 Washing Machine (Ground floor laundry)
        {
            "hostel_slug": "vivekananda", "floor": 0, "type": "washing_machine", "label": "WM-G01",
            "code": "LAT-CG01", "title": "Drum lock jammed on Ground Floor laundry with clothes inside",
            "desc": "Ground floor machine WM-G01 stopped mid-cycle; door electronic lock refuses to release.",
            "reporter": "Rohit Sharma", "reporter_contact": "9812345678", "status": "acknowledged",
            "votes": 5, "hours_ago": 7, "appliance_status": "faulty"
        },
        # 3. Bhabha (10-floor) - Floor 5 Washing Machine
        {
            "hostel_slug": "bhabha", "floor": 5, "type": "washing_machine", "label": "WM-501",
            "code": "LAT-C501", "title": "Drain pump clogged with water overflowing on floor",
            "desc": "WM-501 on 5th floor cannot drain rinse water; soap water spilling across the laundry hallway.",
            "reporter": "Aditya Nair", "reporter_contact": "9701234567", "status": "submitted",
            "votes": 4, "hours_ago": 3, "appliance_status": "faulty"
        },
        # 4. SN Bose (G-6) - Floor 2 Water Cooler
        {
            "hostel_slug": "sn-bose", "floor": 2, "type": "water_cooler", "label": "WC-201",
            "code": "LAT-C201", "title": "Push tap brass lever snapped - water gushing continuously",
            "desc": "Right-side push handle snapped off, water running non-stop. Stopcock temporarily shut off by floor rep.",
            "reporter": "Siddharth Rao", "reporter_contact": "9849012345", "status": "in_progress",
            "votes": 6, "hours_ago": 11, "appliance_status": "faulty"
        },
        # 5. Kalpana Chawla (G-6) - Floor 0 Washing Machine
        {
            "hostel_slug": "kalpana-chawla", "floor": 0, "type": "washing_machine", "label": "WM-G01",
            "code": "LAT-CG02", "title": "Drive belt slipping - drum humming but not spinning",
            "desc": "Machine fills and drains water properly, but drive motor screeches and drum does not turn during wash cycle.",
            "reporter": "Ananya Sen", "reporter_contact": "9876501234", "status": "submitted",
            "votes": 7, "hours_ago": 5, "appliance_status": "faulty"
        },
        # 6. Kalpana Chawla (G-6) - Floor 4 Water Cooler
        {
            "hostel_slug": "kalpana-chawla", "floor": 4, "type": "water_cooler", "label": "WC-401",
            "code": "LAT-C401", "title": "Purifier carbon sediment filter choked - trickle flow",
            "desc": "Water flow from dispensing tap is extremely slow, takes over 3 minutes to fill a single 1L water bottle.",
            "reporter": "Pooja Hegde", "reporter_contact": "9845012345", "status": "acknowledged",
            "votes": 3, "hours_ago": 9, "appliance_status": "faulty"
        },
        # 7. Sarojini Naidu (10-floor) - Floor 7 Water Cooler
        {
            "hostel_slug": "sarojini-naidu", "floor": 7, "type": "water_cooler", "label": "WC-701",
            "code": "LAT-C701", "title": "Compressor tripping MCB / water at ambient room temperature",
            "desc": "Cooler trips the floor breaker every time the compressor kicks on. Water is lukewarm and undrinkable.",
            "reporter": "Priya Nair", "reporter_contact": "9899887766", "status": "in_progress",
            "votes": 9, "hours_ago": 18, "appliance_status": "faulty"
        },
        # 8. Sarojini Naidu (10-floor) - Floor 3 Washing Machine
        {
            "hostel_slug": "sarojini-naidu", "floor": 3, "type": "washing_machine", "label": "WM-301",
            "code": "LAT-C301", "title": "Violent drum shaking & error UE (Unbalanced Error) during spin",
            "desc": "Shock absorber mount loosened; machine bangs loudly against the wall during 800 RPM spin and halts.",
            "reporter": "Meenakshi Sundaram", "reporter_contact": "9887766554", "status": "submitted",
            "votes": 4, "hours_ago": 6, "appliance_status": "faulty"
        },
        # 9. Kalam (10-floor) - Floor 1 Washing Machine
        {
            "hostel_slug": "kalam", "floor": 1, "type": "washing_machine", "label": "WM-101",
            "code": "LAT-C101", "title": "Door lock sensor error 'dE' - machine will not start cycle",
            "desc": "Even with door securely latched, digital panel flashes dE error and cycle aborts immediately.",
            "reporter": "Vikram Das", "reporter_contact": "9823456789", "status": "acknowledged",
            "votes": 3, "hours_ago": 8, "appliance_status": "faulty"
        },
        # 10. Aryabhatta (6-floor) - Floor 4 Water Cooler (Safety Issue!)
        {
            "hostel_slug": "aryabhatta", "floor": 4, "type": "water_cooler", "label": "WC-401",
            "code": "LAT-C410", "title": "Mild electric tingling sensation on tap handle (Earthing leakage)",
            "desc": "URGENT SAFETY: Students reported mild electric shock sensation while touching the stainless steel tap. Power unplugged.",
            "reporter": "Meera Sen", "reporter_contact": "9845098765", "status": "in_progress",
            "votes": 8, "hours_ago": 4, "appliance_status": "out_of_order"
        },
        # 11. Visweswaraya (10-floor) - Floor 9 Washing Machine
        {
            "hostel_slug": "visweswaraya", "floor": 9, "type": "washing_machine", "label": "WM-901",
            "code": "LAT-C901", "title": "Rubber door bellows torn, heavy leakage during wash cycle",
            "desc": "Front rubber gasket has a 2-inch slit; water pools across floor whenever machine fills.",
            "reporter": "Harsh Vardhan", "reporter_contact": "9811223344", "status": "submitted",
            "votes": 5, "hours_ago": 10, "appliance_status": "faulty"
        },
        # 12. Gargi (6-floor) - Floor 2 Water Cooler
        {
            "hostel_slug": "gargi", "floor": 2, "type": "water_cooler", "label": "WC-201",
            "code": "LAT-C204", "title": "Condenser fan seized - cooler emitting burning rubber smell",
            "desc": "Internal cooling fan seized up, unit turned off immediately to prevent compressor burn.",
            "reporter": "Divya Bharti", "reporter_contact": "9818123456", "status": "acknowledged",
            "votes": 4, "hours_ago": 12, "appliance_status": "faulty"
        },
        # 13. Ramanuja (6-floor) - Floor 5 Washing Machine
        {
            "hostel_slug": "ramanuja", "floor": 5, "type": "washing_machine", "label": "WM-501",
            "code": "LAT-C502", "title": "Coin trap blocked, wash cycle halts at 12 minutes remaining",
            "desc": "Filter trap underneath is stuck; machine cannot pump out rinse water without error OE.",
            "reporter": "Kalyan Ram", "reporter_contact": "9866112233", "status": "submitted",
            "votes": 3, "hours_ago": 2, "appliance_status": "faulty"
        },
        # 14. Bhaskara (6-floor) - Floor 3 Water Cooler
        {
            "hostel_slug": "bhaskara", "floor": 3, "type": "water_cooler", "label": "WC-301",
            "code": "LAT-C309", "title": "Waste water drainage pipe detached from wall drain",
            "desc": "Drip tray drainage pipe came off; all overflow water drains directly onto the hallway floor.",
            "reporter": "Varun Tej", "reporter_contact": "9848123456", "status": "acknowledged",
            "votes": 4, "hours_ago": 15, "appliance_status": "faulty"
        }
    ]

    for inc in common_incidents:
        h = next(h for h in hostels if h.slug == inc["hostel_slug"])
        app = next(a for a in appliances_list if a.hostel_id == h.id and a.floor == inc["floor"] and a.asset_label == inc["label"])
        app.status = inc["appliance_status"]

        t_time = now - datetime.timedelta(hours=inc["hours_ago"])
        score, _ = calculate_priority(inc["type"], inc["votes"], t_time, now)

        t = Ticket(
            ticket_code=inc["code"],
            ticket_type="common_appliance",
            hostel_id=h.id,
            floor=inc["floor"],
            appliance_id=app.id,
            category=inc["type"],
            title=inc["title"],
            description=inc["desc"],
            reporter_name=inc["reporter"],
            reporter_contact=inc["reporter_contact"],
            status=inc["status"],
            confirmations_count=inc["votes"],
            computed_priority=score,
            created_at=t_time
        )
        db.add(t)
        db.flush()
        app.active_ticket_id = t.id

        for v_idx in range(inc["votes"]):
            db.add(TicketVote(ticket_id=t.id, user_token=f"{inc['hostel_slug']}_{inc['floor']}_voter_{v_idx}"))

    db.commit()

    print("[*] Seeding Realistic Room Maintenance Tickets with 2-Step Verification & Phone Alerts...")

    # Realistic Room Tickets across various categories and hostels
    # Stages: submitted, in_progress, awaiting_student_verification, resolved
    sn_bose = next(h for h in hostels if h.slug == "sn-bose")
    vivekananda = next(h for h in hostels if h.slug == "vivekananda")
    kalpana = next(h for h in hostels if h.slug == "kalpana-chawla")
    kalam = next(h for h in hostels if h.slug == "kalam")
    raman = next(h for h in hostels if h.slug == "raman")
    aryabhatta = next(h for h in hostels if h.slug == "aryabhatta")
    visweswaraya = next(h for h in hostels if h.slug == "visweswaraya")
    sarojini = next(h for h in hostels if h.slug == "sarojini-naidu")
    bhabha = next(h for h in hostels if h.slug == "bhabha")
    ramanujan = next(h for h in hostels if h.slug == "ramanujan")

    room_tickets_data = [
        # --- STAGE 1: Submitted (Fresh requests awaiting technician triage) ---
        {
            "code": "LAT-G031", "hostel": sn_bose, "floor": 0, "room": "G03",
            "cat": "electrical", "title": "Main room tube light flickering & buzzing continuously",
            "desc": "Tube light over study table buzzes loudly when switched on and flickers at random intervals.",
            "name": "Siddharth Rao", "contact": "9849012345",
            "status": "submitted", "hours": 2,
            "tech_assigned": "", "tech_completed": False, "tech_notes": "", "student_verified": False, "feedback": ""
        },
        {
            "code": "LAT-G120", "hostel": kalpana, "floor": 0, "room": "G12",
            "cat": "plumbing", "title": "Washbasin drain PVC siphon pipe cracked under sink",
            "desc": "Flexible corrugated pipe cracked; water pools on the bathroom floor whenever tap is opened.",
            "name": "Ananya Sen", "contact": "9876501234",
            "status": "submitted", "hours": 4,
            "tech_assigned": "", "tech_completed": False, "tech_notes": "", "student_verified": False, "feedback": ""
        },
        {
            "code": "LAT-1014", "hostel": kalam, "floor": 10, "room": "1014",
            "cat": "network", "title": "LAN RJ45 wall jack broken pins - no link light",
            "desc": "Wall socket pin 3 is bent backward; plugging in ethernet cable gives no network carrier signal.",
            "name": "Vikram Das", "contact": "9823456789",
            "status": "submitted", "hours": 5,
            "tech_assigned": "", "tech_completed": False, "tech_notes": "", "student_verified": False, "feedback": ""
        },
        {
            "code": "LAT-3040", "hostel": raman, "floor": 3, "room": "304",
            "cat": "carpentry", "title": "Wardrobe door hinge screws stripped from wooden panel",
            "desc": "Upper hinge came loose from particle board frame; right wardrobe door is tilting down dangerously.",
            "name": "Tanmay Joshi", "contact": "9765432109",
            "status": "submitted", "hours": 6,
            "tech_assigned": "", "tech_completed": False, "tech_notes": "", "student_verified": False, "feedback": ""
        },
        {
            "code": "LAT-5120", "hostel": sarojini, "floor": 5, "room": "512",
            "cat": "electrical", "title": "Study table 16A power socket sparking when adapter plugged in",
            "desc": "Internal copper contacts are loose; heavy sparking occurs whenever charging laptop.",
            "name": "Priya Nair", "contact": "9899887766",
            "status": "submitted", "hours": 8,
            "tech_assigned": "", "tech_completed": False, "tech_notes": "", "student_verified": False, "feedback": ""
        },
        {
            "code": "LAT-7180", "hostel": visweswaraya, "floor": 7, "room": "718",
            "cat": "appliance", "title": "Ceiling fan bearing screeching noise at high speed",
            "desc": "Fan operates but emits a piercing metallic screeching noise above speed 3.",
            "name": "Harsh Vardhan", "contact": "9811223344",
            "status": "submitted", "hours": 10,
            "tech_assigned": "", "tech_completed": False, "tech_notes": "", "student_verified": False, "feedback": ""
        },

        # --- STAGE 2: In Progress (Technician assigned, on-site repair in progress) ---
        {
            "code": "LAT-G210", "hostel": vivekananda, "floor": 0, "room": "G21",
            "cat": "carpentry", "title": "Window aluminum latch jammed in closed position",
            "desc": "Sliding window latch handle is jammed solid; room cannot be opened for cross ventilation.",
            "name": "Rohan Kulkarni", "contact": "9876123456",
            "status": "in_progress", "hours": 12,
            "tech_assigned": "Naresh (Carpentry)", "tech_completed": False, "tech_notes": "Inspecting window track and latch mechanism on-site.", "student_verified": False, "feedback": ""
        },
        {
            "code": "LAT-4150", "hostel": sn_bose, "floor": 4, "room": "415",
            "cat": "plumbing", "title": "Flush cistern valve failing to shut - continuous water overflow",
            "desc": "Internal inlet float arm stuck down; cistern tank continuously overflows into toilet pan.",
            "name": "Aman Gupta", "contact": "9810987654",
            "status": "in_progress", "hours": 15,
            "tech_assigned": "Mahesh (Plumbing)", "tech_completed": False, "tech_notes": "Procuring replacement flush valve diaphragm from estate inventory.", "student_verified": False, "feedback": ""
        },
        {
            "code": "LAT-8921", "hostel": raman, "floor": 8, "room": "814",
            "cat": "carpentry", "title": "Study table drawer ball-bearing slide rail bent & jammed",
            "desc": "Right-hand drawer runner rail dropped its ball bearings; drawer cannot slide shut.",
            "name": "Karthik Iyer", "contact": "9740123456",
            "status": "in_progress", "hours": 16,
            "tech_assigned": "Naresh (Carpentry)", "tech_completed": False, "tech_notes": "Replacing telescopic channel runner with new heavy-duty set.", "student_verified": False, "feedback": ""
        },
        {
            "code": "LAT-3140", "hostel": aryabhatta, "floor": 3, "room": "314",
            "cat": "electrical", "title": "Ceiling fan speed regulator knob broken and stuck on maximum",
            "desc": "Regulator knob cracked and stuck at maximum speed 5. Resident unable to turn speed down.",
            "name": "Meera Sen", "contact": "9845098765",
            "status": "in_progress", "hours": 20,
            "tech_assigned": "Suresh (Electrical)", "tech_completed": False, "tech_notes": "Replacing damaged modular step regulator with anchor Roma unit.", "student_verified": False, "feedback": ""
        },
        {
            "code": "LAT-6220", "hostel": bhabha, "floor": 6, "room": "622",
            "cat": "network", "title": "Aruba access point in corridor rebooting every 2 minutes",
            "desc": "Room drops ping to gateway every 120 seconds due to PoE switch power cycle on wing B.",
            "name": "Devansh Saxena", "contact": "9833445566",
            "status": "in_progress", "hours": 18,
            "tech_assigned": "Rajesh (Network Operations)", "tech_completed": False, "tech_notes": "Investigating PoE budget drop on 6th floor edge switch stack.", "student_verified": False, "feedback": ""
        },

        # --- STAGE 3: Awaiting Student Verification (Technician STEP 1 DONE, SMS alert sent, awaiting resident confirmation) ---
        {
            "code": "LAT-G080", "hostel": vivekananda, "floor": 0, "room": "G08",
            "cat": "electrical", "title": "Ceiling fan motor humming but blades stationary",
            "desc": "Capacitor failed; fan requires manual push to start spinning.",
            "name": "Aditya Menon", "contact": "9848011223",
            "status": "awaiting_student_verification", "hours": 22,
            "tech_assigned": "Suresh (Electrical)", "tech_completed": True,
            "tech_notes": "Fitted new 2.5uF heavy-duty capacitor and lubricated rotor spindle. Fan tested across all 5 speeds. [SMS Alert Dispatched to 9848011223 at 14:15]: LATTICE: Tech Suresh (Electrical) completed repairs for Room G08. Ticket Reference: #LAT-G080 - Please inspect and confirm.",
            "student_verified": False, "feedback": ""
        },
        {
            "code": "LAT-2190", "hostel": kalpana, "floor": 2, "room": "219",
            "cat": "plumbing", "title": "Health faucet high-pressure hose burst at swivel joint",
            "desc": "Braided steel hose burst at joint, spraying water whenever main angle valve is turned on.",
            "name": "Shreya Patil", "contact": "9701234567",
            "status": "awaiting_student_verification", "hours": 19,
            "tech_assigned": "Mahesh (Plumbing)", "tech_completed": True,
            "tech_notes": "Installed new reinforced stainless steel health faucet and replaced EPDM rubber washer. Zero leaks at 3.5 bar pressure. [SMS Alert Dispatched to 9701234567 at 13:40]: LATTICE: Tech Mahesh (Plumbing) completed repairs for Room 219. Ticket Reference: #LAT-2190 - Kindly test and confirm in your room.",
            "student_verified": False, "feedback": ""
        },
        {
            "code": "LAT-8070", "hostel": kalam, "floor": 8, "room": "807",
            "cat": "carpentry", "title": "Main room entrance door brass mortise lock cylinder sticky",
            "desc": "Key gets caught in cylinder tumbler, difficult to turn and remove.",
            "name": "Pranav Reddy", "contact": "9988776655",
            "status": "awaiting_student_verification", "hours": 24,
            "tech_assigned": "Naresh (Carpentry)", "tech_completed": True,
            "tech_notes": "Flushed and lubricated lock cylinder with dry graphite powder; adjusted strike plate alignment. Smooth locking tested with both keys. [SMS Alert Dispatched to 9988776655 at 12:20]: LATTICE: Tech Naresh (Carpentry) completed repairs for Room 807. Ticket Reference: #LAT-8070 - Please verify.",
            "student_verified": False, "feedback": ""
        },
        {
            "code": "LAT-4110", "hostel": ramanujan, "floor": 4, "room": "411",
            "cat": "network", "title": "Ethernet faceplate dislodged and pushed inside drywall",
            "desc": "Faceplate plastic clips broke off when cable was pulled; RJ45 socket vanished into wall cavity.",
            "name": "Neha Agarwal", "contact": "9812345670",
            "status": "awaiting_student_verification", "hours": 17,
            "tech_assigned": "Rajesh (Network Operations)", "tech_completed": True,
            "tech_notes": "Retrieved cable harness, fitted new metal gang box and Cat6 punch-down keystone jack. Certified 1000BASE-T link OK. [SMS Alert Dispatched to 9812345670 at 15:10]: LATTICE: Tech Rajesh (Network Operations) completed repairs for Room 411. Ticket Reference: #LAT-4110 - Awaiting student verification.",
            "student_verified": False, "feedback": ""
        },

        # --- STAGE 4: Resolved (Full 2-step verification completed - student confirmed) ---
        {
            "code": "LAT-G030", "hostel": vivekananda, "floor": 0, "room": "G03",
            "cat": "electrical", "title": "Ceiling fan speed regulator broken",
            "desc": "Fan operates only at maximum speed 5, knob loose.",
            "name": "Garvit Mehra", "contact": "9876543210",
            "status": "resolved", "hours": 28,
            "tech_assigned": "Suresh (Electrical)", "tech_completed": True,
            "tech_notes": "Replaced stepped capacitor regulator. Fan now tests OK across all 5 speeds. [SMS Alert Dispatched to 9876543210]: LATTICE: Tech Suresh completed repairs. Ticket Reference: #LAT-G030",
            "student_verified": True, "feedback": "Confirmed, fan regulator is working smoothly now. Thank you!"
        },
        {
            "code": "LAT-1002", "hostel": visweswaraya, "floor": 10, "room": "1002",
            "cat": "plumbing", "title": "Flush valve leaking continuously in attached washroom",
            "desc": "Internal flush gasket damaged, water leaking non-stop.",
            "name": "Rahul Joshi", "contact": "9822334455",
            "status": "resolved", "hours": 32,
            "tech_assigned": "Mahesh (Plumbing)", "tech_completed": True,
            "tech_notes": "Cleaned sediment from valve seat and installed new nitrile rubber seal. [SMS Alert Dispatched to 9822334455]: LATTICE: Tech Mahesh completed repairs. Ticket Reference: #LAT-1002",
            "student_verified": True, "feedback": "Verified, no more leaking sound. Great work!"
        },
        {
            "code": "LAT-1050", "hostel": sn_bose, "floor": 1, "room": "105",
            "cat": "plumbing", "title": "Continuous water drip from bathroom sink tap",
            "desc": "Tap spindle worn out, drips even when shut tightly.",
            "name": "Rohit Verma", "contact": "9876543210",
            "status": "resolved", "hours": 35,
            "tech_assigned": "Mahesh (Plumbing)", "tech_completed": True,
            "tech_notes": "Replaced tap washer spindle. [SMS Alert Dispatched to 9876543210]: LATTICE: Tech Mahesh completed repairs. Ticket Reference: #LAT-1050",
            "student_verified": True, "feedback": "Confirmed resolved, completely stopped dripping."
        }
    ]

    for rt in room_tickets_data:
        t_time = now - datetime.timedelta(hours=rt["hours"])
        score, _ = calculate_priority(rt["cat"], 1, t_time, now)

        t = Ticket(
            ticket_code=rt["code"],
            ticket_type="room",
            hostel_id=rt["hostel"].id,
            floor=rt["floor"],
            room_number=rt["room"],
            category=rt["cat"],
            title=rt["title"],
            description=rt["desc"],
            reporter_name=rt["name"],
            reporter_contact=rt["contact"],
            status=rt["status"],
            confirmations_count=1,
            computed_priority=score,
            tech_assigned_to=rt["tech_assigned"],
            tech_completed=rt["tech_completed"],
            tech_completed_at=(t_time + datetime.timedelta(hours=rt["hours"] - 2)) if rt["tech_completed"] else None,
            tech_notes=rt["tech_notes"],
            student_verified=rt["student_verified"],
            student_verified_at=(t_time + datetime.timedelta(hours=rt["hours"] - 1)) if rt["student_verified"] else None,
            student_feedback=rt["feedback"],
            created_at=t_time,
            resolved_at=(t_time + datetime.timedelta(hours=rt["hours"] - 1)) if rt["status"] == "resolved" else None
        )
        db.add(t)

    # Historical Resolved Tickets across all 21 hostels for realistic SLA graphs & analytics
    print("[*] Seeding 50 Historical Resolved Tickets across all 21 Hostels for SLA Metrics...")
    categories = ["electrical", "plumbing", "carpentry", "washing_machine", "water_cooler", "network", "appliance"]
    technicians_pool = ["Suresh (Electrical)", "Mahesh (Plumbing)", "Naresh (Carpentry)", "Rajesh (Network Operations)"]

    for i in range(50):
        h = random.choice(hostels)
        floors = get_hostel_floors(h)
        f = random.choice(floors)
        room_num = format_room_number(h, f, random.randint(1, 28))
        cat = random.choice(categories)

        hours_to_resolve = round(random.uniform(3.5, 28.0), 1)
        days_ago = random.randint(1, 25)
        c_time = now - datetime.timedelta(days=days_ago, hours=hours_to_resolve)
        tech_done_time = c_time + datetime.timedelta(hours=hours_to_resolve - 1.2)
        r_time = c_time + datetime.timedelta(hours=hours_to_resolve)

        tech_name = random.choice(technicians_pool)
        phone = f"98{random.randint(10000000, 99999999)}"

        t = Ticket(
            ticket_code=f"LAT-RES{300 + i}",
            ticket_type="room" if cat in ["electrical", "plumbing", "carpentry", "network", "appliance"] else "common_appliance",
            hostel_id=h.id,
            floor=f,
            room_number=room_num if cat in ["electrical", "plumbing", "carpentry", "network", "appliance"] else None,
            category=cat,
            title=f"Resolved: {cat.replace('_', ' ').capitalize()} maintenance",
            description=f"Standard preventive and corrective repair completed by Estate Maintenance Division ({tech_name}).",
            reporter_name=f"Resident {chr(65 + (i % 26))}.",
            reporter_contact=phone,
            status="resolved",
            confirmations_count=random.randint(1, 4),
            computed_priority=10.0,
            tech_assigned_to=tech_name,
            tech_completed=True,
            tech_completed_at=tech_done_time,
            tech_notes=f"Work completed as per safety standards. [SMS Alert Dispatched to {phone}]: LATTICE: Ticket Reference: #LAT-RES{300 + i}",
            student_verified=True,
            student_verified_at=r_time,
            student_feedback="Satisfied with the prompt repair work.",
            created_at=c_time,
            resolved_at=r_time
        )
        db.add(t)

    db.commit()
    db.close()
    print(f"[+] Seeding complete! Total Hostels: {len(hostels)}, Total Monitored Appliances: {len(appliances_list)}.")
    print(f"[+] Simulated Campus: 14 Crowd-Triaged Common Appliance Incidents, {len(room_tickets_data)} Live Room Tickets (all 2-step verification stages), 50 Historical Resolved SLA Records.")


if __name__ == "__main__":
    seed_database()
