from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_roles
from ..database import get_db
from ..models import (
    ROLE_SUPER_ADMIN, Center, Exam, ExamCenter, Question,
)
from ..schemas import ExamCreate, ExamOut, PaperUpload
from ..services import crypto, ledger

router = APIRouter(prefix="/exams", tags=["exams"])
admin_only = require_roles(ROLE_SUPER_ADMIN)


@router.get("", response_model=list[ExamOut])
def list_exams(db: Session = Depends(get_db), _=Depends(require_roles(ROLE_SUPER_ADMIN))):
    return db.query(Exam).order_by(Exam.id.desc()).all()


@router.post("", response_model=ExamOut)
def create_exam(body: ExamCreate, db: Session = Depends(get_db), _=Depends(admin_only)):
    exam = Exam(
        name=body.name, subject=body.subject,
        start_ts=body.start_ts, duration_min=body.duration_min, status="draft",
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)
    for cid in body.center_ids:
        if db.get(Center, cid):
            db.add(ExamCenter(exam_id=exam.id, center_id=cid))
    db.commit()
    return exam


@router.post("/{exam_id}/paper", response_model=ExamOut)
def upload_paper(exam_id: int, body: PaperUpload, db: Session = Depends(get_db), _=Depends(admin_only)):
    """Encrypt the paper (AES-256-GCM, split key) and purge plaintext."""
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(404, "Exam not found")
    if not body.questions:
        raise HTTPException(400, "Paper has no questions")

    # Persist question structure (the answer key stays server-side only).
    db.query(Question).filter(Question.exam_id == exam_id).delete()
    for i, q in enumerate(body.questions):
        db.add(Question(
            exam_id=exam_id, idx=i, text=q.text, options=q.options,
            correct_index=q.correct_index, section=q.section,
            difficulty=q.difficulty, avg_response_s=q.avg_response_s,
        ))

    plaintext = body.model_dump_json().encode()
    enc = crypto.encrypt_paper(plaintext)           # plaintext is now discarded
    exam.blob = enc["blob"]
    exam.nonce = enc["nonce"]
    exam.blob_hash = enc["blob_hash"]
    exam.server_key_half = enc["server_key_half"]
    exam.contract_key_half = enc["contract_key_half"]
    exam.key_released = False
    db.commit()
    db.refresh(exam)
    return exam


@router.post("/{exam_id}/distribute", response_model=ExamOut)
def distribute(exam_id: int, db: Session = Depends(get_db), _=Depends(admin_only)):
    """Push the encrypted blob to assigned centers; write time-lock on-chain."""
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(404, "Exam not found")
    if not exam.blob:
        raise HTTPException(400, "Upload and encrypt a paper first")

    assignments = db.query(ExamCenter).filter(ExamCenter.exam_id == exam_id).all()
    if not assignments:
        raise HTTPException(400, "No centers assigned to this exam")
    for a in assignments:
        a.acknowledged = True
        center = db.get(Center, a.center_id)
        if center:
            center.paper_received = True
            center.session_state = "standby"
    exam.status = "distributed"
    db.commit()

    ledger.record(db, ledger.EVENT_PAPER_DISTRIBUTED, {
        "examId": exam.id,
        "blobHash": exam.blob_hash,
        "unlockTs": exam.start_ts.isoformat(),
        "centers": [a.center_id for a in assignments],
    })
    db.refresh(exam)
    return exam


@router.get("/{exam_id}/centers")
def exam_centers(exam_id: int, db: Session = Depends(get_db), _=Depends(admin_only)):
    rows = db.query(ExamCenter).filter(ExamCenter.exam_id == exam_id).all()
    out = []
    for r in rows:
        c = db.get(Center, r.center_id)
        out.append({
            "center_id": r.center_id, "name": c.name if c else "?",
            "city": c.city if c else "?", "acknowledged": r.acknowledged,
            "session_state": c.session_state if c else "?",
            "gps_verified": c.gps_verified if c else False,
        })
    return out
