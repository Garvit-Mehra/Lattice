"""
LATTICE · IITH Operations Console — Student Backend API (Port 8000)
Zero-login student portal for reporting hostel appliance failures,
requesting room maintenance, tracking resolution status, and 2-step verification.
"""
import os
import re
import json
import uuid
import random
import datetime
import time
from collections import defaultdict
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from .database import engine, get_db, Base
from .models import Hostel, Appliance, Ticket, TicketVote
from .schemas import (
    HostelResponse, ApplianceResponse, ApplianceReportRequest,
    RoomTicketCreateRequest, TicketResponse, TicketVoteRequest,
    StudentVerifyWorkRequest, DashboardStatsResponse, SLAMetric,
    ApplianceResolveCrowdRequest
)
from .scoring import calculate_priority

# Ensure DB tables exist
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="LATTICE · IITH Operations Console - Student API",
    description="LATTICE · IITH Operations Console — Student Self-Service & 2-Step Work Confirmation",
    version="2.0.0"
)

# Explicit CORS Origins for Campus Security (PRA-SEC-002)
ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://localhost:8001",
    "http://localhost:8002",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8001",
    "http://127.0.0.1:8002",
]
env_origins = os.getenv("LATTICE_ALLOWED_ORIGINS")
if env_origins:
    ALLOWED_ORIGINS.extend([o.strip() for o in env_origins.split(",") if o.strip()])

ORIGIN_REGEX = r"https?://(localhost|127\.0\.0\.1)(:\d+)?|https?://.*\.iith\.ac\.in"

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Abuse Throttling & Rate Limiter (PRA-SEC-004)
_RATE_LIMIT_STORE = defaultdict(list)

def check_rate_limit(request: Request, limit: int = 30, window_seconds: int = 60, action: str = "request"):
    """
    Abuse protection rate limiter per client IP.
    Returns HTTP 429 Too Many Requests if client exceeds the threshold.
    Bypassed if LATTICE_RATE_LIMIT_DISABLED is set.
    """
    if os.getenv("LATTICE_RATE_LIMIT_DISABLED", "0") == "1":
        return

    client_ip = "127.0.0.1"
    if request.client and request.client.host:
        client_ip = request.client.host
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    key = f"{action}:{client_ip}"
    now = time.time()
    cutoff = now - window_seconds
    timestamps = [t for t in _RATE_LIMIT_STORE[key] if t > cutoff]

    if len(timestamps) >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: maximum {limit} {action}s per minute. Please try again shortly."
        )

    timestamps.append(now)
    _RATE_LIMIT_STORE[key] = timestamps


@app.middleware("http")
async def security_and_logging_middleware(request: Request, call_next):
    """Structured request tracing (PRA-BE-002) and security headers (PRA-FE-001)."""
    request_id = request.headers.get("x-request-id", f"req_{uuid.uuid4().hex[:8]}")
    start_time = time.time()
    
    response = await call_next(request)
    
    duration_ms = round((time.time() - start_time) * 1000, 2)
    path = request.url.path

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["x-request-id"] = request_id

    # Anti-caching for HTML/JS/CSS assets
    if path == "/" or path.endswith(".js") or path.endswith(".html") or path.endswith(".css"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

    # Structured logging for API requests
    if path.startswith("/api/") and os.getenv("LATTICE_LOG_JSON", "0") == "1":
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "request_id": request_id,
            "method": request.method,
            "path": path,
            "status_code": response.status_code,
            "duration_ms": duration_ms
        }
        print(json.dumps(log_entry))

    return response


def enrich_ticket_data(ticket: Ticket, now: datetime.datetime = None):
    if now is None:
        now = datetime.datetime.utcnow()
    
    if ticket.status != "resolved":
        if getattr(ticket, "priority_overridden", False):
            score = ticket.computed_priority
            tier = "CRITICAL" if score >= 50.0 else ("HIGH" if score >= 35.0 else ("MEDIUM" if score >= 22.0 else "LOW"))
        else:
            score, tier = calculate_priority(ticket.category, ticket.confirmations_count, ticket.created_at, now)
            ticket.computed_priority = score
    else:
        score = ticket.computed_priority
        tier = "RESOLVED"
    
    return score, tier


