"""
Authentication & Authorization Helper for LATTICE · IITH Operations Console
Provides session and token verification for Technicians and Admins.
"""
import uuid
import datetime
from typing import Optional, Dict

# In-memory session store (sufficient for hackathon demo; persisted while server runs)
ACTIVE_SESSIONS: Dict[str, dict] = {}

# Pre-configured Accounts for IITH Campus
CREDENTIALS = {
    # Technicians
    "technician": {"password": "tech123", "role": "technician", "name": "Chief Campus Technician", "dept": "General Maintenance"},
    "tech_electrical": {"password": "tech123", "role": "technician", "name": "Ramesh (Electrical)", "dept": "Electrical"},
    "tech_plumbing": {"password": "tech123", "role": "technician", "name": "Suresh (Plumbing)", "dept": "Plumbing"},
    "tech_carpentry": {"password": "tech123", "role": "technician", "name": "Venkatesh (Carpentry)", "dept": "Carpentry"},
    "tech_network": {"password": "tech123", "role": "technician", "name": "Anil (LAN/Network)", "dept": "Network"},
    "iith_tech_2026": {"password": "iith_tech_2026", "role": "technician", "name": "On-Duty Technician", "dept": "Facilities"},

    # Estate Office Administrators
    "admin": {"password": "admin123", "role": "admin", "name": "Estate Officer (Administration)", "dept": "Estate Office"},
    "estate_admin": {"password": "admin123", "role": "admin", "name": "Executive Engineer", "dept": "Campus Infra"},
    "iith_admin_2026": {"password": "iith_admin_2026", "role": "admin", "name": "Dean Planning & Facilities", "dept": "Directorate"}
}


def authenticate_user(username: str, password: str, required_role: Optional[str] = None) -> Optional[dict]:
    """Authenticates username and password; returns user payload and creates session token."""
    user = CREDENTIALS.get(username.strip().lower())
    if not user:
        return None
    
    if user["password"] != password.strip():
        return None
    
    if required_role and user["role"] != required_role:
        return None

    token = f"lat_{user['role']}_{uuid.uuid4().hex}"
    session_data = {
        "token": token,
        "username": username,
        "name": user["name"],
        "role": user["role"],
        "dept": user.get("dept", "General"),
        "created_at": datetime.datetime.utcnow().isoformat()
    }
    ACTIVE_SESSIONS[token] = session_data
    return session_data


def verify_session(token: str, required_role: Optional[str] = None) -> Optional[dict]:
    """Validates an active session token."""
    if not token:
        return None
    session = ACTIVE_SESSIONS.get(token)
    if not session:
        return None
    if required_role and session["role"] != required_role:
        return None
    return session


def revoke_session(token: str):
    """Logs out a session."""
    if token in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[token]
