"""CRM adapter — local durable store under .runtime/crm/.

# Mythic: CRM subcontract
# Engineering: CrmAdapter
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _default_path() -> Path:
    configured = os.getenv("AAIS_RUNTIME_DIR")
    root = Path(configured).expanduser() if configured else Path(__file__).resolve().parents[3] / ".runtime"
    return root / "crm" / "store.json"


class CrmAdapter:
    provider = "crm"
    plug_id = "middleware.crm"

    def __init__(self, file_path: Path | None = None, *, connected: bool = True) -> None:
        self._path = file_path or _default_path()
        self._connected = connected
        self._lock = threading.Lock()

    def is_connected(self) -> bool:
        return self._connected

    def _load(self) -> dict[str, Any]:
        if not self._path.is_file():
            return {"leads": [], "deals": [], "connected": True}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"leads": [], "deals": [], "connected": True}

    def _save(self, db: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        db["updatedAt"] = _utc_now()
        self._path.write_text(json.dumps(db, indent=2) + "\n", encoding="utf-8")

    def create_follow_up(self, task: dict[str, Any], lead_id: str | None = None) -> dict[str, Any]:
        with self._lock:
            db = self._load()
            leads = list(db.get("leads") or [])
            deals = list(db.get("deals") or [])
            lead = next((l for l in leads if l.get("id") == lead_id), None) if lead_id else None
            if not lead:
                lead = {
                    "id": lead_id or str(uuid4()),
                    "name": str(task.get("title") or "Lead")[:120],
                    "status": "follow_up",
                    "createdAt": _utc_now(),
                }
                leads.append(lead)
            note_id = str(uuid4())
            deal = {
                "id": str(uuid4()),
                "leadId": lead["id"],
                "title": f"Follow-up: {task.get('title')}"[:200],
                "stage": "follow_up",
                "nextAction": task.get("title"),
                "probability": 0.5,
                "source": task.get("source") or "aais",
                "notes": [
                    {
                        "id": note_id,
                        "text": f"AAIS task {task.get('id')}: {task.get('title')}",
                        "createdAt": _utc_now(),
                    }
                ],
                "createdAt": _utc_now(),
            }
            deals.append(deal)
            db["leads"] = leads
            db["deals"] = deals
            self._save(db)
            return {
                "ok": True,
                "reason_code": "CRM_FOLLOWUP_CREATED",
                "dealId": deal["id"],
                "leadId": lead["id"],
                "noteId": note_id,
                "deal": deal,
            }

    def execute(self, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = dict(payload or {})
        with self._lock:
            db = self._load()
            if action == "crm.leads.create":
                lead = {
                    "id": str(uuid4()),
                    "name": str(payload.get("name") or payload.get("title") or "Lead")[:200],
                    "email": payload.get("email"),
                    "company": payload.get("company"),
                    "status": "new",
                    "createdAt": _utc_now(),
                }
                db.setdefault("leads", []).append(lead)
                self._save(db)
                return {"ok": True, "outcome": "ok", "reason_code": "CRM_LEAD_CREATED", "data": {"lead": lead}}
            if action == "crm.leads.update":
                lead_id = str(payload.get("id") or payload.get("leadId") or "")
                for i, lead in enumerate(db.get("leads") or []):
                    if lead.get("id") == lead_id:
                        lead.update({k: v for k, v in payload.items() if k not in {"id", "leadId"}})
                        lead["updatedAt"] = _utc_now()
                        db["leads"][i] = lead
                        self._save(db)
                        return {"ok": True, "outcome": "ok", "reason_code": "CRM_LEAD_UPDATED", "data": {"lead": lead}}
                return {"ok": False, "outcome": "error", "reason_code": "CRM_LEAD_NOT_FOUND"}
            if action == "crm.deals.stage":
                deal_id = str(payload.get("dealId") or payload.get("id") or "")
                for i, deal in enumerate(db.get("deals") or []):
                    if deal.get("id") == deal_id:
                        deal["stage"] = str(payload.get("stage") or "open")[:80]
                        deal["updatedAt"] = _utc_now()
                        db["deals"][i] = deal
                        self._save(db)
                        return {"ok": True, "outcome": "ok", "reason_code": "CRM_DEAL_STAGE", "data": {"deal": deal}}
                return {"ok": False, "outcome": "error", "reason_code": "CRM_DEAL_NOT_FOUND"}
            if action == "crm.deals.note":
                deal_id = str(payload.get("dealId") or payload.get("id") or "")
                for i, deal in enumerate(db.get("deals") or []):
                    if deal.get("id") == deal_id:
                        note = {
                            "id": str(uuid4()),
                            "text": str(payload.get("text") or payload.get("note") or "")[:4000],
                            "createdAt": _utc_now(),
                        }
                        deal.setdefault("notes", []).append(note)
                        deal["updatedAt"] = _utc_now()
                        db["deals"][i] = deal
                        self._save(db)
                        return {
                            "ok": True,
                            "outcome": "ok",
                            "reason_code": "CRM_DEAL_NOTE",
                            "data": {"deal": deal, "note": note},
                        }
                return {"ok": False, "outcome": "error", "reason_code": "CRM_DEAL_NOT_FOUND"}
            return {"ok": False, "outcome": "error", "reason_code": "CRM_UNKNOWN_ACTION"}
