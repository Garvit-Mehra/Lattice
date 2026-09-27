"""
Automated Integration & 2-Step Verification Tests for LATTICE · IITH Operations Console Multi-Portal Suite:
1. Student Backend (Port 8000 / student_app)
2. Technician Backend (Port 8001 / tech_app)
3. Estate Admin Backend (Port 8002 / admin_app)
"""
from fastapi.testclient import TestClient

from backend.student_app import app as student_app
from backend.tech_app import app as tech_app
from backend.admin_app import app as admin_app

client_student = TestClient(student_app)
client_tech = TestClient(tech_app)
client_admin = TestClient(admin_app)


# ==========================================
# 1. STUDENT BACKEND TESTS (No Login Required)
# ==========================================
def test_student_hostels_and_appliances():
    res = client_student.get("/api/v1/hostels")
    assert res.status_code == 200
    hostels = res.json()
    assert len(hostels) == 21

    # Check 10-floor vs 6-floor hostels
    raman = next(h for h in hostels if h["name"] == "Raman")
    assert raman["total_floors"] == 10
    assert not raman["has_ground_floor"]

    vvk = next(h for h in hostels if h["name"] == "Vivekananda")
    assert vvk["total_floors"] == 7
    assert vvk["has_ground_floor"]

    # Check appliances for Raman floor 1
    res = client_student.get(f"/api/v1/appliances?hostel_id={raman['id']}&floor=1")
    assert res.status_code == 200
    apps = res.json()
    # Odd floor in 10-floor hostel has 1 washing machine and 1 water cooler
    assert any(a["asset_type"] == "washing_machine" for a in apps)
    assert any(a["asset_type"] == "water_cooler" for a in apps)


def test_student_crowd_reporting_and_vote():
    # Fetch Bhabha appliances
    res = client_student.get("/api/v1/hostels")
    bhabha_id = next(h["id"] for h in res.json() if h["slug"] == "bhabha")

    res = client_student.get(f"/api/v1/appliances?hostel_id={bhabha_id}&floor=3")
    apps = res.json()
    app = apps[0]

    # If faulty, resolve first to test clean slate
    if app["status"] != "operational":
        client_student.post(f"/api/v1/appliances/{app['id']}/resolve-crowd")

    import uuid
    u1 = f"student_reporter_{uuid.uuid4().hex[:6]}"
    u2 = f"student_confirmer_{uuid.uuid4().hex[:6]}"

    # 1. Report issue
    res = client_student.post("/api/v1/appliances/report", json={
        "appliance_id": app["id"],
        "issue_description": "Water cooler dispensing warm water",
        "user_token": u1,
        "reporter_name": "Hostel Resident"
    })
    assert res.status_code == 200
    ticket = res.json()
    initial_confirmations = ticket["confirmations_count"]

    # 2. Confirm broken (+1)
    res = client_student.post(f"/api/v1/appliances/{app['id']}/confirm", json={
        "user_token": u2
    })
    assert res.status_code == 200
    updated = res.json()
    assert updated["confirmations_count"] == initial_confirmations + 1
    assert updated["computed_priority"] > ticket["computed_priority"]