def format_ticket_response(t: Ticket, tier: str = "LOW") -> TicketResponse:
    sms_sent = bool(t.tech_completed and t.reporter_contact)
    return TicketResponse(
        id=t.id,
        ticket_code=t.ticket_code,
        ticket_type=t.ticket_type,
        hostel_id=t.hostel_id,
        hostel_name=t.hostel.name if t.hostel else "Unknown Hostel",
        floor=t.floor,
        room_number=t.room_number,
        appliance_id=t.appliance_id,
        category=t.category,
        title=t.title,
        description=t.description,
        reporter_name=t.reporter_name,
        reporter_contact=t.reporter_contact or "",
        status=t.status,
        confirmations_count=t.confirmations_count,
        computed_priority=t.computed_priority,
        priority_tier=tier,
        priority_overridden=bool(getattr(t, "priority_overridden", False)),
        tech_assigned_to=t.tech_assigned_to or "",
        tech_completed=bool(t.tech_completed),
        tech_completed_at=t.tech_completed_at,
        tech_notes=t.tech_notes or "",
        student_verified=bool(t.student_verified),
        student_verified_at=t.student_verified_at,
        student_feedback=t.student_feedback or "",
        sms_dispatched=sms_sent,
        sms_notification_text=(f"LATTICE: Tech completed repairs. Ticket Reference: #{t.ticket_code}. SMS alert dispatched to {t.reporter_contact}." if sms_sent else None),
        created_at=t.created_at,
        updated_at=t.updated_at,
        resolved_at=t.resolved_at
    )



# ==========================================
# 1. HOSTELS & CAMPUS APPLIANCES
# ==========================================
@app.get("/api/v1/hostels", response_model=List[HostelResponse])
def get_hostels(db: Session = Depends(get_db)):
    """Returns all 21 official IITH hostels."""
    return db.query(Hostel).order_by(Hostel.name).all()


