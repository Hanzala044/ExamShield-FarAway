"""Public Audit Trail — no authentication. Mirrors a block explorer: any
citizen, journalist, or court can confirm an event occurred without seeing any
private data."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import LedgerEvent
from ..services import ledger as ledger_svc

router = APIRouter(prefix="/audit", tags=["public-audit"])


def _serialize(ev: LedgerEvent) -> dict:
    return {
        "block_number": ev.block_number,
        "tx_hash": ev.tx_hash,
        "explorer_url": settings.chain_explorer_base + ev.tx_hash,
        "event_type": ev.event_type,
        "payload": ev.payload,
        "payload_hash": ev.payload_hash,
        "prev_hash": ev.prev_hash,
        "ts": ev.ts.isoformat(),
    }


@router.get("/events")
def events(event_type: str | None = None, limit: int = 200, db: Session = Depends(get_db)):
    q = db.query(LedgerEvent)
    if event_type:
        q = q.filter(LedgerEvent.event_type == event_type)
    rows = q.order_by(LedgerEvent.block_number.desc()).limit(limit).all()
    return [_serialize(e) for e in rows]


@router.get("/verify")
def verify_hash(hash: str, db: Session = Depends(get_db)):
    ev = db.query(LedgerEvent).filter(
        (LedgerEvent.payload_hash == hash) | (LedgerEvent.tx_hash == hash)
    ).first()
    if not ev:
        return {"found": False, "hash": hash}
    return {"found": True, **_serialize(ev)}


@router.get("/chain-integrity")
def chain_integrity(db: Session = Depends(get_db)):
    return ledger_svc.verify_chain(db)


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    rows = db.query(LedgerEvent).all()
    by_type: dict[str, int] = {}
    for r in rows:
        by_type[r.event_type] = by_type.get(r.event_type, 0) + 1
    return {"total_events": len(rows), "by_type": by_type,
            "simulated": settings.chain_simulated}
