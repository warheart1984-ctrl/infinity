"""CRM follow-up from AAIS task.

# Mythic: CRM follow-up from AAIS task
# Engineering: create_follow_up_from_task
"""

from __future__ import annotations

from typing import Any

from src.aais_tasks.aais_task_model import AaisTask
from src.operator_middleware_plugs.adapters.crm_adapter import CrmAdapter


def create_follow_up_from_task(
    crm: CrmAdapter,
    task: AaisTask,
    lead_id: str | None = None,
) -> dict[str, Any]:
    tags = [t.lower() for t in (task.tags or [])]
    wants = bool(lead_id) or "crm" in tags
    if not wants:
        return {
            "ok": True,
            "skipped": True,
            "skip_reason": "no crm leadId/tag",
            "reason_code": "CRM_FOLLOWUP_SKIPPED",
        }
    return crm.create_follow_up(task.to_dict(), lead_id)
