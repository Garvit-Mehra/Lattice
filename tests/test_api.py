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


# ==========================================
# 4. P0 & P1 VERIFICATION TESTS
# ==========================================
def test_admin_reseed_endpoint():
    """Verify POST /api/v1/admin/reseed successfully refreshes database with sample data."""
    login_res = client_admin.post("/api/v1/admin/login", json={"username": "admin", "password": "admin123"})
    assert login_res.status_code == 200
    headers = {"Authorization": f"Bearer {login_res.json()['token']}"}

    res = client_admin.post("/api/v1/admin/reseed", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    # Verify benchmark ticket exists after reseed
    res_bench = client_student.get("/api/v1/tickets/LAT-8921")
    assert res_bench.status_code == 200
    assert res_bench.json()["ticket_code"] == "LAT-8921"


def test_priority_override_persistence():
    """Verify admin priority override persists across subsequent queries without being erased."""
    login_res = client_admin.post("/api/v1/admin/login", json={"username": "admin", "password": "admin123"})
    headers = {"Authorization": f"Bearer {login_res.json()['token']}"}

    # Fetch a ticket
    res = client_admin.get("/api/v1/admin/tickets?status_filter=active", headers=headers)
    assert res.status_code == 200
    tickets = res.json()
    t = tickets[0]

    # Override priority to 95.0 (CRITICAL)
    res_override = client_admin.patch(
        f"/api/v1/admin/tickets/{t['id']}/override",
        headers=headers,
        json={"computed_priority": 95.0, "override_reason": "Executive priority elevation"}
    )
    assert res_override.status_code == 200
    updated = res_override.json()
    assert updated["computed_priority"] == 95.0
    assert updated["priority_overridden"] is True
    assert updated["priority_tier"] == "CRITICAL"

    # Subsequent fetch must NOT overwrite priority back to calculated formula
    res_fetch = client_admin.get("/api/v1/admin/tickets?status_filter=all", headers=headers)
    assert res_fetch.status_code == 200
    refetched = next(item for item in res_fetch.json() if item["id"] == t["id"])
    assert refetched["computed_priority"] == 95.0
    assert refetched["priority_tier"] == "CRITICAL"


def test_category_aliasing_and_benchmark_filtering():
    """Verify filtering by 'civil' or 'carpentry' both return carpentry tickets including benchmark #LAT-8921."""
    login_res = client_tech.post("/api/v1/tech/login", json={"username": "technician", "password": "tech123"})
    headers = {"Authorization": f"Bearer {login_res.json()['token']}"}

    # Query with category=civil
    res_civil = client_tech.get("/api/v1/tech/tickets/room?status_filter=all&category=civil", headers=headers)
    assert res_civil.status_code == 200
    codes_civil = [item["ticket_code"] for item in res_civil.json()]
    assert "LAT-8921" in codes_civil

    # Query with category=carpentry
    res_carpentry = client_tech.get("/api/v1/tech/tickets/room?status_filter=all&category=carpentry", headers=headers)
    assert res_carpentry.status_code == 200
    codes_carpentry = [item["ticket_code"] for item in res_carpentry.json()]
    assert "LAT-8921" in codes_carpentry


def test_appliance_status_mutation_and_student_confirm_flow():
    """Verify admin setting appliance to faulty auto-generates active ticket without student 404 deadlock."""
    login_res = client_admin.post("/api/v1/admin/login", json={"username": "admin", "password": "admin123"})
    headers = {"Authorization": f"Bearer {login_res.json()['token']}"}

    # Find an operational appliance
    res_apps = client_admin.get("/api/v1/admin/appliances?status_filter=operational", headers=headers)
    apps = res_apps.json()
    assert len(apps) > 0
    target_app = apps[0]

    # Mutate to faulty
    res_mut = client_admin.patch(
        f"/api/v1/admin/appliances/{target_app['id']}/status",
        headers=headers,
        json={"status": "faulty"}
    )
    assert res_mut.status_code == 200

    # Student confirms broken on this appliance: must succeed and NOT return 404
    res_confirm = client_student.post(
        f"/api/v1/appliances/{target_app['id']}/confirm",
        json={"user_token": "test_confirmer_99"}
    )
    assert res_confirm.status_code == 200
    ticket = res_confirm.json()
    assert ticket["appliance_id"] == target_app["id"]

    # Admin standard resolves ticket -> appliance must be restored to operational
    res_res = client_admin.patch(
        f"/api/v1/admin/tickets/{ticket['id']}/override",
        headers=headers,
        json={"status": "resolved"}
    )
    assert res_res.status_code == 200
    # Verify appliance operational
    res_check = client_student.get(f"/api/v1/appliances?hostel_id={target_app['hostel_id']}&floor={target_app['floor']}")
    refetched_app = next(a for a in res_check.json() if a["id"] == target_app["id"])
    assert refetched_app["status"] == "operational"


def test_single_port_submounts_and_session_persistence():
    """Verify /tech and /admin sub-mounts on port 8000 and cross-process session persistence."""
    # 1. Single port submounts accessible on student app client
    res_tech = client_student.get("/tech/api/v1/hostels")
    assert res_tech.status_code == 200
    assert len(res_tech.json()) == 21

    res_admin = client_student.get("/admin/api/v1/hostels")
    assert res_admin.status_code == 200
    assert len(res_admin.json()) == 21

    # 2. Login as technician on tech app
    login_res = client_tech.post("/api/v1/tech/login", json={"username": "technician", "password": "tech123"})
    token = login_res.json()["token"]

    # Verify session is recognized across backends via SQLite persistence
    from backend.auth import verify_session
    session = verify_session(token, required_role="technician")
    assert session is not None
    assert session["username"] == "technician"


def test_session_expiration_ttl():
    """Verify session expiration TTL checks reject and prune expired tokens (PRA-SEC-003)."""
    import datetime
    from backend.auth import verify_session, ACTIVE_SESSIONS
    from backend.models import AuthSession
    from backend.database import SessionLocal

    token = "lat_admin_test_expired_123"
    past_time = datetime.datetime.utcnow() - datetime.timedelta(hours=2)

    # Insert an expired session into DB
    db = SessionLocal()
    db.query(AuthSession).filter(AuthSession.token == token).delete()
    db.add(AuthSession(
        token=token,
        username="admin",
        name="Admin",
        role="admin",
        dept="Test",
        created_at=past_time - datetime.timedelta(hours=12),
        expires_at=past_time
    ))
    db.commit()
    db.close()

    # Clear from in-memory cache to force DB read
    if token in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[token]

    # Verify that verify_session rejects the expired token
    result = verify_session(token, required_role="admin")
    assert result is None, "Expired session must return None"

    # Verify it was pruned from DB
    db = SessionLocal()
    db_session = db.query(AuthSession).filter(AuthSession.token == token).first()
    assert db_session is None, "Expired session must be pruned from database"
    db.close()


def test_rate_limiting_abuse_throttling():
    """Verify rate limiting rejects excessive automated requests with 429 Too Many Requests (PRA-SEC-004)."""
    from backend.student_app import _RATE_LIMIT_STORE
    _RATE_LIMIT_STORE.clear()

    # Normal request succeeds
    res1 = client_student.post(
        "/api/v1/appliances/1/confirm",
        json={"user_token": "rate_limit_tester_0"}
    )
    assert res1.status_code in [200, 400]  # Either ok or already resolved

    # Artificially fill rate limit bucket to trigger threshold
    for i in range(35):
        client_student.post(
            "/api/v1/appliances/1/confirm",
            json={"user_token": f"rate_limit_tester_{i}"}
        )

    # Next request must return 429
    res_limited = client_student.post(
        "/api/v1/appliances/1/confirm",
        json={"user_token": "rate_limit_tester_over"}
    )
    assert res_limited.status_code == 429
    assert "Rate limit exceeded" in res_limited.json()["detail"]

    # Clear rate limit store so subsequent tests remain unaffected
    _RATE_LIMIT_STORE.clear()


def test_workflow_logic_and_validation():
    """Verify floor bounds, mobile regex, premature verification guard, and rejection escalation."""
    # 1. Floor bounds check: Kalam hostel has 6 floors, floor 99 must fail
    res_floor_err = client_student.post("/api/v1/tickets/room", json={
        "hostel_id": 1,
        "room_number": "9901",
        "floor": 99,
        "category": "electrical",
        "title": "Sparking",
        "description": "Short circuit",
        "reporter_name": "Test",
        "reporter_contact": "9876543210"
    })
    assert res_floor_err.status_code == 400
    assert "Invalid floor" in res_floor_err.json()["detail"]

    # 2. Invalid contact format check: non-10-digit number must fail
    res_phone_err = client_student.post("/api/v1/tickets/room", json={
        "hostel_id": 1,
        "room_number": "101",
        "floor": 1,
        "category": "electrical",
        "title": "Sparking",
        "description": "Short circuit",
        "reporter_name": "Test",
        "reporter_contact": "12345abc"
    })
    assert res_phone_err.status_code == 400
    assert "Invalid contact format" in res_phone_err.json()["detail"]

    # 3. Create valid ticket
    res_ok = client_student.post("/api/v1/tickets/room", json={
        "hostel_id": 1,
        "room_number": "101",
        "floor": 1,
        "category": "electrical",
        "title": "Sparking",
        "description": "Short circuit",
        "reporter_name": "Test Resident",
        "reporter_contact": "9876543210"
    })
    assert res_ok.status_code == 200
    t = res_ok.json()
    t_code = t["ticket_code"]
    t_id = t["id"]

    # 4. Premature verification guard: Student tries to verify before tech completes Step 1
    res_premature = client_student.post(f"/api/v1/tickets/{t_code}/verify", json={
        "verified": True,
        "student_feedback": "All good"
    })
    assert res_premature.status_code == 400
    assert "Technician has not yet submitted Step 1" in res_premature.json()["detail"]

    # 5. Tech completes Step 1
    login_res = client_tech.post("/api/v1/tech/login", json={"username": "tech_electrical", "password": "tech123"})
    token = login_res.json()["token"]
    res_step1 = client_tech.post(
        f"/api/v1/tech/tickets/{t_id}/complete",
        headers={"Authorization": f"Bearer {token}"},
        json={"tech_name": "Ramesh (Electrical)", "tech_notes": "Wiring replaced"}
    )
    assert res_step1.status_code == 200
    assert res_step1.json()["status"] == "awaiting_student_verification"

    # 6. Rejection escalation: Student tests work, rejects repair ("No, Still Broken")
    res_reject = client_student.post(f"/api/v1/tickets/{t_code}/verify", json={
        "verified": False,
        "student_feedback": "Sparks still flying from socket!"
    })
    assert res_reject.status_code == 200
    t_reopened = res_reject.json()
    assert t_reopened["status"] == "in_progress"
    assert t_reopened["priority_tier"] == "CRITICAL"
    assert t_reopened["computed_priority"] >= 50.0
    assert "[REJECTED WORK - REOPENED]" in t_reopened["student_feedback"]


if __name__ == "__main__":
    print("[*] Running LATTICE · IITH Operations Console Multi-Portal Integration Test Suite...")
    test_student_hostels_and_appliances()
    test_student_crowd_reporting_and_vote()
    test_technician_auth_and_portal()
    test_full_2_step_verification_room_lifecycle()
    test_admin_portal_and_overrides()
    test_room_phone_number_required_and_sms()
    test_benchmark_ticket_lat_8921()
    test_admin_reseed_endpoint()
    test_priority_override_persistence()
    test_category_aliasing_and_benchmark_filtering()
    test_appliance_status_mutation_and_student_confirm_flow()
    test_single_port_submounts_and_session_persistence()
    test_session_expiration_ttl()
    test_rate_limiting_abuse_throttling()
    test_workflow_logic_and_validation()
    print("[+] ALL 15 TEST SUITES PASSED CLEANLY! (Student, Technician, Admin, 2-Step Verification, #LAT-8921, Reseed, Aliases, Sessions, TTL, Rate Limiting, Workflow Logic)")

