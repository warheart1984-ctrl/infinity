"""Middleware plug contract — governed external subcontract adapters.

# Mythic: Middleware Plugs
# Engineering: MiddlewarePlug
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class MiddlewarePlugAction:
    action_id: str
    label: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MiddlewarePlugDescriptor:
    plug_id: str
    display_name: str
    provider: str
    plug_class: str = "middleware"
    authority_level: str = "assist"
    actions: list[MiddlewarePlugAction] = field(default_factory=list)
    auth_status: str = "needs_auth"  # ready | needs_auth | demo
    activation_hint: str | None = None
    enabled_default: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "plug_adapter_version": "plug_adapter.v1",
            "plug_id": self.plug_id,
            "display_name": self.display_name,
            "plug_class": self.plug_class,
            "authority_level": self.authority_level,
            "provider": self.provider,
            "actions": [a.to_dict() for a in self.actions],
            "auth_status": self.auth_status,
            "activation_hint": self.activation_hint,
            "enabled": False,
            "cisiv_stage": "implementation",
            "provenance": {"adapter_module": "src.operator_middleware_plugs"},
        }


def env_any(*names: str) -> str:
    for name in names:
        val = str(os.getenv(name) or "").strip()
        if val:
            return val
    return ""


class MiddlewarePlug(ABC):
    """Governed subcontract — fail closed; never pretend live success without auth."""

    plug_id: str = "middleware.base"

    @abstractmethod
    def describe(self) -> MiddlewarePlugDescriptor: ...

    @abstractmethod
    def execute(self, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]: ...

    def _demo(self, action: str, summary: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "ok": True,
            "outcome": "demo",
            "plug_id": self.plug_id,
            "action": action,
            "auth_status": "demo",
            "summary": summary,
            "data": data or {},
            "reason_code": "MIDDLEWARE_DEMO",
        }

    def _needs_auth(self, action: str, hint: str) -> dict[str, Any]:
        return {
            "ok": False,
            "outcome": "needs_auth",
            "plug_id": self.plug_id,
            "action": action,
            "auth_status": "needs_auth",
            "activation_hint": hint,
            "reason_code": "MIDDLEWARE_NEEDS_AUTH",
        }

    def _deferred_live(self, action: str, message: str) -> dict[str, Any]:
        return {
            "ok": False,
            "outcome": "deferred",
            "plug_id": self.plug_id,
            "action": action,
            "auth_status": "ready",
            "summary": message,
            "reason_code": "MIDDLEWARE_LIVE_DEFERRED",
            "message": message,
        }
