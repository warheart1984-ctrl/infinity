"""AAIS Tasks middleware plug — native To Do (no Graph required).

# Mythic: AAIS Tasks
# Engineering: AaisTasksMiddlewarePlug
"""

from __future__ import annotations

from typing import Any

from src.aais_tasks.aais_tasks_adapter import AaisTasksAdapter
from src.aais_tasks.graph_sync import sync_from_graph, sync_to_graph
from src.operator_middleware_plugs.contract import (
    MiddlewarePlug,
    MiddlewarePlugAction,
    MiddlewarePlugDescriptor,
)
from src.operator_middleware_plugs.oauth_token_store import resolve_graph_token


class AaisTasksMiddlewarePlug(MiddlewarePlug):
    plug_id = "middleware.aais.tasks"

    def __init__(self, adapter: AaisTasksAdapter | None = None) -> None:
        self._adapter = adapter or AaisTasksAdapter()

    def describe(self) -> MiddlewarePlugDescriptor:
        return MiddlewarePlugDescriptor(
            plug_id=self.plug_id,
            display_name="AAIS Tasks",
            provider="aais.tasks",
            authority_level="execute",
            actions=[
                MiddlewarePlugAction("create", "Create task"),
                MiddlewarePlugAction("list", "List tasks"),
                MiddlewarePlugAction("updateStatus", "Update status"),
                MiddlewarePlugAction("syncFromGraph", "Sync from Microsoft"),
                MiddlewarePlugAction("syncToGraph", "Sync to Microsoft"),
            ],
            auth_status="ready",
            activation_hint="Native AAIS Tasks — works without Microsoft token.",
        )

    def execute(self, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = dict(payload or {})
        action = (action or "list").strip() or "list"
        if action in {"create", "createTask"}:
            result = self._adapter.create_task(payload)
            return {
                "ok": result["ok"],
                "outcome": "ok",
                "plug_id": self.plug_id,
                "action": action,
                "auth_status": "ready",
                "summary": f"Created AAIS task {result.get('task', {}).get('title')}",
                "data": result,
                "reason_code": result.get("reason_code"),
            }
        if action in {"list", "listTasks"}:
            result = self._adapter.list_tasks()
            return {
                "ok": True,
                "outcome": "ok",
                "plug_id": self.plug_id,
                "action": action,
                "data": result,
                "reason_code": result.get("reason_code"),
            }
        if action in {"updateStatus", "update", "updateTask"}:
            task_id = str(payload.get("id") or payload.get("taskId") or "")
            result = self._adapter.update_status(task_id, str(payload.get("status") or "notStarted"))
            return {
                "ok": result["ok"],
                "outcome": "ok" if result["ok"] else "error",
                "plug_id": self.plug_id,
                "action": action,
                "data": result,
                "reason_code": result.get("reason_code"),
            }
        if action == "syncFromGraph":
            token = resolve_graph_token()
            result = sync_from_graph(self._adapter.store, token)
            return {
                "ok": result.get("ok", False),
                "outcome": "ok" if result.get("ok") else ("needs_auth" if result.get("needs_auth") else "error"),
                "plug_id": self.plug_id,
                "action": action,
                "data": result,
                "reason_code": result.get("reason_code"),
                "activation_hint": result.get("error") if result.get("needs_auth") else None,
            }
        if action == "syncToGraph":
            token = resolve_graph_token()
            task_id = str(payload.get("id") or payload.get("taskId") or "")
            result = sync_to_graph(self._adapter.store, token, task_id)
            return {
                "ok": result.get("ok", False),
                "outcome": "ok" if result.get("ok") else ("needs_auth" if result.get("needs_auth") else "error"),
                "plug_id": self.plug_id,
                "action": action,
                "data": result,
                "reason_code": result.get("reason_code"),
            }
        return {
            "ok": False,
            "outcome": "error",
            "plug_id": self.plug_id,
            "action": action,
            "reason_code": "AAIS_TASK_UNKNOWN_ACTION",
        }
