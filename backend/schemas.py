"""
Pydantic Schemas for LATTICE · IITH Operations Console API
"""
from typing import List, Optional
from pydantic import BaseModel
import datetime


class HostelResponse(BaseModel):
    id: int
    name: str
    slug: str
    total_floors: int
    has_ground_floor: bool = False
    description: str

    class Config:
        from_attributes = True



class ApplianceResponse(BaseModel):
    id: int
    hostel_id: int
    hostel_name: str
    floor: int
    asset_type: str
    asset_label: str
    location_desc: str
    status: str
    active_ticket_id: Optional[int] = None
    confirmations_count: int = 0
    working_confirmations_count: int = 0
    required_working_confirmations: int = 2
    priority_score: float = 0.0
    priority_tier: str = "LOW"
    issue_description: Optional[str] = None

    class Config:
        from_attributes = True


class ApplianceReportRequest(BaseModel):
    appliance_id: int
    issue_description: str
    user_token: Optional[str] = "anon_user"
    reporter_name: Optional[str] = "Hostel Resident"


class ApplianceResolveCrowdRequest(BaseModel):
    user_token: Optional[str] = "anon_user"


class RoomTicketCreateRequest(BaseModel):
    hostel_id: int
    room_number: str
    floor: int
    category: str  # electrical, plumbing, carpentry, network
    title: str
    description: str
    reporter_name: Optional[str] = "Hostel Resident"
    reporter_contact: str  # Mandatory phone number for technician callback & SMS notifications


class TicketResponse(BaseModel):
    id: int
    ticket_code: str
    ticket_type: str
    hostel_id: int
    hostel_name: str
    floor: Optional[int] = None
    room_number: Optional[str] = None
    appliance_id: Optional[int] = None
    category: str
    title: str
    description: str
    reporter_name: str
    reporter_contact: Optional[str] = ""
    status: str
    confirmations_count: int
    computed_priority: float
    priority_tier: str
    priority_overridden: Optional[bool] = False
    
    # 2-Step Verification & SMS Notification
    tech_assigned_to: Optional[str] = ""
    tech_completed: bool = False
    tech_completed_at: Optional[datetime.datetime] = None
    tech_notes: Optional[str] = ""
    student_verified: bool = False
    student_verified_at: Optional[datetime.datetime] = None
    student_feedback: Optional[str] = ""
    sms_dispatched: Optional[bool] = False
    sms_notification_text: Optional[str] = None

    created_at: datetime.datetime
    updated_at: datetime.datetime
    resolved_at: Optional[datetime.datetime] = None


    class Config:
        from_attributes = True


class TicketVoteRequest(BaseModel):
    user_token: Optional[str] = "anon_user"


class TicketStatusUpdateRequest(BaseModel):
    status: str  # submitted, in_progress, awaiting_student_verification, resolved
    resolution_note: Optional[str] = None


# --- Technician & Admin Authentication ---
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str
    role: str
    name: str


# --- 2-Step Verification Requests ---
class TechAssignRequest(BaseModel):
    tech_name: str = "Technician"


class TechCompleteWorkRequest(BaseModel):
    tech_notes: str
    tech_name: Optional[str] = "Technician"


class StudentVerifyWorkRequest(BaseModel):
    verified: bool  # True if resident confirms work completed, False if rejected
    student_feedback: Optional[str] = ""


# --- Admin Control Requests ---
class AdminTicketOverrideRequest(BaseModel):
    status: Optional[str] = None
    computed_priority: Optional[float] = None
    tech_assigned_to: Optional[str] = None
    tech_notes: Optional[str] = None
    override_reason: Optional[str] = None
    force_resolve: Optional[bool] = False


class AdminApplianceStatusRequest(BaseModel):
    status: str  # 'operational', 'faulty', 'out_of_order'


class SLAMetric(BaseModel):
    hostel_id: int
    hostel_name: str
    avg_resolution_hours: float
    total_resolved: int
    total_pending: int
    open_incidents: Optional[int] = None
    resolved_count: Optional[int] = None
    performance_rating: str  # 'Excellent', 'Good', 'Needs Improvement'


class DashboardStatsResponse(BaseModel):
    total_active_tickets: int
    total_critical_tickets: int
    critical_tickets: Optional[int] = None
    total_appliances_monitored: int
    appliances_operational_pct: float
    operational_appliance_pct: Optional[float] = None
    avg_resolution_time_hrs: Optional[float] = None
    sla_metrics: List[SLAMetric]


# ─── SMS OTP Schemas ───────────────────────────────────────────────────────────

class OtpSendRequest(BaseModel):
    """Request an OTP SMS to a phone number."""
    phone: str
    purpose: str = "login"   # login | ticket | step2


class OtpSendResponse(BaseModel):
    success: bool
    master_bypass: bool = False   # True → skip OTP entry, log in immediately
    message: str = ""
    # Only present in dev/demo mode (no Twilio creds configured)
    dev_code: Optional[str] = None


class OtpVerifyRequest(BaseModel):
    """Verify an OTP code for a given phone and purpose."""
    phone: str
    code: str
    purpose: str = "login"


class OtpVerifyResponse(BaseModel):
    verified: bool
    message: str = ""


# ─── Phone-OTP based Login (Tech & Admin) ─────────────────────────────────────

class PhoneLoginRequest(BaseModel):
    """Step 1: initiate OTP login by phone number."""
    phone: str


class PhoneOtpLoginRequest(BaseModel):
    """Step 2: complete OTP login by phone + code."""
    phone: str
    code: str


# ─── Admin-managed TechUser CRUD ──────────────────────────────────────────────

class TechUserCreateRequest(BaseModel):
    username: str
    name: str
    phone: str
    dept: Optional[str] = "General Maintenance"


class TechUserUpdateRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    dept: Optional[str] = None
    is_active: Optional[bool] = None


class TechUserResponse(BaseModel):
    id: int
    username: str
    name: str
    phone: str
    dept: str
    is_active: bool
    created_at: datetime.datetime
    created_by: str

    class Config:
        from_attributes = True


# ─── Student OTP Phone Verification ───────────────────────────────────────────

class PhoneOtpVerifyTicketRequest(BaseModel):
    """After OTP is verified, attach verified_otp_token to the room ticket submit."""
    phone: str
    code: str


