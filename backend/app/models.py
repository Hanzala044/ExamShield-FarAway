from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text,
)
from sqlalchemy.orm import relationship

from .database import Base


# ── Roles ──────────────────────────────────────────────────────────────────
ROLE_SUPER_ADMIN = "super_admin"
ROLE_COORDINATOR = "coordinator"
ROLE_INVIGILATOR = "invigilator"
ROLE_STUDENT = "student"
ALL_ROLES = {ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_INVIGILATOR, ROLE_STUDENT}


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    center_id = Column(Integer, ForeignKey("centers.id"), nullable=True)


class Center(Base):
    __tablename__ = "centers"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    city = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    radius_m = Column(Integer, default=150)            # geofence radius
    gps_verified = Column(Boolean, default=False)
    paper_received = Column(Boolean, default=False)
    session_state = Column(String, default="standby")  # standby|checkin|active|locked


class Exam(Base):
    __tablename__ = "exams"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    start_ts = Column(DateTime, nullable=False)
    duration_min = Column(Integer, default=180)
    status = Column(String, default="draft")  # draft|distributed|active|closed|analyzed
    # PaperVault: encrypted blob + split-key material
    blob = Column(Text, nullable=True)              # base64 ciphertext
    nonce = Column(String, nullable=True)           # hex GCM nonce
    blob_hash = Column(String, nullable=True)       # sha256 of ciphertext
    server_key_half = Column(String, nullable=True)    # hex, server vault half
    contract_key_half = Column(String, nullable=True)  # hex, "smart contract" half
    key_released = Column(Boolean, default=False)
    questions = relationship("Question", back_populates="exam", cascade="all, delete-orphan")


class ExamCenter(Base):
    __tablename__ = "exam_centers"
    id = Column(Integer, primary_key=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    center_id = Column(Integer, ForeignKey("centers.id"), nullable=False)
    acknowledged = Column(Boolean, default=False)


class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True)
    roll_no = Column(String, unique=True, nullable=False, index=True)  # encoded in QR
    full_name = Column(String, nullable=False)
    center_id = Column(Integer, ForeignKey("centers.id"), nullable=False)
    seat = Column(String, nullable=True)
    reg_photo_hash = Column(String, nullable=False)  # stand-in for enrolled biometric
    true_match = Column(Boolean, default=True)       # demo: False => impersonator
    checked_in = Column(Boolean, default=False)
    match_score = Column(Float, nullable=True)
    override = Column(Boolean, default=False)
    session_token = Column(String, nullable=True)


class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    idx = Column(Integer, nullable=False)           # 0-based position
    section = Column(String, default="General")
    text = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)          # list[str]
    correct_index = Column(Integer, nullable=False)
    difficulty = Column(String, default="medium")   # easy|medium|hard
    avg_response_s = Column(Float, default=25.0)    # national average for the rule engine
    exam = relationship("Exam", back_populates="questions")


class Submission(Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    center_id = Column(Integer, ForeignKey("centers.id"), nullable=False)
    answers = Column(JSON, nullable=False)          # {"0": 2, "1": 0, ...}
    submitted_ts = Column(DateTime, default=datetime.utcnow)
    checksum = Column(String, nullable=True)


class TelemetryEvent(Base):
    __tablename__ = "telemetry"
    id = Column(Integer, primary_key=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    q_idx = Column(Integer, nullable=True)
    chosen = Column(Integer, nullable=True)
    response_ms = Column(Integer, nullable=True)
    change_count = Column(Integer, default=0)
    tab_switch = Column(Boolean, default=False)
    ts = Column(DateTime, default=datetime.utcnow)


class Flag(Base):
    __tablename__ = "flags"
    id = Column(Integer, primary_key=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    rule = Column(String, nullable=False)
    evidence_note = Column(Text, nullable=False)
    confidence = Column(Float, default=0.5)
    phase = Column(String, default="live")          # live|post
    status = Column(String, default="pending")      # pending|confirmed|dismissed
    on_chain = Column(Boolean, default=False)
    ts = Column(DateTime, default=datetime.utcnow)


class LedgerEvent(Base):
    """Simulated Polygon block. Hash-chained for tamper-evidence, exposed via a
    public read endpoint mirroring a block explorer."""
    __tablename__ = "ledger_events"
    id = Column(Integer, primary_key=True)
    block_number = Column(Integer, nullable=False)
    tx_hash = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    payload_hash = Column(String, nullable=False, index=True)
    prev_hash = Column(String, nullable=False)
    ts = Column(DateTime, default=datetime.utcnow)