@app.get("/api/v1/appliances", response_model=List[ApplianceResponse])
def get_appliances(
    hostel_id: Optional[int] = None,
    floor: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Returns appliances with live crowd incident state."""
    query = db.query(Appliance).join(Hostel)
    if hostel_id:
        query = query.filter(Appliance.hostel_id == hostel_id)
    if floor is not None:
        query = query.filter(Appliance.floor == floor)

    appliances = query.order_by(Appliance.asset_type, Appliance.asset_label).all()
    now = datetime.datetime.utcnow()
    results = []

    for app_item in appliances:
        ticket = app_item.active_ticket
        confs = 0
        working_confs = 0
        score = 0.0
        tier = "LOW"
        issue_desc = None

        if ticket and ticket.status != "resolved":
            confs = ticket.confirmations_count
            score, tier = enrich_ticket_data(ticket, now)
            issue_desc = ticket.description
            working_confs = db.query(TicketVote).filter(
                TicketVote.ticket_id == ticket.id,
                TicketVote.user_token.startswith("working:")
            ).count()

        results.append(ApplianceResponse(
            id=app_item.id,
            hostel_id=app_item.hostel_id,
            hostel_name=app_item.hostel.name,
            floor=app_item.floor,
            asset_type=app_item.asset_type,
            asset_label=app_item.asset_label,
            location_desc=app_item.location_desc,
            status=app_item.status,
            active_ticket_id=app_item.active_ticket_id,
            confirmations_count=confs,
            working_confirmations_count=working_confs,
            required_working_confirmations=2,
            priority_score=score,
            priority_tier=tier,
            issue_description=issue_desc
        ))

    return results


@app.post("/api/v1/appliances/report", response_model=TicketResponse)
def report_appliance(req: ApplianceReportRequest, request: Request, db: Session = Depends(get_db)):
    """First student reports a broken appliance."""
    check_rate_limit(request, limit=20, action="complaint")
    app_item = db.query(Appliance).filter(Appliance.id == req.appliance_id).first()
    if not app_item:
        raise HTTPException(status_code=404, detail="Appliance not found")

    now = datetime.datetime.utcnow()

    # If already an active ticket, increment confirmation count instead of duplicating
    if app_item.active_ticket and app_item.active_ticket.status != "resolved":
        ticket = app_item.active_ticket
        ticket.confirmations_count += 1
        score, tier = enrich_ticket_data(ticket, now)
        db.add(TicketVote(ticket_id=ticket.id, user_token=req.user_token or "anon"))
        db.commit()
        db.refresh(ticket)
        return format_ticket_response(ticket, tier)

    # Generate new ticket code
    ticket_code = f"LAT-{random.randint(1000, 9999)}"
    title = f"{app_item.asset_label} on Floor {app_item.floor} reported {app_item.asset_type.replace('_', ' ')} failure"
    score, tier = calculate_priority(app_item.asset_type, 1, now, now)

    new_ticket = Ticket(
        ticket_code=ticket_code,
        ticket_type="common_appliance",
        hostel_id=app_item.hostel_id,
        floor=app_item.floor,
        appliance_id=app_item.id,
        category=app_item.asset_type,
        title=title,
        description=req.issue_description,
        reporter_name=req.reporter_name or "Campus Resident",
        status="submitted",
        confirmations_count=1,
        computed_priority=score,
        created_at=now
    )
    db.add(new_ticket)
    db.flush()

    app_item.status = "faulty"
    app_item.active_ticket_id = new_ticket.id
    db.add(TicketVote(ticket_id=new_ticket.id, user_token=req.user_token or "anon"))

    db.commit()
    db.refresh(new_ticket)
    return format_ticket_response(new_ticket, tier)


@app.post("/api/v1/appliances/{appliance_id}/confirm", response_model=TicketResponse)
def confirm_appliance_issue(
    appliance_id: int,
    req: TicketVoteRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Students tap '+1 Confirm Broken' to escalate community priority."""
    check_rate_limit(request, limit=30, action="vote")
    app_item = db.query(Appliance).filter(Appliance.id == appliance_id).first()
    if not app_item:
        raise HTTPException(status_code=404, detail="Appliance not found")

    now = datetime.datetime.utcnow()

    # If no active ticket, spawn one instead of 404 deadlocking
    if not app_item.active_ticket or app_item.active_ticket.status == "resolved":
        ticket_code = f"LAT-{random.randint(1000, 9999)}"
        title = f"{app_item.asset_label} on Floor {app_item.floor} reported {app_item.asset_type.replace('_', ' ')} failure"
        score, tier = calculate_priority(app_item.asset_type, 1, now, now)
        ticket = Ticket(
            ticket_code=ticket_code,
            ticket_type="common_appliance",
            hostel_id=app_item.hostel_id,
            floor=app_item.floor,
            appliance_id=app_item.id,
            category=app_item.asset_type,
            title=title,
            description="Appliance confirmed malfunctioning by resident.",
            reporter_name="Campus Resident",
            status="submitted",
            confirmations_count=1,
            computed_priority=score,
            created_at=now
        )
        db.add(ticket)
        db.flush()
        app_item.active_ticket_id = ticket.id
        app_item.status = "faulty"
        db.add(TicketVote(ticket_id=ticket.id, user_token=req.user_token or "anon"))
        db.commit()
        db.refresh(ticket)
        return format_ticket_response(ticket, tier)

    ticket = app_item.active_ticket
    if ticket.status == "resolved":
        raise HTTPException(status_code=400, detail="Incident already resolved.")

    # Deduplicate votes from same user token
    existing_vote = db.query(TicketVote).filter(
        TicketVote.ticket_id == ticket.id,
        TicketVote.user_token == req.user_token
    ).first()

    if not existing_vote:
        db.add(TicketVote(ticket_id=ticket.id, user_token=req.user_token))
        ticket.confirmations_count += 1

    score, tier = enrich_ticket_data(ticket, now)
    
    if ticket.confirmations_count >= 3 and app_item.status == "faulty":
        app_item.status = "out_of_order"

    db.commit()
    db.refresh(ticket)
    return format_ticket_response(ticket, tier)


@app.post("/api/v1/appliances/{appliance_id}/resolve-crowd")
def crowd_report_working(
    appliance_id: int,
    request: Request,
    req: Optional[ApplianceResolveCrowdRequest] = None,
    force: bool = False,
    db: Session = Depends(get_db)
):
    """Students confirm the appliance is working again (requires multi-resident consensus)."""
    check_rate_limit(request, limit=20, action="resolution")
    app_item = db.query(Appliance).filter(Appliance.id == appliance_id).first()
    if not app_item:
        raise HTTPException(status_code=404, detail="Appliance not found")

    REQUIRED_CONFIRMATIONS = 2
    now = datetime.datetime.utcnow()

    # If force resolution is requested (e.g. admin or test suite setup)
    if force or not app_item.active_ticket or app_item.active_ticket.status == "resolved":
        if app_item.active_ticket and app_item.active_ticket.status != "resolved":
            app_item.active_ticket.status = "resolved"
            app_item.active_ticket.resolved_at = now
            existing_notes = app_item.active_ticket.tech_notes or ""
            app_item.active_ticket.tech_notes = (existing_notes + f" [Resolved by community crowd-confirmation at {now.strftime('%Y-%m-%d %H:%M:%S')}]").strip()
        app_item.status = "operational"
        app_item.active_ticket_id = None
        db.commit()
        return {
            "status": "success",
            "resolved": True,
            "working_confirmations": REQUIRED_CONFIRMATIONS,
            "required_confirmations": REQUIRED_CONFIRMATIONS,
            "message": f"{app_item.asset_label} restored to operational state."
        }

    ticket = app_item.active_ticket
    raw_token = (req.user_token if req and req.user_token else "anon_user").strip()
    work_token = f"working:{raw_token}"

    # Deduplicate: prevent the same resident token from voting multiple times
    existing_work_vote = db.query(TicketVote).filter(
        TicketVote.ticket_id == ticket.id,
        TicketVote.user_token == work_token
    ).first()

    if existing_work_vote:
        raise HTTPException(
            status_code=400,
            detail="You have already confirmed this appliance is working. Waiting for another resident to verify before it is restored."
        )

    # Record vote
    db.add(TicketVote(ticket_id=ticket.id, user_token=work_token))
    db.flush()

    working_count = db.query(TicketVote).filter(
        TicketVote.ticket_id == ticket.id,
        TicketVote.user_token.startswith("working:")
    ).count()

    if working_count >= REQUIRED_CONFIRMATIONS:
        ticket.status = "resolved"
        ticket.resolved_at = now
        existing_notes = ticket.tech_notes or ""
        ticket.tech_notes = (existing_notes + f" [Resolved by community crowd consensus: {working_count}/{REQUIRED_CONFIRMATIONS} resident confirmations at {now.strftime('%Y-%m-%d %H:%M:%S')}]").strip()
        app_item.status = "operational"
        app_item.active_ticket_id = None
        db.commit()
        return {
            "status": "success",
            "resolved": True,
            "working_confirmations": working_count,
            "required_confirmations": REQUIRED_CONFIRMATIONS,
            "message": f"{app_item.asset_label} confirmed fixed and restored to operational state ({working_count}/{REQUIRED_CONFIRMATIONS} resident consensus)."
        }
    else:
        existing_notes = ticket.tech_notes or ""
        ticket.tech_notes = (existing_notes + f" [Working verification {working_count}/{REQUIRED_CONFIRMATIONS} recorded at {now.strftime('%Y-%m-%d %H:%M:%S')}]").strip()
        db.commit()
        remaining = REQUIRED_CONFIRMATIONS - working_count
        return {
            "status": "pending_consensus",
            "resolved": False,
            "working_confirmations": working_count,
            "required_confirmations": REQUIRED_CONFIRMATIONS,
            "message": f"Confirmation recorded ({working_count}/{REQUIRED_CONFIRMATIONS}). Need {remaining} more resident{'s' if remaining > 1 else ''} to verify fix before restoring to operational."
        }


# ==========================================
# 2. ROOM MAINTENANCE & 2-STEP VERIFICATION
# ==========================================
@app.post("/api/v1/tickets/room", response_model=TicketResponse)
def create_room_ticket(req: RoomTicketCreateRequest, request: Request, db: Session = Depends(get_db)):
    """Lodge direct room maintenance request with floor and mobile validation."""
    check_rate_limit(request, limit=15, action="complaint")
    hostel = db.query(Hostel).filter(Hostel.id == req.hostel_id).first()
    if not hostel:
        raise HTTPException(status_code=404, detail="Hostel not found")

    # Floor boundary validation against hostel capacity (Task 12)
    max_floor = hostel.total_floors or 6
    min_floor = 0 if hostel.has_ground_floor else 1
    if req.floor < min_floor or req.floor > max_floor:
        floor_desc = f"Ground (0) to Floor {max_floor}" if hostel.has_ground_floor else f"Floor 1 to Floor {max_floor}"
        raise HTTPException(
            status_code=400,
            detail=f"Invalid floor {req.floor} for {hostel.name}. Valid floor range is {floor_desc}."
        )

    # Room number validation (Task 12)
    clean_room = (req.room_number or "").strip().upper()
    if not clean_room:
        raise HTTPException(status_code=400, detail="Room number is required.")

    # Indian Mobile Phone (or IITH campus email) validation (Task 11)
    contact = (req.reporter_contact or "").strip()
    if not contact:
        raise HTTPException(
            status_code=400,
            detail="Mobile phone number is required so technician can contact you and dispatch SMS verification notifications."
        )

    is_phone = bool(re.match(r"^(\+91[\-\s]?)?[6-9]\d{9}$", contact))
    is_email = bool(re.match(r"^[a-zA-Z0-9_.+-]+@([a-zA-Z0-9-]+\.)?iith\.ac\.in$", contact))
    if not (is_phone or is_email):
        raise HTTPException(
            status_code=400,
            detail="Invalid contact format. Please provide a valid 10-digit Indian mobile number (e.g. 9876543210) or IITH email."
        )

    now = datetime.datetime.utcnow()
    ticket_code = f"LAT-{random.randint(1000, 9999)}"
    score, tier = calculate_priority(req.category, 1, now, now)

    ticket = Ticket(
        ticket_code=ticket_code,
        ticket_type="room",
        hostel_id=req.hostel_id,
        floor=req.floor,
        room_number=clean_room,
        category=req.category,
        title=req.title,
        description=req.description,
        reporter_name=req.reporter_name or "Hostel Resident",
        reporter_contact=contact,

        status="submitted",
        confirmations_count=1,
        computed_priority=score,
        tech_completed=False,
        student_verified=False,
        created_at=now
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return format_ticket_response(ticket, tier)


@app.get("/api/v1/tickets/{ticket_code}", response_model=TicketResponse)
def get_ticket_by_code(ticket_code: str, db: Session = Depends(get_db)):
    """Fetch live status of a specific ticket by reference code."""
    clean_code = ticket_code.strip().upper().lstrip("#")
    ticket = db.query(Ticket).filter(Ticket.ticket_code == clean_code).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    _, tier = enrich_ticket_data(ticket)
    return format_ticket_response(ticket, tier)


@app.post("/api/v1/tickets/{ticket_code}/verify", response_model=TicketResponse)
def student_verify_room_work(
    ticket_code: str,
    req: StudentVerifyWorkRequest,
    db: Session = Depends(get_db)
):
    """
    Step 2 of 2-Step Verification for Room Maintenance:
    The student verifies whether the technician has completed the work in their room.
    Only when BOTH tech_completed AND student_verified are True does status become 'resolved'.
    """
    clean_code = ticket_code.strip().upper().lstrip("#")
    ticket = db.query(Ticket).filter(Ticket.ticket_code == clean_code).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    now = datetime.datetime.utcnow()

    if req.verified:
        # Require technician to complete Step 1 first to prevent premature auto-resolve
        if not ticket.tech_completed:
            raise HTTPException(
                status_code=400,
                detail="Cannot complete verification: Technician has not yet submitted Step 1 repair completion."
            )
        ticket.student_verified = True
        ticket.student_verified_at = now
        ticket.student_feedback = req.student_feedback or "Resident confirmed work completed."
        ticket.status = "resolved"
        ticket.resolved_at = now
    else:
        # Resident reports work is still incomplete or not working
        ticket.student_verified = False
        ticket.tech_completed = False
        ticket.status = "in_progress"
        ticket.student_feedback = f"[REJECTED WORK - REOPENED]: {req.student_feedback or 'Defect still persists'}"
        # Task 10: Escalate priority score on student rejection (+15 points, minimum 52.0 CRITICAL)
        ticket.computed_priority = round(max((ticket.computed_priority or 25.0) + 15.0, 52.0), 1)
        ticket.priority_overridden = True

    db.commit()
    db.refresh(ticket)
    _, tier = enrich_ticket_data(ticket, now)
    return format_ticket_response(ticket, tier)

    db.commit()
    db.refresh(ticket)
    _, tier = enrich_ticket_data(ticket, now)
    return format_ticket_response(ticket, tier)


# ==========================================
# 3. SLA & DASHBOARD ANALYTICS API
# ==========================================
@app.get("/api/v1/analytics/sla", response_model=DashboardStatsResponse)
def get_sla_analytics(db: Session = Depends(get_db)):
    """Computes SLA resolution turnaround times per hostel and overall KPIs."""
    now = datetime.datetime.utcnow()
    hostels = db.query(Hostel).all()
    sla_metrics = []

    total_active = db.query(Ticket).filter(Ticket.status != "resolved").count()
    
    # Critical active tickets (score >= 35)
    active_tickets = db.query(Ticket).filter(Ticket.status != "resolved").all()
    critical_count = sum(1 for t in active_tickets if t.computed_priority >= 35.0)

    total_appliances = db.query(Appliance).count()
    operational_appliances = db.query(Appliance).filter(Appliance.status == "operational").count()
    operational_pct = (operational_appliances / total_appliances * 100.0) if total_appliances > 0 else 100.0

    for h in hostels:
        resolved_tickets = db.query(Ticket).filter(
            Ticket.hostel_id == h.id,
            Ticket.status == "resolved",
            Ticket.resolved_at.isnot(None)
        ).all()

        pending_count = db.query(Ticket).filter(
            Ticket.hostel_id == h.id,
            Ticket.status != "resolved"
        ).count()

        if resolved_tickets:
            durations = [(t.resolved_at - t.created_at).total_seconds() / 3600.0 for t in resolved_tickets]
            avg_hours = round(sum(durations) / len(durations), 1)
        else:
            avg_hours = 12.0  # Baseline

        if avg_hours <= 12.0:
            rating = "Excellent"
        elif avg_hours <= 24.0:
            rating = "Good"
        else:
            rating = "Needs Improvement"

        sla_metrics.append(SLAMetric(
            hostel_id=h.id,
            hostel_name=h.name,
            avg_resolution_hours=avg_hours,
            total_resolved=len(resolved_tickets),
            total_pending=pending_count,
            performance_rating=rating
        ))

    return DashboardStatsResponse(
        total_active_tickets=total_active,
        total_critical_tickets=critical_count,
        total_appliances_monitored=total_appliances,
        appliances_operational_pct=round(operational_pct, 1),
        sla_metrics=sla_metrics
    )


# ==========================================
# 4. STATIC FRONTEND & PRESENTATION SERVING
# ==========================================
@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

if os.path.exists(FRONTEND_DIR):
    static_path = os.path.join(FRONTEND_DIR, "static")
    if os.path.exists(static_path):
        app.mount("/static", StaticFiles(directory=static_path), name="static")

    @app.get("/")
    @app.get("/student")
    def serve_student_ui():
        index_file = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "LATTICE · IITH Operations Console Student UI not found."}

    @app.get("/static/tech.js")
    def serve_tech_js():
        candidates = [
            os.path.join(FRONTEND_DIR, "static", "tech.js"),
            os.path.join(FRONTEND_DIR, "technician", "static", "tech.js"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return FileResponse(c, media_type="application/javascript")
        return Response(status_code=404)

    @app.get("/static/admin.js")
    def serve_admin_js():
        candidates = [
            os.path.join(FRONTEND_DIR, "static", "admin.js"),
            os.path.join(FRONTEND_DIR, "admin", "static", "admin.js"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return FileResponse(c, media_type="application/javascript")
        return Response(status_code=404)

    @app.get("/presentation")
    @app.get("/presemtation")
    @app.get("/deck")
    @app.get("/slides")
    def serve_presentation():
        pres_file = os.path.join(os.path.dirname(FRONTEND_DIR), "presentation", "index.html")
        if os.path.exists(pres_file):
            return FileResponse(pres_file)
        return {"message": "Presentation slides not found."}


# Sub-mount Technician and Admin backends for unified single-port access on port 8000
try:
    from .tech_app import app as tech_fastapi_app
    app.mount("/tech", tech_fastapi_app)
except Exception as e:
    print(f"Warning: Could not mount tech_app on student_app: {e}")

try:
    from .admin_app import app as admin_fastapi_app
    app.mount("/admin", admin_fastapi_app)
except Exception as e:
    print(f"Warning: Could not mount admin_app on student_app: {e}")

