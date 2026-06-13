import hashlib
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    Exam, ExamCenter, Flag, Question, Student, Submission, TelemetryEvent,
)
from ..schemas import StartExamRequest, SubmitRequest, TelemetryIn
from ..services import integrity, ledger
from ..services.ws_manager import manager

router = APIRouter(prefix="/session", tags=["session"])


def _resolve(db: Session, token: str) -> tuple[Student, Exam]:
    student = db.query(Student).filter(Student.session_token == token).first()
    if not student:
        raise HTTPException(401, "Invalid or expired session token")
    # the active exam assigned to this student's center
    exam = (
        db.query(Exam)
        .join(ExamCenter, ExamCenter.exam_id == Exam.id)
        .filter(ExamCenter.center_id == student.center_id)
        .filter(Exam.status.in_(["active", "closed", "distributed"]))
        .order_by(Exam.start_ts.desc())
        .first()
    )
    if not exam:
        raise HTTPException(404, "No exam assigned to this center")
    return student, exam


@router.post("/start")
def start(body: StartExamRequest, db: Session = Depends(get_db)):
    """Kiosk unlock. Returns questions only once the time-lock has released."""
    student, exam = _resolve(db, body.session_token)
    if not exam.key_released or exam.status not in ("active", "closed"):
        raise HTTPException(423, "Exam is locked. Waiting for time-lock release.")

    questions = (
        db.query(Question).filter(Question.exam_id == exam.id).order_by(Question.idx).all()
    )
    return {
        "exam": {"id": exam.id, "name": exam.name, "subject": exam.subject,
                 "duration_min": exam.duration_min},
        "student": {"name": student.full_name, "roll_no": student.roll_no, "seat": student.seat},
        "questions": [
            {"idx": q.idx, "section": q.section, "text": q.text, "options": q.options}
            for q in questions
        ],
    }


@router.post("/telemetry")
async def telemetry(body: TelemetryIn, db: Session = Depends(get_db)):
    """Stream a telemetry beat → run IntegrityAI live rules → push alerts."""
    student, exam = _resolve(db, body.session_token)

    db.add(TelemetryEvent(
        exam_id=exam.id, student_id=student.id, q_idx=body.q_idx, chosen=body.chosen,
        response_ms=body.response_ms, change_count=body.change_count, tab_switch=body.tab_switch,
    ))
    db.commit()

    question = None
    if body.q_idx is not None:
        question = db.query(Question).filter(
            Question.exam_id == exam.id, Question.idx == body.q_idx
        ).first()

    found = integrity.check_live(question, body.response_ms, body.change_count, body.tab_switch)
    pushed = []
    for f in found:
        flag = Flag(
            exam_id=exam.id, student_id=student.id, rule=f["rule"],
            evidence_note=f["note"], confidence=f["confidence"], phase="live",
        )
        db.add(flag)
        db.commit()
        db.refresh(flag)
        ledger.record(db, ledger.EVENT_ANOMALY_FLAGGED, {
            "examId": exam.id,
            "flagHash": ledger.hash_fields(student.id, f["rule"], flag.id),
            "ts": datetime.utcnow().isoformat(),
        })
        flag.on_chain = True
        db.commit()
        alert = {
            "type": "anomaly", "flag_id": flag.id, "rule": f["rule"],
            "confidence": f["confidence"], "note": f["note"],
            "student": {"id": student.id, "roll_no": student.roll_no,
                        "name": student.full_name, "seat": student.seat},
        }
        await manager.broadcast(f"center:{student.center_id}", alert)
        await manager.broadcast("admin", {**alert, "center_id": student.center_id})
        pushed.append(alert)

    return {"flags": pushed}


@router.post("/submit")
def submit(body: SubmitRequest, db: Session = Depends(get_db)):
    student, exam = _resolve(db, body.session_token)
    answers = {str(k): int(v) for k, v in body.answers.items()}
    checksum = hashlib.sha256(
        json.dumps({"s": student.id, "a": answers}, sort_keys=True).encode()
    ).hexdigest()

    existing = db.query(Submission).filter(
        Submission.exam_id == exam.id, Submission.student_id == student.id
    ).first()
    if existing:
        existing.answers = answers
        existing.checksum = checksum
        existing.submitted_ts = datetime.utcnow()
    else:
        db.add(Submission(
            exam_id=exam.id, student_id=student.id, center_id=student.center_id,
            answers=answers, checksum=checksum,
        ))
    student.session_token = None  # one-shot: kiosk locks out after submit
    db.commit()
    return {"status": "submitted", "checksum": checksum, "answered": len(answers)}
