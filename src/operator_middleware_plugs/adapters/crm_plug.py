"""CRM middleware plug registry entry.

# Mythic: CRM
# Engineering: CrmMiddlewarePlug
"""

from __future__ import annotations

from typing import Any

from src.operator_middleware_plugs.adapters.crm_adapter import CrmAdapter
from src.operator_middleware_plugs.contract import (
    MiddlewarePlug,
    MiddlewarePlugAction,
    MiddlewarePlugDescriptor,
)


class CrmMiddlewarePlug(MiddlewarePlug):
    plug_id = "middleware.crm"
    aliases = ("native.crm.attach",)

    def __init__(self, adapter: CrmAdapter | None = None) -> None:
        self._adapter = adapter or CrmAdapter()

    def describe(self) -> MiddlewarePlugDescriptor:
        return MiddlewarePlugDescriptor(
            plug_id=self.plug_id,
            display_name="CRM Leads / Deals",
            provider="crm",
            authority_level="execute",
            actions=[
                MiddlewarePlugAction("crm.leads.create", "Create lead"),
                MiddlewarePlugAction("crm.leads.update", "Update lead"),
                MiddlewarePlugAction("crm.deals.stage", "Set deal stage"),
                MiddlewarePlugAction("crm.deals.note", "Add deal note"),
            ],
            auth_status="ready" if self._adapter.is_connected() else "needs_auth",
            activation_hint="Local durable CRM under .runtime/crm/",
        )

    def execute(self, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = dict(payload or {})
        action = (action or "crm.leads.create").strip()
        if payload.get("force_demo") and action == "crm.leads.create":
            return self._demo(
                action,
                "Demo CRM lead",
                {"lead": {"id": "demo", "name": payload.get("name") or "Demo"}},
            )
        result = self._adapter.execute(action, payload)
        result.setdefault("plug_id", self.plug_id)
        result.setdefault("action", action)
        result.setdefault("auth_status", "ready")
        return result
