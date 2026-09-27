"""
LATTICE · IITH Operations Console — Technician Backend API (Port 8001)
Dedicated portal for maintenance technicians to inspect water cooler/washing machine breakdowns,
manage room maintenance complaints, and execute Step 1 of the 2-step verification.
"""
import os
import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .database import engine, get_db, Base
from .models import Hostel, Appliance, Ticket, TicketVote
from .schemas import (
    LoginRequest, LoginResponse, TechAssignRequest,
    TechCompleteWorkRequest, ApplianceResponse, TicketResponse
)
from .scoring import calculate_priority
from .auth import authenticate_user, verify_session, revoke_session

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="LATTICE · IITH Operations Console - Technician API",
    description="Dedicated Technician Portal — Water Coolers, Laundry & 2-Step Room Maintenance",
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


def get_current_tech(authorization: Optional[str] = Header(None)) -> dict:
    """Verifies technician session token."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required. Please login.")
    token = authorization.replace("Bearer ", "").strip()
    session = verify_session(token, required_role="technician")
    if not session:
        # Also allow admin to access technician endpoints
        session_admin = verify_session(token, required_role="admin")
        if not session_admin:
            raise HTTPException(status_code=401, detail="Invalid or expired technician session.")
        return session_admin
    return session


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
# 1. AUTHENTICATION
# ==========================================
@app.post("/api/v1/tech/login", response_model=LoginResponse)
def tech_login(req: LoginRequest):
    """Authenticate technician credentials."""
    session = authenticate_user(req.username, req.password, required_role="technician")
    if not session:
        # Fallback to test admin logging into tech panel
        session = authenticate_user(req.username, req.password, required_role="admin")
        if not session:
            raise HTTPException(status_code=401, detail="Invalid technician credentials.")

    return LoginResponse(
        token=session["token"],
        username=session["username"],
        role=session["role"],
        name=session["name"]
    )


@app.post("/api/v1/tech/logout")
def tech_logout(authorization: Optional[str] = Header(None)):
    """Logs out technician."""
    if authorization:
        token = authorization.replace("Bearer ", "").strip()
        revoke_session(token)
    return {"status": "success", "message": "Logged out successfully."}


@app.get("/api/v1/tech/me")
def tech_me(tech: dict = Depends(get_current_tech)):
    """Returns profile of currently logged-in technician."""
    return tech


# ==========================================
# 2. TAB 1: COMMON APPLIANCES (WATER & LAUNDRY)
# ==========================================
@app.get("/api/v1/tech/appliances/faulty", response_model=List[ApplianceResponse])
def get_faulty_appliances(
    asset_type: Optional[str] = None,
    hostel_id: Optional[int] = None,
    db: Session = Depends(get_db),
    tech: dict = Depends(get_current_tech)
):
    """
    Returns water coolers and washing machines with active breakdowns,
    ranked dynamically by student confirmation count and severity score.
    """
    query = db.query(Appliance).join(Hostel).filter(
        (Appliance.status != "operational") | (Appliance.active_ticket_id != None)
    )
    if asset_type:
        query = query.filter(Appliance.asset_type == asset_type)
    if hostel_id:
        query = query.filter(Appliance.hostel_id == hostel_id)

    appliances = query.all()
    now = datetime.datetime.utcnow()
    results = []

    for app_item in appliances:
        ticket = app_item.active_ticket
        confs = ticket.confirmations_count if ticket else 1
        score = ticket.computed_priority if ticket else 10.0
        tier = "LOW"
        issue_desc = ticket.description if ticket else "Reported malfunctioning"

        if ticket and ticket.status != "resolved":
            score, tier = enrich_ticket_data(ticket, now)

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

    # Sort descending by priority score
    results.sort(key=lambda x: x.priority_score, reverse=True)
    return results


@app.post("/api/v1/tech/appliances/{appliance_id}/status")
def update_appliance_status(
    appliance_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    tech: dict = Depends(get_current_tech)
):
    """
    Technician updates appliance status:
    - 'in_progress': technician has dispatched
    - 'operational': technician has fixed the appliance
    - 'out_of_order': parts ordered / decommissioned
    """
    app_item = db.query(Appliance).filter(Appliance.id == appliance_id).first()
    if not app_item:
        raise HTTPException(status_code=404, detail="Appliance not found")

    new_status = payload.get("status")
    notes = payload.get("notes", "")

    if new_status not in ["operational", "faulty", "out_of_order", "in_progress"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    now = datetime.datetime.utcnow()
    app_item.status = new_status

    if app_item.active_ticket and app_item.active_ticket.status != "resolved":
        if new_status == "operational":
            app_item.active_ticket.status = "resolved"
            app_item.active_ticket.resolved_at = now
            app_item.active_ticket.tech_notes = notes or f"Restored to operational by {tech['name']}"
            app_item.active_ticket_id = None
        elif new_status == "in_progress":
            app_item.active_ticket.status = "in_progress"
            app_item.active_ticket.tech_assigned_to = tech["name"]

    db.commit()
    return {"status": "success", "message": f"{app_item.asset_label} status updated to {new_status}."}


# ==========================================
# 3. TAB 2: ROOM MAINTENANCE & 2-STEP RESOLUTION
# ==========================================
@app.get("/api/v1/tech/tickets/room", response_model=List[TicketResponse])
def get_room_tickets(
    status_filter: Optional[str] = "active",  # active, awaiting_verification, resolved, all
    category: Optional[str] = None,
    hostel_id: Optional[int] = None,
    db: Session = Depends(get_db),
    tech: dict = Depends(get_current_tech)
):
    """
    Returns room maintenance requests.
    Technicians can see incoming defects, assigned tasks, and tickets awaiting student verification.
    """
    query = db.query(Ticket).filter(Ticket.ticket_type == "room")

    if status_filter == "active":
        query = query.filter(Ticket.status != "resolved")
    elif status_filter == "awaiting_verification":
        query = query.filter(Ticket.status == "awaiting_student_verification")
    elif status_filter == "resolved":
        query = query.filter(Ticket.status == "resolved")

    if category:
        query = query.filter(Ticket.category == category)
    if hostel_id:
        query = query.filter(Ticket.hostel_id == hostel_id)

    tickets = query.order_by(Ticket.computed_priority.desc(), Ticket.created_at.desc()).all()
    now = datetime.datetime.utcnow()
    results = []

    for t in tickets:
        _, tier = enrich_ticket_data(t, now)
        results.append(format_ticket_response(t, tier))

    return results


@app.post("/api/v1/tech/tickets/{ticket_id}/assign", response_model=TicketResponse)
def assign_room_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    tech: dict = Depends(get_current_tech)
):
    """Technician accepts / claims a room maintenance ticket."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.status = "in_progress"
    ticket.tech_assigned_to = tech["name"]
    db.commit()
    db.refresh(ticket)
    _, tier = enrich_ticket_data(ticket)
    return format_ticket_response(ticket, tier)


