"""
LATTICE · IITH Operations Console - FastAPI Application
Smart Hostel Maintenance & Crowd-Triage Platform for IITH
"""
import os
import random
import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from .database import engine, get_db, Base
from .models import Hostel, Appliance, Ticket, TicketVote
from .schemas import (
    HostelResponse, ApplianceResponse, ApplianceReportRequest,
    RoomTicketCreateRequest, TicketResponse, TicketVoteRequest,
    TicketStatusUpdateRequest, DashboardStatsResponse, SLAMetric,
    StudentVerifyWorkRequest
)
from .scoring import calculate_priority

# Ensure DB tables exist
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="LATTICE · IITH Operations Console API",
    description="Smart Campus Maintenance & Dynamic Crowd-Triage System for IIT Hyderabad",
    version="1.0.0"
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
    if path == "/" or path == "/presentation" or path.endswith(".js") or path.endswith(".html") or path.endswith(".css"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Helper function to compute priority tier and refreshed score
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


# ==========================================
# 1. HOSTELS API
# ==========================================
@app.get("/api/v1/hostels", response_model=List[HostelResponse])
def get_hostels(db: Session = Depends(get_db)):
    """Returns all IITH hostels."""
    return db.query(Hostel).order_by(Hostel.name).all()


# ==========================================
# 2. APPLIANCES & CROWD-TRIAGE API
# ==========================================
@app.get("/api/v1/appliances", response_model=List[ApplianceResponse])
def get_appliances(
    hostel_id: Optional[int] = None,
    floor: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Returns floor-wise washing machines, dryers, and water coolers
    with active crowd incident details.
    """
    query = db.query(Appliance).join(Hostel)
    if hostel_id:
        query = query.filter(Appliance.hostel_id == hostel_id)
    if floor:
        query = query.filter(Appliance.floor == floor)

    appliances = query.order_by(Appliance.floor, Appliance.asset_type, Appliance.asset_label).all()
    results = []
    now = datetime.datetime.utcnow()

    for app in appliances:
        ticket = app.active_ticket
        if ticket and ticket.status != "resolved":
            score, tier = enrich_ticket_data(ticket, now)
            confirmations = ticket.confirmations_count
            issue_desc = ticket.description
            ticket_id = ticket.id
        else:
            score, tier = 0.0, "OPERATIONAL"
            confirmations = 0
            issue_desc = None
            ticket_id = None

        results.append(ApplianceResponse(
            id=app.id,
            hostel_id=app.hostel_id,
            hostel_name=app.hostel.name,
            floor=app.floor,
            asset_type=app.asset_type,
            asset_label=app.asset_label,
            location_desc=app.location_desc,
            status=app.status,
            active_ticket_id=ticket_id,
            confirmations_count=confirmations,
            priority_score=score,
            priority_tier=tier,
            issue_description=issue_desc
        ))

    return results


@app.post("/api/v1/appliances/report", response_model=TicketResponse)
def report_appliance(req: ApplianceReportRequest, db: Session = Depends(get_db)):
    """
    First student reports an appliance issue.
    Creates a new community incident ticket and marks appliance as faulty.
    """
    app = db.query(Appliance).filter(Appliance.id == req.appliance_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Appliance not found")

    now = datetime.datetime.utcnow()

    # If already an active ticket, increment confirmation count instead of duplicating
    if app.active_ticket and app.active_ticket.status != "resolved":
        ticket = app.active_ticket
        ticket.confirmations_count += 1
        score, tier = enrich_ticket_data(ticket, now)
        db.add(TicketVote(ticket_id=ticket.id, user_token=req.user_token or "anon"))
        db.commit()
        db.refresh(ticket)
        return format_ticket_response(ticket, tier)

    # Generate new ticket code
    ticket_code = f"LAT-{random.randint(1000, 9999)}"
    title = f"{app.asset_label} on Floor {app.floor} reported {app.asset_type.replace('_', ' ')} failure"
    
    score, tier = calculate_priority(app.asset_type, 1, now, now)

    new_ticket = Ticket(
        ticket_code=ticket_code,
        ticket_type="common_appliance",
        hostel_id=app.hostel_id,
        floor=app.floor,
        appliance_id=app.id,
        category=app.asset_type,
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

    app.status = "faulty"
    app.active_ticket_id = new_ticket.id
    db.add(TicketVote(ticket_id=new_ticket.id, user_token=req.user_token or "anon"))

    db.commit()
    db.refresh(new_ticket)
    return format_ticket_response(new_ticket, tier)


@app.post("/api/v1/appliances/{appliance_id}/confirm", response_model=TicketResponse)
def confirm_appliance_broken(
    appliance_id: int,
    req: TicketVoteRequest,
    db: Session = Depends(get_db)
):
    """
    '+1 Confirm Broken' crowd verification.
    Increases priority score dynamically without creating a duplicate ticket!
    """
    app = db.query(Appliance).filter(Appliance.id == appliance_id).first()
    if not app or not app.active_ticket:
        raise HTTPException(status_code=404, detail="No active incident found for this appliance.")

    ticket = app.active_ticket
    if ticket.status == "resolved":
        raise HTTPException(status_code=400, detail="Incident already resolved.")

    # Check for duplicate vote from same user token
    existing_vote = db.query(TicketVote).filter(
        TicketVote.ticket_id == ticket.id,
        TicketVote.user_token == req.user_token
    ).first()

    if not existing_vote:
        db.add(TicketVote(ticket_id=ticket.id, user_token=req.user_token))
        ticket.confirmations_count += 1

    now = datetime.datetime.utcnow()
    score, tier = enrich_ticket_data(ticket, now)
    
    # If confirmations >= 3, mark as high priority / out of order
    if ticket.confirmations_count >= 3 and app.status == "faulty":
        app.status = "out_of_order"

    db.commit()
    db.refresh(ticket)
    return format_ticket_response(ticket, tier)


@app.post("/api/v1/appliances/{appliance_id}/resolve-crowd")
def crowd_report_working(appliance_id: int, db: Session = Depends(get_db)):
    """Students confirm the appliance is working again."""
    app = db.query(Appliance).filter(Appliance.id == appliance_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Appliance not found")

    now = datetime.datetime.utcnow()
    if app.active_ticket and app.active_ticket.status != "resolved":
        app.active_ticket.status = "resolved"
        app.active_ticket.resolved_at = now
    
    app.status = "operational"
    app.active_ticket_id = None
    db.commit()
    return {"status": "success", "message": f"{app.asset_label} restored to operational state."}


# ==========================================
# 3. PERSONAL ROOM MAINTENANCE TICKETS
# ==========================================
@app.post("/api/v1/tickets/room", response_model=TicketResponse)
def create_room_ticket(req: RoomTicketCreateRequest, db: Session = Depends(get_db)):
    """Logs a direct room maintenance ticket for electrical, plumbing, carpentry, or network."""
    hostel = db.query(Hostel).filter(Hostel.id == req.hostel_id).first()
    if not hostel:
        raise HTTPException(status_code=404, detail="Hostel not found")

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
        reporter_contact=req.reporter_contact or "",
        status="submitted",
        confirmations_count=1,
        computed_priority=score,
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


# ==========================================
# 4. ADMIN & DISPATCH QUEUE API
# ==========================================
@app.get("/api/v1/admin/queue", response_model=List[TicketResponse])
def get_prioritized_queue(
    status_filter: Optional[str] = None,
    category_filter: Optional[str] = None,
    hostel_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Returns incident queue dynamically ranked by crowd-priority score.
    """
    now = datetime.datetime.utcnow()
    query = db.query(Ticket).join(Hostel)

    if status_filter:
        query = query.filter(Ticket.status == status_filter)
    else:
        query = query.filter(Ticket.status != "resolved")

    if category_filter:
        query = query.filter(Ticket.category == category_filter)
    if hostel_id:
        query = query.filter(Ticket.hostel_id == hostel_id)

    tickets = query.all()
    enriched = []
    for t in tickets:
        score, tier = enrich_ticket_data(t, now)
        t.computed_priority = score
        enriched.append((score, t, tier))

    # Sort descending by priority score
    enriched.sort(key=lambda x: x[0], reverse=True)

    db.commit()  # Save refreshed scores
    return [format_ticket_response(item[1], item[2]) for item in enriched]


@app.patch("/api/v1/tickets/{ticket_id}/status", response_model=TicketResponse)
def update_ticket_status(
    ticket_id: int,
    req: TicketStatusUpdateRequest,
    db: Session = Depends(get_db)
):
    """Update ticket workflow status: acknowledged -> in_progress -> resolved."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    now = datetime.datetime.utcnow()
    ticket.status = req.status
    ticket.updated_at = now

    if req.status == "resolved":
        ticket.resolved_at = now
        # If it was tied to an appliance, restore appliance
        if ticket.appliance_id:
            app = db.query(Appliance).filter(Appliance.id == ticket.appliance_id).first()
            if app:
                app.status = "operational"
                app.active_ticket_id = None

    db.commit()
    db.refresh(ticket)
    _, tier = enrich_ticket_data(ticket, now)
    return format_ticket_response(ticket, tier)


@app.post("/api/v1/tickets/{ticket_code}/verify", response_model=TicketResponse)
def student_verify_room_work(
    ticket_code: str,
    req: StudentVerifyWorkRequest,
    db: Session = Depends(get_db)
):
    """
    Step 2 of 2-Step Verification for Room Maintenance:
    Student confirms if technician work resolved the issue in their room.
    """
    ticket = db.query(Ticket).filter(Ticket.ticket_code == ticket_code.upper()).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    now = datetime.datetime.utcnow()

    if req.verified:
        ticket.student_verified = True
        ticket.student_verified_at = now
        ticket.student_feedback = req.student_feedback or "Resident confirmed work completed."
        
        if ticket.tech_completed:
            ticket.status = "resolved"
            ticket.resolved_at = now
        else:
            ticket.status = "awaiting_tech_confirmation"
    else:
        ticket.student_verified = False
        ticket.tech_completed = False
        ticket.status = "in_progress"
        ticket.student_feedback = f"Resident reported work incomplete: {req.student_feedback or 'Defect still persists'}"

    db.commit()
    db.refresh(ticket)
    _, tier = enrich_ticket_data(ticket, now)
    return format_ticket_response(ticket, tier)



# ==========================================
# 5. SLA & DASHBOARD ANALYTICS API
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


# Helper serializer
def format_ticket_response(t: Ticket, tier: str) -> TicketResponse:
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
        created_at=t.created_at,
        updated_at=t.updated_at,
        resolved_at=t.resolved_at
    )


# ==========================================
# 6. STATIC ASSET SERVING FOR FRONTEND
# ==========================================
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

if os.path.exists(FRONTEND_DIR):
    static_path = os.path.join(FRONTEND_DIR, "static")
    if os.path.exists(static_path):
        app.mount("/static", StaticFiles(directory=static_path), name="static")

    @app.get("/")
    def serve_frontend():
        index_file = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "Frontend index.html not found, visit /docs for API."}

    @app.get("/presentation")
    def serve_presentation():
        pres_file = os.path.join(os.path.dirname(FRONTEND_DIR), "presentation", "index.html")
        if os.path.exists(pres_file):
            return FileResponse(pres_file)
        return {"message": "Presentation slides not found."}


# Sub-mount Technician and Admin backends for unified single-port access
try:
    from .tech_app import app as tech_fastapi_app
    app.mount("/tech", tech_fastapi_app)
except Exception as e:
    print(f"Warning: Could not mount tech_app: {e}")

try:
    from .admin_app import app as admin_fastapi_app
    app.mount("/admin", admin_fastapi_app)
except Exception as e:
    print(f"Warning: Could not mount admin_app: {e}")


