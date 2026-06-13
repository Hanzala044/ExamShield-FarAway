import hashlib
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_roles
from ..database import get_db
from ..models import (
    ROLE_COORDINATOR, ROLE_INVIGILATOR, ROLE_SUPER_ADMIN,
    Center, Exam, ExamCenter, Student, Submission, User,
)
from ..schemas import (
    CenterOut, CheckInRequest, OverrideRequest, ReleaseKeyRequest,
)
from ..services import crypto, face, ledger
from ..services.ws_manager import manager

router = APIRouter(prefix="/centers", tags=["centers"])
staff = require_roles(ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_INVIGILATOR)
coordinator = require_roles(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)


@router.get("", response_model=list[CenterOut])
def list_centers(db: Session = Depends(get_db), _=Depends(staff)):
    return db.query(Center).order_by(Center.id).all()


@router.get("/{center_id}", response_model=CenterOut)
def get_center(center_id: int, db: Session = Depends(get_db), _=Depends(staff)):
    c = db.get(Center, center_id)
    if not c:
        raise HTTPException(404, "Center not found")
    return c


@router.post("/{center_id}/verify-gps", response_model=CenterOut)
def verify_gps(center_id: int, db: Session = Depends(get_db), user: User = Depends(coordinator)):
    c = db.get(Center, center_id)
    if not c:
        raise HTTPException(404, "Center not found")
    c.gps_verified = True
    db.commit()
    gps_hash = ledger.hash_fields(c.lat, c.lon, c.radius_m)
    ledger.record(db, ledger.EVENT_CENTER_VERIFIED, {
        "centerId": c.id, "gpsHash": gps_hash, "ts": datetime.utcnow().isoformat(),
    })
    db.refresh(c)
    return c


@router.get("/{center_id}/exams")
def center_exams(center_id: int, db: Session = Depends(get_db), _=Depends(staff)):
    rows = (
        db.query(Exam)
        .join(ExamCenter, ExamCenter.exam_id == Exam.id)
        .filter(ExamCenter.center_id == center_id)
        .order_by(Exam.start_ts.desc())
        .all()
    )
    return [{
        "id": e.id, "name": e.name, "subject": e.subject, "status": e.status,
        "key_released": e.key_released, "start_ts": e.start_ts.isoformat(),
    } for e in rows]


@router.get("/{center_id}/students")
def center_students(center_id: int, db: Session = Depends(get_db), _=Depends(staff)):
    rows = db.query(Student).filter(Student.center_id == center_id).order_by(Student.seat).all()
    return [{
        "id": s.id, "roll_no": s.roll_no, "name": s.full_name, "seat": s.seat,
        "checked_in": s.checked_in, "match_score": s.match_score, "override": s.override,
    } for s in rows]


def _issue_token(student: Student) -> str:
    return "sess_" + hashlib.sha256(f"{student.id}:{os.urandom(8).hex()}".encode()).hexdigest()[:24]


def _log_checkin(db: Session, student: Student, result: str, score: float):
    h = ledger.hash_fields(student.id, student.center_id, result, round(score, 3))
    ledger.record(db, ledger.EVENT_STUDENT_CHECKED_IN, {
        "studentHash": ledger.hash_fields(student.id),
        "centerId": student.center_id,
        "result": result,
        "checkinHash": h,
        "ts": datetime.utcnow().isoformat(),
    })


@router.post("/{center_id}/checkin")
def checkin(center_id: int, body: CheckInRequest, db: Session = Depends(get_db),
            user: User = Depends(coordinator)):
    """VerifyGate face match. Auto-pass >= threshold; otherwise needs override."""
    student = db.query(Student).filter(
        Student.roll_no == body.roll_no, Student.center_id == center_id
    ).first()
    if not student:
        raise HTTPException(404, "No such student at this center")

    result = face.compare(student, body.captured_token)
    student.match_score = result["score"]

    if result["passed"]:
        student.checked_in = True
        student.override = False
        student.session_token = _issue_token(student)
        db.commit()
        _log_checkin(db, student, "match", result["score"])
        return {
            "status": "checked_in", "match": True, "score": result["score"],
            "session_token": student.session_token, "seat": student.seat,
            "name": student.full_name,
        }

    db.commit()
    return {
        "status": "mismatch", "match": False, "score": result["score"],
        "threshold": result["threshold"], "student_id": student.id,
        "name": student.full_name,
        "message": "Confidence below threshold. Coordinator override required.",
    }