@app.post("/api/v1/tech/tickets/{ticket_id}/complete", response_model=TicketResponse)
def tech_complete_room_work(
    ticket_id: int,
    req: TechCompleteWorkRequest,
    db: Session = Depends(get_db),
    tech: dict = Depends(get_current_tech)
):
    """
    STEP 1 OF 2-STEP VERIFICATION:
    Technician marks the physical work as completed in the resident's room.
    Does NOT disappear from active queue until the student verifies.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    now = datetime.datetime.utcnow()
    ticket.tech_completed = True
    ticket.tech_completed_at = now
    ticket.tech_assigned_to = req.tech_name or tech["name"]

    # Trigger SMS notification simulation to the student's phone
    sms_notice = ""
    if ticket.reporter_contact:
        sms_notice = f"[SMS Alert Dispatched to {ticket.reporter_contact} at {now.strftime('%H:%M')}]: LATTICE: Tech {ticket.tech_assigned_to} completed repairs for Room {ticket.room_number or ''}. Ticket Reference: #{ticket.ticket_code}. Please verify at http://localhost:8000"
        print(f"[SMS NOTIFICATION SERVICE] -> {ticket.reporter_contact}: {sms_notice}")

    combined_notes = req.tech_notes
    if sms_notice:
        combined_notes = f"{req.tech_notes} | {sms_notice}".strip(" | ")
    ticket.tech_notes = combined_notes

    # If student has already verified, resolve immediately
    if ticket.student_verified:
        ticket.status = "resolved"
        ticket.resolved_at = now
    else:
        # Move to Step 2: Awaiting resident confirmation
        ticket.status = "awaiting_student_verification"

    db.commit()
    db.refresh(ticket)
    _, tier = enrich_ticket_data(ticket, now)
    return format_ticket_response(ticket, tier)


# ==========================================
# 4. STATIC FRONTEND SERVING
# ==========================================
TECH_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "technician")

if os.path.exists(TECH_DIR):
    static_path = os.path.join(TECH_DIR, "static")
    if os.path.exists(static_path):
        app.mount("/static", StaticFiles(directory=static_path), name="static")

    @app.get("/")
    def serve_tech_ui():
        index_file = os.path.join(TECH_DIR, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "LATTICE · IITH Operations Console Technician UI not found."}
