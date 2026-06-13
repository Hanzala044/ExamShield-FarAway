"""Idempotent demo seed.

Creates: 5 staff users, 3 GPS-registered centers, 50 students (2 impersonators),
one LIVE exam ready for the interactive demo (time-lock already elapsed, awaiting
key release), and one COMPLETED exam with 50 submissions containing two planted
collusion clusters so 'Run Fraud Analysis' surfaces real structure.
"""
import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .auth import hash_password
from .models import (
    ROLE_COORDINATOR, ROLE_INVIGILATOR, ROLE_SUPER_ADMIN,
    Center, Exam, ExamCenter, Question, Student, Submission, User,
)
from .services import crypto, ledger

random.seed(2026)

CENTERS = [
    {"name": "Kendriya Vidyalaya, R.K. Puram", "city": "New Delhi", "lat": 28.5639, "lon": 77.1750},
    {"name": "St. Xavier's College", "city": "Mumbai", "lat": 19.0610, "lon": 72.8295},
    {"name": "Fergusson College", "city": "Pune", "lat": 18.5214, "lon": 73.8410},
]
DISTRIBUTION = [20, 18, 12]  # students per center → 50

FIRST = ["Aarav", "Vivaan", "Aditya", "Ananya", "Diya", "Ishaan", "Kabir", "Sara",
         "Riya", "Arjun", "Myra", "Reyansh", "Anika", "Vihaan", "Kiara", "Aryan",
         "Navya", "Dhruv", "Saanvi", "Ayaan"]
LAST = ["Sharma", "Patel", "Reddy", "Nair", "Iyer", "Singh", "Gupta", "Das",
        "Menon", "Kulkarni"]


def _name(i: int) -> str:
    return f"{FIRST[i % len(FIRST)]} {LAST[(i // len(FIRST)) % len(LAST)]}"


def _questions(subject: str, n: int) -> list[dict]:
    qs = []
    for i in range(n):
        difficulty = "hard" if i % 4 == 0 else ("easy" if i % 4 == 1 else "medium")
        avg = 34.0 if difficulty == "hard" else (12.0 if difficulty == "easy" else 25.0)
        correct = random.randint(0, 3)
        qs.append({
            "text": f"[{subject}] Q{i + 1}. Sample question on topic {i + 1} "
                    f"(difficulty: {difficulty}). Select the correct option.",
            "options": [f"Option A-{i+1}", f"Option B-{i+1}",
                        f"Option C-{i+1}", f"Option D-{i+1}"],
            "correct_index": correct,
            "section": subject,
            "difficulty": difficulty,
            "avg_response_s": avg,
        })
    return qs


def _persist_exam(db: Session, name, subject, start_ts, n_q, release: bool, status: str) -> Exam:
    exam = Exam(name=name, subject=subject, start_ts=start_ts, duration_min=180, status=status)
    db.add(exam)
    db.commit()
    db.refresh(exam)

    qdefs = _questions(subject, n_q)
    for i, q in enumerate(qdefs):
        db.add(Question(
            exam_id=exam.id, idx=i, text=q["text"], options=q["options"],
            correct_index=q["correct_index"], section=q["section"],
            difficulty=q["difficulty"], avg_response_s=q["avg_response_s"],
        ))
    db.commit()

    import json
    enc = crypto.encrypt_paper(json.dumps(qdefs).encode())
    exam.blob = enc["blob"]
    exam.nonce = enc["nonce"]
    exam.blob_hash = enc["blob_hash"]
    exam.server_key_half = enc["server_key_half"]
    exam.contract_key_half = enc["contract_key_half"]
    exam.key_released = release
    db.commit()
    db.refresh(exam)
    return exam


