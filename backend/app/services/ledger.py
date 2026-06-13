"""ChainLedger — simulated Polygon audit trail.

Stores only cryptographic hashes of critical events (never papers, answers, or
PII). Blocks are hash-chained (each carries the previous payload hash) so any
retroactive edit breaks the chain and is detectable. A public read endpoint
mirrors a block explorer for citizen verification.

To go live: implement the same `record()` signature against a deployed Solidity
contract via ethers/web3 and flip settings.chain_simulated.
"""
import hashlib
import json
import os
from datetime import datetime

from sqlalchemy.orm import Session

from ..models import LedgerEvent

GENESIS = "0" * 64

# The six PRD event types.
EVENT_PAPER_DISTRIBUTED = "PaperDistributed"
EVENT_CENTER_VERIFIED = "CenterVerified"
EVENT_STUDENT_CHECKED_IN = "StudentCheckedIn"
EVENT_KEY_RELEASED = "KeyReleased"
EVENT_SESSION_OPENED = "SessionOpened"
EVENT_SESSION_CLOSED = "SessionClosed"
EVENT_ANOMALY_FLAGGED = "AnomalyFlagged"
EVENT_ANALYSIS_COMPLETE = "AnalysisComplete"


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def record(db: Session, event_type: str, payload: dict) -> LedgerEvent:
    last = db.query(LedgerEvent).order_by(LedgerEvent.id.desc()).first()
    prev_hash = last.payload_hash if last else GENESIS
    block_number = (last.block_number + 1) if last else 1

    payload_hash = hashlib.sha256((_canonical(payload) + prev_hash).encode()).hexdigest()
    tx_hash = "0x" + hashlib.sha256((payload_hash + os.urandom(8).hex()).encode()).hexdigest()

    ev = LedgerEvent(
        block_number=block_number,
        tx_hash=tx_hash,
        event_type=event_type,
        payload=payload,
        payload_hash=payload_hash,
        prev_hash=prev_hash,
        ts=datetime.utcnow(),
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


def hash_fields(*parts) -> str:
    """sha256 of arbitrary fields — used to put a proof on-chain without PII."""
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()


def verify_chain(db: Session) -> dict:
    events = db.query(LedgerEvent).order_by(LedgerEvent.id.asc()).all()
    prev = GENESIS
    for ev in events:
        expected = hashlib.sha256((_canonical(ev.payload) + prev).encode()).hexdigest()
        if expected != ev.payload_hash or ev.prev_hash != prev:
            return {"valid": False, "broken_at_block": ev.block_number}
        prev = ev.payload_hash
    return {"valid": True, "blocks": len(events)}
