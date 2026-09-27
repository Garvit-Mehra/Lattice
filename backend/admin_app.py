"""
LATTICE · IITH Operations Console — Admin / Estate Office Backend API (Port 8002)
Super-admin control suite for monitoring campus-wide SLA metrics,
managing all 21 hostels & 279 appliances, and overriding any ticket or resolution state.
"""
import os
import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from .database import engine, get_db, Base
from .models import Hostel, Appliance, Ticket, TicketVote
from .schemas import (
    LoginRequest, LoginResponse, DashboardStatsResponse,
    SLAMetric, TicketResponse, ApplianceResponse,
    AdminTicketOverrideRequest, AdminApplianceStatusRequest
)
from .scoring import calculate_priority
from .auth import authenticate_user, verify_session, revoke_session

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="LATTICE · IITH Operations Console - Admin API",
    description="Super-Admin Control Suite — Estate Office Dispatch & Campus SLA Governance",
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


def get_current_admin(authorization: Optional[str] = Header(None)) -> dict:
    """Verifies estate admin session token."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Estate Admin authentication required.")
    token = authorization.replace("Bearer ", "").strip()
    session = verify_session(token, required_role="admin")
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired admin session.")
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
@app.post("/api/v1/admin/login", response_model=LoginResponse)
def admin_login(req: LoginRequest):
    """Authenticate estate admin credentials."""
    session = authenticate_user(req.username, req.password, required_role="admin")
    if not session:
        raise HTTPException(status_code=401, detail="Invalid estate administrator credentials.")

    return LoginResponse(
        token=session["token"],
        username=session["username"],
        role=session["role"],
        name=session["name"]
    )


@app.post("/api/v1/admin/logout")
def admin_logout(authorization: Optional[str] = Header(None)):
    """Logs out admin."""
    if authorization:
        token = authorization.replace("Bearer ", "").strip()
        revoke_session(token)
    return {"status": "success", "message": "Admin session terminated."}


@app.get("/api/v1/admin/me")
def admin_me(admin: dict = Depends(get_current_admin)):
    """Returns profile of currently logged-in administrator."""
    return admin


# ==========================================
# 2. KPI DASHBOARD & SLA ANALYTICS
# ==========================================
@app.get("/api/v1/admin/dashboard/stats", response_model=DashboardStatsResponse)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """Returns campus KPIs, active critical counts, appliance health %, and SLA metrics."""
    now = datetime.datetime.utcnow()
    total_appliances = db.query(Appliance).count()
    operational_appliances = db.query(Appliance).filter(Appliance.status == "operational").count()
    operational_pct = (operational_appliances / total_appliances * 100.0) if total_appliances > 0 else 100.0

    active_tickets = db.query(Ticket).filter(Ticket.status != "resolved").all()
    critical_count = 0
    for t in active_tickets:
        _, tier = enrich_ticket_data(t, now)
        if tier in ["CRITICAL", "HIGH"]:
            critical_count += 1

    hostels = db.query(Hostel).order_by(Hostel.name).all()
    sla_metrics = []

    for h in hostels:
        resolved_tickets = db.query(Ticket).filter(
            Ticket.hostel_id == h.id,
            Ticket.status == "resolved",
            Ticket.resolved_at != None
        ).all()

        pending_count = db.query(Ticket).filter(
            Ticket.hostel_id == h.id,
            Ticket.status != "resolved"
        ).count()

        if resolved_tickets:
            total_hours = sum((t.resolved_at - t.created_at).total_seconds() / 3600.0 for t in resolved_tickets)
            avg_hours = round(total_hours / len(resolved_tickets), 1)
        else:
            avg_hours = 12.0  # baseline campus SLA

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
            open_incidents=pending_count,
            resolved_count=len(resolved_tickets),
            performance_rating=rating
        ))

    all_resolved = db.query(Ticket).filter(Ticket.status == "resolved", Ticket.resolved_at != None).all()
    overall_avg = round(sum((t.resolved_at - t.created_at).total_seconds() / 3600.0 for t in all_resolved) / len(all_resolved), 1) if all_resolved else 8.5

    return DashboardStatsResponse(
        total_active_tickets=len(active_tickets),
        total_critical_tickets=critical_count,
        critical_tickets=critical_count,
        total_appliances_monitored=total_appliances,
        appliances_operational_pct=round(operational_pct, 1),
        operational_appliance_pct=round(operational_pct, 1),
        avg_resolution_time_hrs=overall_avg,
        sla_metrics=sla_metrics
    )


# ==========================================
# 3. TICKET GOVERNANCE & OVERRIDE
# ==========================================
@app.get("/api/v1/admin/tickets", response_model=List[TicketResponse])
def get_all_tickets(
    ticket_type: Optional[str] = None,  # 'common_appliance', 'room', None for all
    status_filter: Optional[str] = None,
    hostel_id: Optional[int] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """Search and filter all tickets across campus."""
    query = db.query(Ticket)
    if ticket_type:
        if ticket_type == "appliance":
            query = query.filter(Ticket.ticket_type == "common_appliance")
        else:
            query = query.filter(Ticket.ticket_type == ticket_type)

    if status_filter and status_filter != "all":
        if status_filter == "active":
            query = query.filter(Ticket.status != "resolved")
        elif status_filter == "awaiting_verification":
            query = query.filter(Ticket.status == "awaiting_student_verification")
        elif status_filter == "resolved":
            query = query.filter(Ticket.status == "resolved")
        else:
            query = query.filter(Ticket.status == status_filter)

    if hostel_id:
        query = query.filter(Ticket.hostel_id == hostel_id)
    if category:
        query = query.filter(Ticket.category == category)

    tickets = query.order_by(Ticket.computed_priority.desc(), Ticket.created_at.desc()).all()
    now = datetime.datetime.utcnow()
    results = []
    for t in tickets:
        _, tier = enrich_ticket_data(t, now)
        results.append(format_ticket_response(t, tier))
    return results


@app.patch("/api/v1/admin/tickets/{ticket_id}/override", response_model=TicketResponse)
def admin_override_ticket(
    ticket_id: int,
    req: AdminTicketOverrideRequest,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """
    Super-admin override:
    Force resolve, change priority score, update status, or bypass 2-step verification.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    now = datetime.datetime.utcnow()

    if req.force_resolve:
        ticket.status = "resolved"
        ticket.resolved_at = now
        ticket.tech_completed = True
        ticket.student_verified = True
        reason_str = req.override_reason or req.tech_notes or "Force-resolved by Estate Officer"
        ticket.tech_notes = f"{ticket.tech_notes or ''} | [Estate Officer Override ({admin['name']})]: {reason_str}".strip(" | ")
        if ticket.appliance:
            ticket.appliance.status = "operational"
            ticket.appliance.active_ticket_id = None
    elif req.status:
        ticket.status = req.status
        if req.status == "resolved":
            ticket.resolved_at = now
            ticket.tech_completed = True
            ticket.student_verified = True
        elif req.status == "in_progress":
            ticket.resolved_at = None

    if req.computed_priority is not None:
        ticket.computed_priority = req.computed_priority

    if req.tech_assigned_to is not None:
        ticket.tech_assigned_to = req.tech_assigned_to

    if req.tech_notes and not req.force_resolve:
        ticket.tech_notes = f"{ticket.tech_notes or ''} | [Admin Note]: {req.tech_notes}".strip(" | ")
    elif req.override_reason and not req.force_resolve:
        ticket.tech_notes = f"{ticket.tech_notes or ''} | [Override Reason]: {req.override_reason}".strip(" | ")

    db.commit()
    db.refresh(ticket)
    _, tier = enrich_ticket_data(ticket, now)
    return format_ticket_response(ticket, tier)