def run(db: Session):
    if db.query(User).first():
        return  # already seeded

    # ── Centers ──
    centers = []
    for c in CENTERS:
        center = Center(name=c["name"], city=c["city"], lat=c["lat"], lon=c["lon"],
                        radius_m=150, gps_verified=True, paper_received=True,
                        session_state="standby")
        db.add(center)
        centers.append(center)
    db.commit()
    for c in centers:
        ledger.record(db, ledger.EVENT_CENTER_VERIFIED, {
            "centerId": c.id, "gpsHash": ledger.hash_fields(c.lat, c.lon, c.radius_m),
            "ts": datetime.utcnow().isoformat(),
        })

    # ── Users ──
    db.add(User(username="admin", password_hash=hash_password("admin123"),
                full_name="NTA Control Room", role=ROLE_SUPER_ADMIN))
    for i, c in enumerate(centers, start=1):
        db.add(User(username=f"coord{i}", password_hash=hash_password("coord123"),
                    full_name=f"Coordinator — {c.city}", role=ROLE_COORDINATOR, center_id=c.id))
    db.add(User(username="invig1", password_hash=hash_password("invig123"),
                full_name="Invigilator — New Delhi", role=ROLE_INVIGILATOR, center_id=centers[0].id))
    db.commit()

    # ── Students (50) ──
    students = []
    impostors = {5, 25}  # demo: face match will fall below threshold for these
    n = 0
    for ci, count in enumerate(DISTRIBUTION):
        for s in range(count):
            n += 1
            roll = f"NEET2026-{n:04d}"
            stu = Student(
                roll_no=roll, full_name=_name(n - 1), center_id=centers[ci].id,
                seat=f"{chr(65 + ci)}-{s + 1:03d}",
                reg_photo_hash=ledger.hash_fields("photo", roll),
                true_match=(n not in impostors),
            )
            db.add(stu)
            students.append(stu)
    db.commit()

    # ── Exam 1: LIVE interactive demo (time-lock already elapsed, key withheld) ──
    live = _persist_exam(
        db, "NEET-UG 2026 — Physics (LIVE DEMO)", "Physics",
        datetime.utcnow() - timedelta(minutes=2), n_q=15, release=False, status="distributed",
    )
    for c in centers:
        db.add(ExamCenter(exam_id=live.id, center_id=c.id, acknowledged=True))
    db.commit()
    ledger.record(db, ledger.EVENT_PAPER_DISTRIBUTED, {
        "examId": live.id, "blobHash": live.blob_hash,
        "unlockTs": live.start_ts.isoformat(), "centers": [c.id for c in centers],
    })

    # ── Exam 2: COMPLETED, with planted collusion clusters for fraud analysis ──
    done = _persist_exam(
        db, "NEET-UG 2026 — Biology (Completed)", "Biology",
        datetime.utcnow() - timedelta(days=1), n_q=20, release=True, status="closed",
    )
    for c in centers:
        db.add(ExamCenter(exam_id=done.id, center_id=c.id, acknowledged=True))
    db.commit()
    ledger.record(db, ledger.EVENT_PAPER_DISTRIBUTED, {
        "examId": done.id, "blobHash": done.blob_hash,
        "unlockTs": done.start_ts.isoformat(), "centers": [c.id for c in centers],
    })

    correct = {q.idx: q.correct_index for q in done.questions}
    n_q = len(correct)

    def base_answers(accuracy: float) -> dict:
        ans = {}
        for qi, ci in correct.items():
            ans[str(qi)] = ci if random.random() < accuracy else (ci + random.randint(1, 3)) % 4
        return ans

    # planted clusters: members share an identical set of WRONG answers
    cluster_a = students[2:6]    # 4 candidates (Delhi)
    cluster_b = students[22:25]  # 3 candidates (Mumbai)
    wrong_a = {str(qi): (correct[qi] + 1) % 4 for qi in range(0, 12)}  # 12 shared wrongs
    wrong_b = {str(qi): (correct[qi] + 2) % 4 for qi in range(3, 13)}  # 10 shared wrongs

    cluster_ids = {s.id for s in cluster_a + cluster_b}
    for stu in students:
        ans = base_answers(0.7)
        if stu in cluster_a:
            ans.update(wrong_a)
        elif stu in cluster_b:
            ans.update(wrong_b)
        import hashlib, json
        checksum = hashlib.sha256(
            json.dumps({"s": stu.id, "a": ans}, sort_keys=True).encode()
        ).hexdigest()
        db.add(Submission(exam_id=done.id, student_id=stu.id, center_id=stu.center_id,
                          answers=ans, checksum=checksum))
    db.commit()

    for c in centers:
        ledger.record(db, ledger.EVENT_SESSION_CLOSED, {
            "examId": done.id, "centerId": c.id,
            "submissionCount": db.query(Submission).filter(
                Submission.exam_id == done.id, Submission.center_id == c.id).count(),
            "checksum": ledger.hash_fields("session", done.id, c.id),
            "ts": datetime.utcnow().isoformat(),
        })