@router.post("/{center_id}/override")
def override(center_id: int, body: OverrideRequest, db: Session = Depends(get_db),
             user: User = Depends(coordinator)):
    """Manual override — logged on-chain either way; no silent bypass."""
    student = db.get(Student, body.student_id)
    if not student or student.center_id != center_id:
        raise HTTPException(404, "No such student at this center")

    if body.approve:
        student.checked_in = True
        student.override = True
        student.session_token = _issue_token(student)
        db.commit()
        ledger.record(db, ledger.EVENT_STUDENT_CHECKED_IN, {
            "studentHash": ledger.hash_fields(student.id),
            "centerId": center_id,
            "result": "manual_override",
            "by": user.username,
            "reason": body.reason,
            "ts": datetime.utcnow().isoformat(),
        })
        return {"status": "checked_in", "override": True, "session_token": student.session_token}

    ledger.record(db, ledger.EVENT_STUDENT_CHECKED_IN, {
        "studentHash": ledger.hash_fields(student.id),
        "centerId": center_id, "result": "denied",
        "by": user.username, "reason": body.reason,
        "ts": datetime.utcnow().isoformat(),
    })
    return {"status": "denied", "override": False}


@router.post("/release-key")
async def release_key(body: ReleaseKeyRequest, db: Session = Depends(get_db),
                      user: User = Depends(coordinator)):
    """Time-lock + geofence gated key release. Mirrors the Solidity releaseKey()."""
    exam = db.get(Exam, body.exam_id)
    center = db.get(Center, body.center_id)
    if not exam or not center:
        raise HTTPException(404, "Exam or center not found")

    now = datetime.utcnow()
    if now < exam.start_ts:
        remaining = int((exam.start_ts - now).total_seconds())
        raise HTTPException(423, f"Time-lock active. Key releases in {remaining}s.")

    ok, dist = crypto.within_geofence(
        center.lat, center.lon, center.radius_m, body.device_lat, body.device_lon
    )
    if not ok:
        raise HTTPException(
            403, f"Geofence check failed. Device is {dist:.0f}m from center "
                 f"(allowed: {center.radius_m}m). Key withheld.",
        )

    # Reassemble + verify by decrypting (GCM auth tag proves integrity).
    key = crypto.reassemble_key(exam.server_key_half, exam.contract_key_half)
    try:
        crypto.decrypt_paper(exam.blob, exam.nonce, key)
    except Exception:
        raise HTTPException(500, "Decryption failed — blob integrity error")

    exam.key_released = True
    exam.status = "active"
    center.session_state = "active"
    db.commit()

    ledger.record(db, ledger.EVENT_KEY_RELEASED, {
        "examId": exam.id, "centerId": center.id, "ts": now.isoformat(),
    })
    ledger.record(db, ledger.EVENT_SESSION_OPENED, {
        "examId": exam.id, "centerId": center.id, "ts": now.isoformat(),
    })
    await manager.broadcast(f"center:{center.id}", {
        "type": "session_opened", "exam_id": exam.id,
        "message": "Time-lock cleared. Exam is now live.",
    })
    return {"status": "released", "geofence_distance_m": round(dist, 1)}


@router.post("/{center_id}/state")
def set_state(center_id: int, state: str, db: Session = Depends(get_db),
              user: User = Depends(coordinator)):
    c = db.get(Center, center_id)
    if not c:
        raise HTTPException(404, "Center not found")
    if state not in {"standby", "checkin", "active", "locked"}:
        raise HTTPException(400, "Invalid state")
    c.session_state = state
    db.commit()
    return {"center_id": center_id, "session_state": state}


@router.post("/close-session")
def close_session(exam_id: int, center_id: int, db: Session = Depends(get_db),
                  user: User = Depends(coordinator)):
    """Lock the session and write a tamper-evident submission checksum on-chain."""
    exam = db.get(Exam, exam_id)
    center = db.get(Center, center_id)
    if not exam or not center:
        raise HTTPException(404, "Exam or center not found")

    subs = db.query(Submission).filter(
        Submission.exam_id == exam_id, Submission.center_id == center_id
    ).all()
    checksum = hashlib.sha256(
        "|".join(sorted(s.checksum or "" for s in subs)).encode()
    ).hexdigest()
    center.session_state = "locked"
    if exam.status == "active":
        exam.status = "closed"
    db.commit()

    ledger.record(db, ledger.EVENT_SESSION_CLOSED, {
        "examId": exam_id, "centerId": center_id,
        "submissionCount": len(subs), "checksum": checksum,
        "ts": datetime.utcnow().isoformat(),
    })
    return {"status": "locked", "submission_count": len(subs), "checksum": checksum}
