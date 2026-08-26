"""Sovereign state router — read-only constitutional endpoints.

GET /sovereign/state                  consolidated dashboard snapshot
GET /sovereign/verdicts?limit=N       recent sanitized verdicts (newest first)
GET /sovereign/verdicts/{receipt_id}  one verdict + its commit certificate
GET /sovereign/epoch                  boot epoch + manifest binding

No POST/PUT/PATCH/DELETE exists in this router by construction. Mutation
crosses only via the CEN boundary (gate_commit), never over HTTP here.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.cen_governance_bridge import cen_governance_bridge
from src.sovereign_state import SovereignStateReader

router = APIRouter(prefix="/sovereign", tags=["sovereign"])


def _combined_receipts():
    """Gate-judgment history first (the demo's living chain); bridge receipts
    from governed commits flow through when present."""
    try:
        from app.sovereign_gate_router import gate_history_receipts
        history = gate_history_receipts()
        if history:
            return history
    except Exception:
        pass
    return cen_governance_bridge.receipts


def _combined_certificates():
    combined = dict(cen_governance_bridge.certificates)
    try:
        from app.sovereign_gate_router import gate_history_certificates
        combined.update(gate_history_certificates())
    except Exception:
        pass
    return combined


# Process-local singletons; the reader retains no gate access.
_reader = SovereignStateReader(
    receipts_provider=_combined_receipts,
    certificates_provider=_combined_certificates,
)


@router.get("/state")
def sovereign_state() -> dict:
    return _reader.summary()


@router.get("/epoch")
def sovereign_epoch() -> dict:
    return {**_reader.epoch(), **_reader.ledger_head()}


@router.get("/verdicts")
def sovereign_verdicts(limit: int = Query(default=25, ge=1, le=200)) -> dict:
    verdicts = _reader.recent_verdicts(limit=limit)
    return {"count": len(verdicts), "verdicts": verdicts}


@router.get("/verdicts/{receipt_id}")
def sovereign_verdict(receipt_id: str) -> dict:
    entry = _reader.verdict_by_receipt(receipt_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="receipt not found")
    return entry
