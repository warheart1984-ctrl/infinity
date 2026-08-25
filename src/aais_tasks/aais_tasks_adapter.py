"""AAIS Tasks adapter — primary task lane (no Graph token required).

# Mythic: AAIS Tasks lane
# Engineering: AaisTasksAdapter
"""

from __future__ import annotations

from typing import Any

from src.aais_tasks.aais_task_store import AaisTaskStore


class AaisTasksAdapter:
    provider = "aais_tasks"
    lane = "aais_tasks"

    def __init__(self, store: AaisTaskStore | None = None) -> None:
        self.store = store or AaisTaskStore()

    def create_task(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = dict(payload or {})
        task = self.store.create(
            title=str(payload.get("title") or "Untitled"),
            description=payload.get("description"),
            due_date=payload.get("dueDate") or payload.get("due_date"),
            status=payload.get("status") or "notStarted",
            priority=payload.get("priority") or "normal",
            tags=list(payload.get("tags") or []),
            source=payload.get("source") or "aais",
            graph_id=payload.get("graphId") or payload.get("graph_id"),
        )
        return {
            "ok": True,
            "provider": self.provider,
            "reason_code": "AAIS_TASK_CREATED",
            "task": task.to_dict(),
        }

    def list_tasks(self) -> dict[str, Any]:
        tasks = [t.to_dict() for t in self.store.list()]
        return {
            "ok": True,
            "provider": self.provider,
            "reason_code": "AAIS_TASK_LIST",
            "tasks": tasks,
        }

    def update_task(self, task_id: str, patch: dict[str, Any] | None = None) -> dict[str, Any]:
        updated = self.store.update(task_id, **dict(patch or {}))
        if not updated:
            return {
                "ok": False,
                "provider": self.provider,
                "reason_code": "AAIS_TASK_NOT_FOUND",
                "error": f"Task not found: {task_id}",
            }
        return {
            "ok": True,
            "provider": self.provider,
            "reason_code": "AAIS_TASK_UPDATED",
            "task": updated.to_dict(),
        }

    def update_status(self, task_id: str, status: str) -> dict[str, Any]:
        return self.update_task(task_id, {"status": status})
