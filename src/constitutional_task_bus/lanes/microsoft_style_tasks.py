"""Microsoft-style planning / todo / calendar subcontract lane.

# Mythic: Microsoft-like lane
# Engineering: MicrosoftStyleTasksLane
"""

from __future__ import annotations

import os
from typing import Any

from src.constitutional_task_bus.lanes.base import TaskBusLaneAdapter


class MicrosoftStyleTasksLane(TaskBusLaneAdapter):
    lane_id = "microsoft_style_tasks"
    provider_label = "microsoft_graph_subcontract"
    actions = ("plan", "list_tasks", "create_task", "email_draft")

    def describe(self) -> dict[str, Any]:
        token = (
            os.getenv("AAIS_MS_GRAPH_TOKEN")
            or os.getenv("MICROSOFT_GRAPH_TOKEN")
            or os.getenv("MS_GRAPH_ACCESS_TOKEN")
            or ""
        ).strip()
        return {
            "lane_id": self.lane_id,
            "label": "Microsoft-style Tasks Lane",
            "engineering": "MicrosoftStyleTasksLane",
            "provider_label": self.provider_label,
            "actions": list(self.actions),
            "auth_status": "ready" if token else "needs_auth",
            "activation_hint": (
                None
                if token
                else "Set AAIS_MS_GRAPH_TOKEN (or MICROSOFT_GRAPH_TOKEN) for live Graph To Do / mail."
            ),
            "scope": "planning / todo / calendar / docs (MVP: plan + task stubs)",
            "not_claimed": "Full Microsoft 365 / Graph parity is deferred.",
        }

    def execute(
        self,
        *,
        action: str,
        payload: dict[str, Any],
        mode: str,
        trace_id: str,
    ) -> dict[str, Any]:
        action = (action or "plan").strip() or "plan"
        if action not in self.actions:
            return {
                "ok": False,
                "lane_id": self.lane_id,
                "reason_code": "TASK_BUS_UNKNOWN_ACTION",
                "message": f"Unknown action {action}",
                "trace_id": trace_id,
            }

        text = str(payload.get("text") or payload.get("prompt") or "").strip()
        if mode != "live":
            tasks = [
                {"id": "demo-1", "title": f"Clarify: {text[:80] or 'operator ask'}", "status": "open"},
                {"id": "demo-2", "title": "Capture next governed step", "status": "open"},
            ]
            return self._demo_result(
                action=action,
                payload=payload,
                trace_id=trace_id,
                summary=f"Demo {action}: produced {len(tasks)} planned tasks (no Graph call).",
                extra={
                    "tasks": tasks,
                    "email_draft": (
                        {
                            "to": payload.get("to") or "operator@local",
                            "subject": f"[AAIS Task Bus] {text[:60] or 'plan'}",
                            "body": f"Governed draft under trace {trace_id}.\n\n{text}",
                        }
                        if action == "email_draft"
                        else None
                    ),
                },
            )

        token = (
            os.getenv("AAIS_MS_GRAPH_TOKEN")
            or os.getenv("MICROSOFT_GRAPH_TOKEN")
            or os.getenv("MS_GRAPH_ACCESS_TOKEN")
            or ""
        ).strip()
        if not token:
            return self._needs_auth_result(
                action=action,
                activation_hint="Set AAIS_MS_GRAPH_TOKEN for live Microsoft Graph tasks.",
                trace_id=trace_id,
            )

        # Live Graph wire is deferred — record explicit decision, do not fake success
        return {
            "ok": False,
            "lane_id": self.lane_id,
            "action": action,
            "mode": "live",
            "status": "deferred",
            "reason_code": "TASK_BUS_LIVE_GRAPH_DEFERRED",
            "message": (
                "Token present but live Graph To Do/mail execute is deferred. "
                "No silent substitute provider."
            ),
            "trace_id": trace_id,
            "activation_hint": "Use demo mode or await Graph client MVP.",
        }
