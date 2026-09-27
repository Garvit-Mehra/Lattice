"""
SQLAlchemy ORM Models for LATTICE · IITH Operations Console
"""
import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from .database import Base


class Hostel(Base):
    __tablename__ = "hostels"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    slug = Column(String(50), nullable=False, unique=True, index=True)
    total_floors = Column(Integer, default=6)
    has_ground_floor = Column(Boolean, default=False)
    description = Column(String(255), default="")

    appliances = relationship("Appliance", back_populates="hostel", cascade="all, delete-orphan")
    tickets = relationship("Ticket", back_populates="hostel", cascade="all, delete-orphan")



class Appliance(Base):
    __tablename__ = "appliances"

    id = Column(Integer, primary_key=True, index=True)
    hostel_id = Column(Integer, ForeignKey("hostels.id"), nullable=False)
    floor = Column(Integer, nullable=False)
    asset_type = Column(String(50), nullable=False)  # 'washing_machine', 'dryer', 'water_cooler'
    asset_label = Column(String(50), nullable=False)  # e.g. "WM-01", "WC-F2"
    location_desc = Column(String(100), default="")  # e.g. "Wing B, Near Lift"
    status = Column(String(50), default="operational")  # 'operational', 'faulty', 'out_of_order'
    active_ticket_id = Column(Integer, ForeignKey("tickets.id", use_alter=True, name="fk_appliance_active_ticket"), nullable=True)

    hostel = relationship("Hostel", back_populates="appliances")
    active_ticket = relationship("Ticket", foreign_keys=[active_ticket_id], post_update=True)


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_code = Column(String(20), unique=True, index=True, nullable=False)  # e.g. "LAT-8921"
    ticket_type = Column(String(50), nullable=False)  # 'common_appliance' or 'room'
    
    hostel_id = Column(Integer, ForeignKey("hostels.id"), nullable=False)
    floor = Column(Integer, nullable=True)
    room_number = Column(String(20), nullable=True)  # For room tickets
    appliance_id = Column(Integer, ForeignKey("appliances.id"), nullable=True)

    category = Column(String(50), nullable=False)  # 'electrical', 'plumbing', 'carpentry', 'network', 'appliance'
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    reporter_name = Column(String(100), default="Anonymous Student")
    reporter_contact = Column(String(50), default="")

    status = Column(String(50), default="submitted")  # 'submitted', 'in_progress', 'awaiting_student_verification', 'resolved'
    confirmations_count = Column(Integer, default=1)  # Number of students confirming the issue
    computed_priority = Column(Float, default=10.0)  # Dynamically computed priority score
    priority_overridden = Column(Boolean, default=False)  # Admin override flag to protect manual score

    # 2-Step Verification for Room Maintenance
    tech_assigned_to = Column(String(100), default="")
    tech_completed = Column(Boolean, default=False)
    tech_completed_at = Column(DateTime, nullable=True)
    tech_notes = Column(Text, default="")
    student_verified = Column(Boolean, default=False)
    student_verified_at = Column(DateTime, nullable=True)
    student_feedback = Column(Text, default="")

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    hostel = relationship("Hostel", back_populates="tickets")
    appliance = relationship("Appliance", foreign_keys=[appliance_id])
    votes = relationship("TicketVote", back_populates="ticket", cascade="all, delete-orphan")


class TicketVote(Base):
    __tablename__ = "ticket_votes"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    user_token = Column(String(100), nullable=False)  # Simple fingerprint/token to avoid duplicate votes
    voted_at = Column(DateTime, default=datetime.datetime.utcnow)

    ticket = relationship("Ticket", back_populates="votes")


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(100), unique=True, index=True, nullable=False)
    username = Column(String(100), nullable=False)
    name = Column(String(100), nullable=False)
    role = Column(String(50), nullable=False)
    dept = Column(String(100), default="General")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