# ==========================================
# 2. TECHNICIAN BACKEND & 2-STEP VERIFICATION
# ==========================================
def test_technician_auth_and_portal():
    # 1. Unauthenticated request rejected
    res = client_tech.get("/api/v1/tech/appliances/faulty")
    assert res.status_code == 401

    # 2. Login with valid technician credentials
    res = client_tech.post("/api/v1/tech/login", json={
        "username": "technician",
        "password": "tech123"
    })
    assert res.status_code == 200
    data = res.json()
    token = data["token"]
    assert "token" in data
    assert data["role"] == "technician"

    headers = {"Authorization": f"Bearer {token}"}

    # 3. Authenticated request succeeds
    res = client_tech.get("/api/v1/tech/me", headers=headers)
    assert res.status_code == 200
    assert res.json()["username"] == "technician"

    # 4. Tab 1: Faulty appliances list
    res = client_tech.get("/api/v1/tech/appliances/faulty", headers=headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_full_2_step_verification_room_lifecycle():
    """
    Critical requirement:
    - Student lodges room ticket
    - Tech sees ticket, claims it, marks work completed (Step 1)
    - Ticket moves to awaiting_student_verification (does NOT disappear!)
    - Student verifies in their room (Step 2)
    - Ticket becomes resolved
    """
    # 1. Student creates room maintenance ticket
    res_h = client_student.get("/api/v1/hostels")
    vvk = next(h for h in res_h.json() if h["slug"] == "vivekananda")

    res = client_student.post("/api/v1/tickets/room", json={
        "hostel_id": vvk["id"],
        "room_number": "G03",
        "floor": 0,
        "category": "electrical",
        "title": "Ceiling fan speed regulator broken",
        "description": "Fan operates only at maximum speed 5, knob loose",
        "reporter_name": "Garvit Mehra",
        "reporter_contact": "garvit@iith.ac.in"
    })
    assert res.status_code == 200
    ticket = res.json()
    ticket_id = ticket["id"]
    ticket_code = ticket["ticket_code"]
    assert ticket["status"] == "submitted"
    assert not ticket["tech_completed"]
    assert not ticket["student_verified"]

    # 2. Technician logs in
    login_res = client_tech.post("/api/v1/tech/login", json={
        "username": "tech_electrical",
        "password": "tech123"
    })
    tech_token = login_res.json()["token"]
    tech_headers = {"Authorization": f"Bearer {tech_token}"}

    # 3. Technician views room queries (Tab 2)
    res_room = client_tech.get("/api/v1/tech/tickets/room?status_filter=active", headers=tech_headers)
    assert res_room.status_code == 200
    active_room_tickets = res_room.json()
    assert any(t["id"] == ticket_id for t in active_room_tickets)

    # 4. Technician claims ticket
    res_assign = client_tech.post(f"/api/v1/tech/tickets/{ticket_id}/assign", headers=tech_headers)
    assert res_assign.status_code == 200
    assert res_assign.json()["status"] == "in_progress"

    # 5. Technician marks work completed (STEP 1)
    res_step1 = client_tech.post(f"/api/v1/tech/tickets/{ticket_id}/complete", headers=tech_headers, json={
        "tech_notes": "Replaced stepped capacitor regulator. Fan now tests OK across all 5 speeds.",
        "tech_name": "Suresh (Electrical)"
    })
    assert res_step1.status_code == 200
    step1_data = res_step1.json()
    assert step1_data["tech_completed"] is True
    assert step1_data["status"] == "awaiting_student_verification"
    assert step1_data["student_verified"] is False

    # Verify ticket DOES NOT disappear from technician portal when viewing awaiting verification
    res_awaiting = client_tech.get("/api/v1/tech/tickets/room?status_filter=awaiting_verification", headers=tech_headers)
    assert res_awaiting.status_code == 200
    assert any(t["id"] == ticket_id for t in res_awaiting.json())

    # 6. Student looks up ticket and confirms completion (STEP 2)
    lookup_res = client_student.get(f"/api/v1/tickets/{ticket_code}")
    assert lookup_res.status_code == 200
    assert lookup_res.json()["status"] == "awaiting_student_verification"

    verify_res = client_student.post(f"/api/v1/tickets/{ticket_code}/verify", json={
        "verified": True,
        "student_feedback": "Confirmed, fan regulator is working smoothly now. Thank you!"
    })
    assert verify_res.status_code == 200
    final_ticket = verify_res.json()
    assert final_ticket["tech_completed"] is True
    assert final_ticket["student_verified"] is True
    assert final_ticket["status"] == "resolved"
    assert final_ticket["resolved_at"] is not None


# ==========================================
# 3. ESTATE ADMIN BACKEND TESTS
# ==========================================
def test_admin_portal_and_overrides():
    # 1. Unauthenticated request rejected
    res = client_admin.get("/api/v1/admin/dashboard/stats")
    assert res.status_code == 401

    # 2. Login as super admin
    login_res = client_admin.post("/api/v1/admin/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert login_res.status_code == 200
    admin_token = login_res.json()["token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 3. View KPIs & SLA Scoreboard
    res_stats = client_admin.get("/api/v1/admin/dashboard/stats", headers=admin_headers)
    assert res_stats.status_code == 200
    stats = res_stats.json()
    assert "total_active_tickets" in stats
    assert "sla_metrics" in stats
    assert len(stats["sla_metrics"]) == 21  # All 21 IITH hostels tracked

    # 4. View all 279 monitored appliances
    res_apps = client_admin.get("/api/v1/admin/appliances", headers=admin_headers)
    assert res_apps.status_code == 200
    appliances = res_apps.json()
    assert len(appliances) == 279

    # 5. Admin overrides an appliance status
    test_app = appliances[0]
    res_override_app = client_admin.patch(
        f"/api/v1/admin/appliances/{test_app['id']}/status",
        headers=admin_headers,
        json={"status": "operational"}
    )
    assert res_override_app.status_code == 200

    # 6. Admin can force override/resolve any ticket
    res_tickets = client_admin.get("/api/v1/admin/tickets?status_filter=all", headers=admin_headers)
    assert res_tickets.status_code == 200
    tickets = res_tickets.json()
    if tickets:
        t = tickets[0]
        res_override_t = client_admin.patch(
            f"/api/v1/admin/tickets/{t['id']}/override",
            headers=admin_headers,
            json={
                "status": "resolved",
                "override_reason": "Estate Office verified and cleared during campus inspection."
            }
        )
        assert res_override_t.status_code == 200
        assert res_override_t.json()["status"] == "resolved"


def test_room_phone_number_required_and_sms():
    """Verify phone number is mandatory and triggers SMS notification."""
    res_h = client_student.get("/api/v1/hostels")
    sn_bose = next(h for h in res_h.json() if h["name"] == "SN Bose")


    # 1. Missing or blank contact number is rejected
    res_bad = client_student.post("/api/v1/tickets/room", json={
        "hostel_id": sn_bose["id"],
        "room_number": "105",
        "floor": 1,
        "category": "plumbing",
        "title": "Tap leaking",
        "description": "Continuous water drip from bathroom sink tap",
        "reporter_name": "Test Resident",
        "reporter_contact": ""
    })
    assert res_bad.status_code == 400
    assert "Mobile phone number is required" in res_bad.json()["detail"]

    # 2. Valid 10-digit phone number is accepted
    res_good = client_student.post("/api/v1/tickets/room", json={
        "hostel_id": sn_bose["id"],
        "room_number": "105",
        "floor": 1,
        "category": "plumbing",
        "title": "Tap leaking",
        "description": "Continuous water drip from bathroom sink tap",
        "reporter_name": "Rohit Verma",
        "reporter_contact": "9876543210"
    })
    assert res_good.status_code == 200
    ticket = res_good.json()
    assert ticket["reporter_contact"] == "9876543210"
    t_id = ticket["id"]
    t_code = ticket["ticket_code"]

    # 3. Technician logs in and completes Step 1
    login_res = client_tech.post("/api/v1/tech/login", json={
        "username": "tech_plumbing",
        "password": "tech123"
    })
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    res_comp = client_tech.post(f"/api/v1/tech/tickets/{t_id}/complete", headers=headers, json={
        "tech_notes": "Replaced tap washer spindle.",
        "tech_name": "Mahesh (Plumbing)"
    })
    assert res_comp.status_code == 200
    comp_ticket = res_comp.json()
    assert comp_ticket["tech_completed"]
    assert comp_ticket["sms_dispatched"]
    assert "9876543210" in comp_ticket["sms_notification_text"]
    assert "LATTICE:" in comp_ticket["sms_notification_text"]
    assert f"#{t_code}" in comp_ticket["sms_notification_text"]
    assert comp_ticket["ticket_code"].startswith("LAT-")

    # 4. Student queries ticket and receives SMS confirmation info
    res_fetch = client_student.get(f"/api/v1/tickets/{t_code}")
    assert res_fetch.status_code == 200
    fetched = res_fetch.json()
    assert fetched["status"] == "awaiting_student_verification"
    assert fetched["reporter_contact"] == "9876543210"
    assert fetched["sms_dispatched"]
    assert fetched["ticket_code"].startswith("LAT-")

    # 5. Verify lookup works with leading '#' or '%23'
    res_fetch_hash = client_student.get(f"/api/v1/tickets/%23{t_code}")
    assert res_fetch_hash.status_code == 200
    assert res_fetch_hash.json()["id"] == t_id


def test_benchmark_ticket_lat_8921():
    """Verify the benchmark ticket reference #LAT-8921 resolves seamlessly."""
    # Lookup without hash
    res1 = client_student.get("/api/v1/tickets/LAT-8921")
    assert res1.status_code == 200
    t1 = res1.json()
    assert t1["ticket_code"] == "LAT-8921"
    assert t1["room_number"] == "814"

    # Lookup with hash encoded %23
    res2 = client_student.get("/api/v1/tickets/%23LAT-8921")
    assert res2.status_code == 200
    t2 = res2.json()
    assert t2["ticket_code"] == "LAT-8921"


if __name__ == "__main__":
    print("[*] Running LATTICE · IITH Operations Console Multi-Portal Integration Test Suite...")
    test_student_hostels_and_appliances()
    test_student_crowd_reporting_and_vote()
    test_technician_auth_and_portal()
    test_full_2_step_verification_room_lifecycle()
    test_admin_portal_and_overrides()
    test_room_phone_number_required_and_sms()
    test_benchmark_ticket_lat_8921()
    print("[+] ALL 7 TEST SUITES PASSED CLEANLY! (Student, Technician, Admin, 2-Step Verification, #LAT-8921 & SMS Alerting)")