@app.delete("/api/v1/admin/tickets/{ticket_id}")
def admin_delete_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """Admin can delete invalid or test tickets."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.appliance:
        ticket.appliance.active_ticket_id = None
        ticket.appliance.status = "operational"

    db.delete(ticket)
    db.commit()
    return {"status": "success", "message": f"Ticket {ticket.ticket_code} deleted successfully."}


# ==========================================
# 4. CAMPUS APPLIANCES GOVERNANCE
# ==========================================
@app.get("/api/v1/admin/appliances", response_model=List[ApplianceResponse])
def get_all_campus_appliances(
    hostel_id: Optional[int] = None,
    asset_type: Optional[str] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """View and filter all 279 campus appliances."""
    query = db.query(Appliance).join(Hostel)
    if hostel_id:
        query = query.filter(Appliance.hostel_id == hostel_id)
    if asset_type:
        query = query.filter(Appliance.asset_type == asset_type)
    if status_filter:
        query = query.filter(Appliance.status == status_filter)

    apps = query.order_by(Appliance.hostel_id, Appliance.floor, Appliance.asset_type).all()
    now = datetime.datetime.utcnow()
    results = []

    for a in apps:
        confs = a.active_ticket.confirmations_count if a.active_ticket else 0
        score = 0.0
        tier = "LOW"
        issue_desc = None
        if a.active_ticket and a.active_ticket.status != "resolved":
            score, tier = enrich_ticket_data(a.active_ticket, now)
            issue_desc = a.active_ticket.description

        results.append(ApplianceResponse(
            id=a.id,
            hostel_id=a.hostel_id,
            hostel_name=a.hostel.name,
            floor=a.floor,
            asset_type=a.asset_type,
            asset_label=a.asset_label,
            location_desc=a.location_desc,
            status=a.status,
            active_ticket_id=a.active_ticket_id,
            confirmations_count=confs,
            priority_score=score,
            priority_tier=tier,
            issue_description=issue_desc
        ))

    return results


@app.patch("/api/v1/admin/appliances/{appliance_id}/status")
def admin_update_appliance_status(
    appliance_id: int,
    req: AdminApplianceStatusRequest,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """Directly override status of any campus appliance."""
    app_item = db.query(Appliance).filter(Appliance.id == appliance_id).first()
    if not app_item:
        raise HTTPException(status_code=404, detail="Appliance not found")

    app_item.status = req.status
    if req.status == "operational" and app_item.active_ticket:
        app_item.active_ticket.status = "resolved"
        app_item.active_ticket.resolved_at = datetime.datetime.utcnow()
        app_item.active_ticket_id = None

    db.commit()
    return {"status": "success", "message": f"{app_item.asset_label} status updated to {req.status}."}


# ==========================================
# 5. STATIC FRONTEND SERVING
# ==========================================
ADMIN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "admin")

if os.path.exists(ADMIN_DIR):
    static_path = os.path.join(ADMIN_DIR, "static")
    if os.path.exists(static_path):
        app.mount("/static", StaticFiles(directory=static_path), name="static")

    @app.get("/")
    def serve_admin_ui():
        index_file = os.path.join(ADMIN_DIR, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "LATTICE · IITH Operations Console Admin UI not found."}
