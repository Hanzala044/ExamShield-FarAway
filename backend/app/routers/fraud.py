from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_roles
from ..database import get_db
from ..models import (
    ROLE_COORDINATOR, ROLE_INVIGILATOR, ROLE_SUPER_ADMIN, Exam, Flag, Student,
)
from ..schemas import FlagDecision
from ..services import integrity, ledger

router = APIRouter(prefix="/fraud", tags=["fraud"])
admin = require_roles(ROLE_SUPER_ADMIN)
staff = require_roles(ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_INVIGILATOR)


@router.post("/{exam_id}/analyze")
def run_analysis(exam_id: int, db: Session = Depends(get_db), _=Depends(admin)):
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(404, "Exam not found")

    report = integrity.analyze(db, exam)

    # persist post-exam flags
    db.query(Flag).filter(Flag.exam_id == exam_id, Flag.phase == "post").delete()
    for r in report["ranked"]:
        db.add(Flag(
            exam_id=exam_id, student_id=r["student_id"], rule="identical_wrong_cluster",
            evidence_note=r["evidence"], confidence=r["score"], phase="post",
            status="confirmed", on_chain=True,
        ))
    exam.status = "analyzed"
    db.commit()

    ledger.record(db, ledger.EVENT_ANALYSIS_COMPLETE, {
        "examId": exam_id,
        "flaggedCount": report["flagged_count"],
        "clusters": len(report["clusters"]),
        "reportHash": ledger.hash_fields(exam_id, report["flagged_count"], len(report["clusters"])),
        "ts": datetime.utcnow().isoformat(),
    })
    return report


@router.get("/{exam_id}/report")
def get_report(exam_id: int, db: Session = Depends(get_db), _=Depends(admin)):
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(404, "Exam not found")
    return integrity.analyze(db, exam)


@router.get("/{exam_id}/flags")
def list_flags(exam_id: int, phase: str | None = None, center_id: int | None = None,
               db: Session = Depends(get_db), _=Depends(staff)):
    q = db.query(Flag).filter(Flag.exam_id == exam_id)
    if phase:
        q = q.filter(Flag.phase == phase)
    flags = q.order_by(Flag.ts.desc()).all()
    out = []
    for f in flags:
        s = db.get(Student, f.student_id)
        if center_id and s and s.center_id != center_id:
            continue
        out.append({
            "id": f.id, "rule": f.rule, "note": f.evidence_note,
            "confidence": f.confidence, "phase": f.phase, "status": f.status,
            "on_chain": f.on_chain,
            "student": {"id": s.id, "roll_no": s.roll_no, "name": s.full_name,
                        "seat": s.seat, "center_id": s.center_id} if s else None,
            "ts": f.ts.isoformat(),
        })
    return out


@router.post("/flags/{flag_id}/decision")
def decide_flag(flag_id: int, body: FlagDecision, db: Session = Depends(get_db),
                _=Depends(staff)):
    if body.status not in {"confirmed", "dismissed"}:
        raise HTTPException(400, "status must be confirmed or dismissed")
    flag = db.get(Flag, flag_id)
    if not flag:
        raise HTTPException(404, "Flag not found")
    flag.status = body.status
    if body.status == "confirmed" and not flag.on_chain:
        s = db.get(Student, flag.student_id)
        ledger.record(db, ledger.EVENT_ANOMALY_FLAGGED, {
            "examId": flag.exam_id,
            "flagHash": ledger.hash_fields(flag.student_id, flag.rule, flag.id, "confirmed"),
            "ts": datetime.utcnow().isoformat(),
        })
        flag.on_chain = True
    db.commit()
    return {"id": flag.id, "status": flag.status, "on_chain": flag.on_chain}
