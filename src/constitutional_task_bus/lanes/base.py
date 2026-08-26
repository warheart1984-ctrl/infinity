"""Lane adapter base contract for the Constitutional Task Bus.

# Mythic: Provider Adapter Layer
# Engineering: TaskBusLaneAdapter
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class TaskBusLaneAdapter(ABC):
    """Governed subcontract — external providers do not act outside AAIS law."""

    lane_id: str = "base"
    provider_label: str = "aais"
    actions: tuple[str, ...] = ()

    @abstractmethod
    def describe(self) -> dict[str, Any]:
        """Catalog row for status/UI."""

    @abstractmethod
    def execute(
        self,
        *,
        action: str,
        payload: dict[str, Any],
        mode: str,
        trace_id: str,
    ) -> dict[str, Any]:
        """Run one lane action. mode is demo|live. Fail closed — never silent-reroute."""

    def _demo_result(
        self,
        *,
        action: str,
        payload: dict[str, Any],
        trace_id: str,
        summary: str,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "ok": True,
            "lane_id": self.lane_id,
            "action": action,
            "mode": "demo",
            "summary": summary,
            "trace_id": trace_id,
            "input_excerpt": str(payload.get("text") or payload.get("prompt") or "")[:240],
            **(extra or {}),
        }

    def _needs_auth_result(
        self,
        *,
        action: str,
        activation_hint: str,
        trace_id: str,
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "lane_id": self.lane_id,
            "action": action,
            "mode": "live",
            "status": "needs_auth",
            "reason_code": "TASK_BUS_NEEDS_AUTH",
            "activation_hint": activation_hint,
            "trace_id": trace_id,
        }
