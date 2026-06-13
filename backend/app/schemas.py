from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ── Auth ──
class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str
    center_id: Optional[int] = None


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    center_id: Optional[int] = None

    class Config:
        from_attributes = True


# ── Exam / paper ──
class QuestionIn(BaseModel):
    text: str
    options: list[str]
    correct_index: int
    section: str = "General"
    difficulty: str = "medium"
    avg_response_s: float = 25.0


class ExamCreate(BaseModel):
    name: str
    subject: str
    start_ts: datetime
    duration_min: int = 180
    center_ids: list[int] = []


class PaperUpload(BaseModel):
    questions: list[QuestionIn]


class ExamOut(BaseModel):
    id: int
    name: str
    subject: str
    start_ts: datetime
    duration_min: int
    status: str
    key_released: bool
    blob_hash: Optional[str] = None

    class Config:
        from_attributes = True


# ── Centers ──
class CenterOut(BaseModel):
    id: int
    name: str
    city: str
    lat: float
    lon: float
    radius_m: int
    gps_verified: bool
    paper_received: bool
    session_state: str

    class Config:
        from_attributes = True


# ── Check-in ──
class CheckInRequest(BaseModel):
    roll_no: str
    captured_token: str = "live"


class OverrideRequest(BaseModel):
    student_id: int
    approve: bool
    reason: str


# ── Session ──
class ReleaseKeyRequest(BaseModel):
    exam_id: int
    center_id: int
    device_lat: float
    device_lon: float


# ── Student exam ──
class StartExamRequest(BaseModel):
    session_token: str


class TelemetryIn(BaseModel):
    session_token: str
    q_idx: Optional[int] = None
    chosen: Optional[int] = None
    response_ms: Optional[int] = None
    change_count: int = 0
    tab_switch: bool = False


class SubmitRequest(BaseModel):
    session_token: str
    answers: dict[str, int]


# ── Flags ──
class FlagDecision(BaseModel):
    status: str  # confirmed|dismissed
