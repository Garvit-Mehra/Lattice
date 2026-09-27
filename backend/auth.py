"""
Authentication & Authorization Helper for LATTICE · IITH Operations Console
Provides session and token verification for Technicians and Admins.
Supports secure environment variable overrides and session TTL expiration.
"""
import os
import hmac
import uuid
import datetime
from typing import Optional, Dict

# In-memory session cache (layer 1) + SQLite persistence (layer 2 for multi-process concurrency)
ACTIVE_SESSIONS: Dict[str, dict] = {}

from .database import SessionLocal
from .models import AuthSession

# Configurable Session Expiration (default: 12 hours)
SESSION_TTL_HOURS = int(os.getenv("LATTICE_SESSION_TTL_HOURS", "12"))


def get_credential_store() -> dict:
    """
    Builds credential store with environment secret overrides.
    Falls back to campus demo accounts if environment variables are unset.
    """
    admin_pwd = os.getenv("ADMIN_PASSWORD", "admin123")
    tech_pwd = os.getenv("TECH_PASSWORD", "tech123")
    iith_admin_pwd = os.getenv("IITH_ADMIN_PASSWORD", "iith_admin_2026")
    iith_tech_pwd = os.getenv("IITH_TECH_PASSWORD", "iith_tech_2026")

    # Warn if default demo passwords are in use in production environment
    if os.getenv("LATTICE_ENV") == "production" and (admin_pwd == "admin123" or tech_pwd == "tech123"):
        print("[SECURITY WARNING] Default administrator/technician passwords in use in production mode. Set ADMIN_PASSWORD and TECH_PASSWORD.")

    return {
        # Technicians
        "technician": {"password": tech_pwd, "role": "technician", "name": "Chief Campus Technician", "dept": "General Maintenance"},
        "tech_electrical": {"password": tech_pwd, "role": "technician", "name": "Ramesh (Electrical)", "dept": "Electrical"},
        "tech_plumbing": {"password": tech_pwd, "role": "technician", "name": "Suresh (Plumbing)", "dept": "Plumbing"},
        "tech_carpentry": {"password": tech_pwd, "role": "technician", "name": "Venkatesh (Carpentry)", "dept": "Carpentry"},
        "tech_network": {"password": tech_pwd, "role": "technician", "name": "Anil (LAN/Network)", "dept": "Network"},
        "iith_tech_2026": {"password": iith_tech_pwd, "role": "technician", "name": "On-Duty Technician", "dept": "Facilities"},

        # Estate Office Administrators
        "admin": {"password": admin_pwd, "role": "admin", "name": "Estate Officer (Administration)", "dept": "Estate Office"},
        "estate_admin": {"password": admin_pwd, "role": "admin", "name": "Executive Engineer", "dept": "Campus Infra"},
        "iith_admin_2026": {"password": iith_admin_pwd, "role": "admin", "name": "Dean Planning & Facilities", "dept": "Directorate"}
    }


def authenticate_user(username: str, password: str, required_role: Optional[str] = None) -> Optional[dict]:
    """Authenticates username and password; returns user payload and creates session token with TTL."""
    clean_user = username.strip().lower()
    credentials = get_credential_store()
    user = credentials.get(clean_user)
    if not user:
        return None
    
    # Constant-time comparison to guard against timing attacks
    if not hmac.compare_digest(user["password"], password.strip()):
        return None
    
    if required_role and user["role"] != required_role:
        return None

    now = datetime.datetime.utcnow()
    expires_at = now + datetime.timedelta(hours=SESSION_TTL_HOURS)

    token = f"lat_{user['role']}_{uuid.uuid4().hex}"
    session_data = {
        "token": token,
        "username": clean_user,
        "name": user["name"],
        "role": user["role"],
        "dept": user.get("dept", "General"),
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat()
    }
    ACTIVE_SESSIONS[token] = session_data

    # Persist session to SQLite so other micro-services (ports 8000, 8001, 8002) recognize it
    db = SessionLocal()
    try:
        db.add(AuthSession(
            token=token,
            username=session_data["username"],
            name=session_data["name"],
            role=session_data["role"],
            dept=session_data["dept"],
            created_at=now,
            expires_at=expires_at
        ))
        db.commit()
    except Exception as e:
        print(f"Warning: Failed to persist auth session to DB: {e}")
    finally:
        db.close()

    return session_data


def verify_session(token: str, required_role: Optional[str] = None) -> Optional[dict]:
    """Validates an active session token across memory cache and SQLite, checking expiration."""
    if not token:
        return None

    now = datetime.datetime.utcnow()

    # Check Layer 1 (in-memory cache)
    session = ACTIVE_SESSIONS.get(token)
    if not session:
        # Check Layer 2 (Shared SQLite database)
        db = SessionLocal()
        try:
            db_session = db.query(AuthSession).filter(AuthSession.token == token).first()
            if db_session:
                # Check expiration on DB record
                if db_session.expires_at and now > db_session.expires_at:
                    db.delete(db_session)
                    db.commit()
                    return None

                session = {
                    "token": db_session.token,
                    "username": db_session.username,
                    "name": db_session.name,
                    "role": db_session.role,
                    "dept": db_session.dept,
                    "created_at": db_session.created_at.isoformat() if db_session.created_at else "",
                    "expires_at": db_session.expires_at.isoformat() if db_session.expires_at else ""
                }
                ACTIVE_SESSIONS[token] = session
        except Exception as e:
            print(f"Warning: Failed reading session from DB: {e}")
        finally:
            db.close()

    if not session:
        return None

    # Check TTL Expiration
    expires_at_str = session.get("expires_at")
    if expires_at_str:
        try:
            expires_dt = datetime.datetime.fromisoformat(expires_at_str)
            if now > expires_dt:
                revoke_session(token)
                return None
        except Exception:
            pass

    if required_role and session["role"] != required_role:
        return None

    return session


def revoke_session(token: str):
    """Logs out a session from both memory cache and SQLite."""
    if token in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[token]
    
    db = SessionLocal()
    try:
        db.query(AuthSession).filter(AuthSession.token == token).delete()
        db.commit()
    except Exception as e:
        print(f"Warning: Failed revoking session from DB: {e}")
    finally:
        db.close()
