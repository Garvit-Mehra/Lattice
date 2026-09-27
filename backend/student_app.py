"""
LATTICE · IITH Operations Console — Student Backend API (Port 8000)
Zero-login student portal for reporting hostel appliance failures,
requesting room maintenance, tracking resolution status, and 2-step verification.
"""
import os
import random
import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .database import engine, get_db, Base
from .models import Hostel, Appliance, Ticket, TicketVote
from .schemas import (
    HostelResponse, ApplianceResponse, ApplianceReportRequest,
    RoomTicketCreateRequest, TicketResponse, TicketVoteRequest,
    StudentVerifyWorkRequest
)
from .scoring import calculate_priority

# Ensure DB tables exist
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="LATTICE · IITH Operations Console - Student API",
    description="LATTICE · IITH Operations Console — Student Self-Service & 2-Step Work Confirmation",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.endswith(".js") or path.endswith(".html") or path.endswith(".css"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


def enrich_ticket_data(ticket: Ticket, now: datetime.datetime = None):
    if now is None:
        now = datetime.datetime.utcnow()
    
    if ticket.status != "resolved":
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
        score = 0.0
        tier = "LOW"
        issue_desc = None

        if ticket and ticket.status != "resolved":
            confs = ticket.confirmations_count
            score, tier = enrich_ticket_data(ticket, now)
            issue_desc = ticket.description

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
            priority_score=score,
            priority_tier=tier,
            issue_description=issue_desc
        ))

    return results


@app.post("/api/v1/appliances/report", response_model=TicketResponse)
def report_appliance(req: ApplianceReportRequest, db: Session = Depends(get_db)):
    """First student reports a broken appliance."""
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
    db: Session = Depends(get_db)
):
    """Students tap '+1 Confirm Broken' to escalate community priority."""
    app_item = db.query(Appliance).filter(Appliance.id == appliance_id).first()
    if not app_item or not app_item.active_ticket:
        raise HTTPException(status_code=404, detail="No active incident reported on this appliance.")

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

    now = datetime.datetime.utcnow()
    score, tier = enrich_ticket_data(ticket, now)
    
    if ticket.confirmations_count >= 3 and app_item.status == "faulty":
        app_item.status = "out_of_order"

    db.commit()
    db.refresh(ticket)
    return format_ticket_response(ticket, tier)


@app.post("/api/v1/appliances/{appliance_id}/resolve-crowd")
def crowd_report_working(appliance_id: int, db: Session = Depends(get_db)):
    """Students confirm the appliance is working again."""
    app_item = db.query(Appliance).filter(Appliance.id == appliance_id).first()
    if not app_item:
        raise HTTPException(status_code=404, detail="Appliance not found")

    now = datetime.datetime.utcnow()
    if app_item.active_ticket and app_item.active_ticket.status != "resolved":
        app_item.active_ticket.status = "resolved"
        app_item.active_ticket.resolved_at = now
    
    app_item.status = "operational"
    app_item.active_ticket_id = None
    db.commit()
    return {"status": "success", "message": f"{app_item.asset_label} restored to operational state."}


# ==========================================
# 2. ROOM MAINTENANCE & 2-STEP VERIFICATION
# ==========================================
@app.post("/api/v1/tickets/room", response_model=TicketResponse)
def create_room_ticket(req: RoomTicketCreateRequest, db: Session = Depends(get_db)):
    """Lodge direct room maintenance request."""
    hostel = db.query(Hostel).filter(Hostel.id == req.hostel_id).first()
    if not hostel:
        raise HTTPException(status_code=404, detail="Hostel not found")

    contact = (req.reporter_contact or "").strip()
    if not contact:
        raise HTTPException(
            status_code=400,
            detail="Mobile phone number is required so technician can contact you and dispatch SMS verification notifications."
        )

    now = datetime.datetime.utcnow()
    ticket_code = f"LAT-{random.randint(1000, 9999)}"
    score, tier = calculate_priority(req.category, 1, now, now)

    ticket = Ticket(
        ticket_code=ticket_code,
        ticket_type="room",
        hostel_id=req.hostel_id,
        floor=req.floor,
        room_number=req.room_number,
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
        ticket.student_verified = True
        ticket.student_verified_at = now
        ticket.student_feedback = req.student_feedback or "Resident confirmed work completed."
        
        # Check if 2-step verification is complete
        if ticket.tech_completed:
            ticket.status = "resolved"
            ticket.resolved_at = now
        else:
            # Student confirmed in advance
            ticket.status = "awaiting_tech_confirmation"
    else:
        # Resident reports work is still incomplete or not working
        ticket.student_verified = False
        ticket.tech_completed = False
        ticket.status = "in_progress"
        ticket.student_feedback = f"Resident reported work incomplete: {req.student_feedback or 'Defect still persists'}"

    db.commit()
    db.refresh(ticket)
    _, tier = enrich_ticket_data(ticket, now)
    return format_ticket_response(ticket, tier)


# ==========================================
# 3. STATIC FRONTEND SERVING
# ==========================================
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

if os.path.exists(FRONTEND_DIR):
    static_path = os.path.join(FRONTEND_DIR, "static")
    if os.path.exists(static_path):
        app.mount("/static", StaticFiles(directory=static_path), name="static")

    @app.get("/")
    def serve_student_ui():
        index_file = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "LATTICE · IITH Operations Console Student UI not found."}
