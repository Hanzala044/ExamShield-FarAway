"""VerifyGate — simulated biometric face match.

Production swaps this for AWS Rekognition / Azure Face (CompareFaces + liveness).
The simulation is deterministic per student so demos are repeatable: students
flagged `true_match=False` in the seed model an impersonator and score below the
threshold, exercising the manual-override + on-chain mismatch path.
"""
import hashlib

from ..config import settings
from ..models import Student


def compare(student: Student, captured_token: str = "live") -> dict:
    """Returns a confidence score in [0,1] and pass/fail vs the threshold.

    `captured_token` stands in for the live webcam frame; we fold it + the
    enrolled photo hash into a deterministic pseudo-score.
    """
    seed = hashlib.sha256(
        f"{student.reg_photo_hash}:{captured_token}".encode()
    ).hexdigest()
    jitter = int(seed[:4], 16) / 0xFFFF  # 0..1

    if student.true_match:
        score = round(0.88 + jitter * 0.11, 3)   # 0.88 .. 0.99
    else:
        score = round(0.55 + jitter * 0.25, 3)   # 0.55 .. 0.80 (below threshold)

    return {
        "score": score,
        "passed": score >= settings.face_match_threshold,
        "threshold": settings.face_match_threshold,
        "liveness": True,
    }
