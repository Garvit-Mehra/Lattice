"""
LATTICE · IITH Operations Console — SMS & OTP Service
Wraps Twilio to send OTP codes. Supports:
  - Master phone bypass (hackathon demo)
  - In-memory + SQLite OTP store with 5-minute TTL
  - 6-digit TOTP-style codes
"""
import os
import random
import datetime
from typing import Optional

# ─── Configuration ────────────────────────────────────────────────────────────

TWILIO_ACCOUNT_SID  = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN   = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER  = os.getenv("TWILIO_FROM_NUMBER", "")   # e.g. "+14155238886"

# Demo master number — entering this phone skips OTP and goes straight to dashboard.
# Set to "" or remove env var in production.
MASTER_PHONE_NUMBER = os.getenv("LATTICE_MASTER_PHONE", "+919999999999")

OTP_TTL_SECONDS = int(os.getenv("LATTICE_OTP_TTL_SECONDS", "300"))   # 5 minutes

# ─── In-Memory OTP Store (backed by SQLite for cross-worker persistence) ─────

_OTP_CACHE: dict[str, dict] = {}  # phone → {code, expires_at, purpose}


def _normalise_phone(phone: str) -> str:
    """Strips spaces/dashes and ensures Indian numbers have +91 prefix."""
    clean = phone.strip().replace(" ", "").replace("-", "")
    digits_only = clean.lstrip("+")
    if digits_only.startswith("91") and len(digits_only) == 12:
        return f"+{digits_only}"
    if len(digits_only) == 10 and digits_only[0] in "6789":
        return f"+91{digits_only}"
    return clean if clean.startswith("+") else f"+{clean}"


def is_master_number(phone: str) -> bool:
    """Returns True if the phone matches the bypass master number."""
    if not MASTER_PHONE_NUMBER:
        return False
    return _normalise_phone(phone) == _normalise_phone(MASTER_PHONE_NUMBER)


def generate_otp(phone: str, purpose: str = "login") -> str:
    """Generates a 6-digit OTP, stores it, and returns it (caller sends SMS)."""
    code = f"{random.randint(100000, 999999)}"
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=OTP_TTL_SECONDS)
    normalised = _normalise_phone(phone)
    _OTP_CACHE[normalised] = {
        "code": code,
        "expires_at": expires_at,
        "purpose": purpose,
    }
    # Persist to SQLite for multi-process durability
    try:
        from .database import SessionLocal
        from .models import OtpRecord
        db = SessionLocal()
        try:
            existing = db.query(OtpRecord).filter(OtpRecord.phone == normalised).first()
            if existing:
                existing.code = code
                existing.expires_at = expires_at
                existing.purpose = purpose
            else:
                db.add(OtpRecord(phone=normalised, code=code, expires_at=expires_at, purpose=purpose))
            db.commit()
        finally:
            db.close()
    except Exception as e:
        print(f"[OTP] Warning: could not persist OTP to DB: {e}")

    return code


def verify_otp(phone: str, code: str, purpose: str = "login") -> bool:
    """Validates OTP. Returns True on success and immediately invalidates it."""
    normalised = _normalise_phone(phone)
    now = datetime.datetime.utcnow()

    record = _OTP_CACHE.get(normalised)
    if not record:
        # Try SQLite fallback
        try:
            from .database import SessionLocal
            from .models import OtpRecord
            db = SessionLocal()
            try:
                db_rec = db.query(OtpRecord).filter(OtpRecord.phone == normalised).first()
                if db_rec:
                    record = {
                        "code": db_rec.code,
                        "expires_at": db_rec.expires_at,
                        "purpose": db_rec.purpose,
                    }
            finally:
                db.close()
        except Exception:
            pass

    if not record:
        return False
    if record.get("purpose") != purpose:
        return False
    if now > record["expires_at"]:
        _OTP_CACHE.pop(normalised, None)
        return False
    if record["code"] != code.strip():
        return False

    # Invalidate after successful use
    _OTP_CACHE.pop(normalised, None)
    try:
        from .database import SessionLocal
        from .models import OtpRecord
        db = SessionLocal()
        try:
            db.query(OtpRecord).filter(OtpRecord.phone == normalised).delete()
            db.commit()
        finally:
            db.close()
    except Exception:
        pass

    return True


def send_otp_sms(phone: str, purpose: str = "login") -> dict:
    """
    Sends an OTP SMS via Twilio. Returns {success, code (dev only), master_bypass}.
    If TWILIO_* credentials are absent, falls back to console-only mode (dev).
    """
    normalised = _normalise_phone(phone)

    # Master bypass — no SMS needed
    if is_master_number(normalised):
        return {"success": True, "master_bypass": True, "message": "Master number — OTP bypassed."}

    code = generate_otp(normalised, purpose)

    purpose_labels = {
        "login":        "LATTICE Portal Login",
        "ticket":       "LATTICE Ticket Verification",
        "step2":        "LATTICE Work Completion Verify",
    }
    label = purpose_labels.get(purpose, "LATTICE")
    body  = f"[{label}] Your OTP is {code}. Valid for 5 minutes. Do not share."

    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER:
        try:
            from twilio.rest import Client
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            client.messages.create(body=body, from_=TWILIO_FROM_NUMBER, to=normalised)
            print(f"[SMS] OTP sent to {normalised} via Twilio.")
            return {"success": True, "master_bypass": False}
        except Exception as e:
            print(f"[SMS] Twilio error: {e}")
            return {"success": False, "error": str(e)}
    else:
        # Dev / demo mode — print OTP to console
        print(f"[SMS DEV] OTP for {normalised} ({purpose}): {code}")
        return {"success": True, "master_bypass": False, "dev_code": code}
