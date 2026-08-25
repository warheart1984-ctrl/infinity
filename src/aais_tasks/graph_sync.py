"""Graph ↔ AAIS task sync (fail closed; no silent fake).

# Mythic: Graph ↔ AAIS task bridge
# Engineering: sync_from_graph / sync_to_graph
"""

from __future__ import annotations

from typing import Any

from src.aais_tasks.aais_task_store import AaisTaskStore
from src.operator_middleware_plugs.clients.graph_client import (
    call_graph,
    graph_create_todo_task,
    graph_list_todo_tasks,
)


def sync_from_graph(
    store: AaisTaskStore,
    token: str | None,
    *,
    list_id: str = "tasks",
) -> dict[str, Any]:
    if not token:
        return {
            "ok": False,
            "needs_auth": True,
            "reason_code": "GRAPH_SYNC_NEEDS_AUTH",
            "error": "Set AAIS_MS_GRAPH_TOKEN for syncFromGraph.",
        }
    listed = graph_list_todo_tasks(token, list_id=list_id)
    if not listed.get("ok"):
        return {
            "ok": False,
            "reason_code": listed.get("reason_code"),
            "error": listed.get("error"),
        }
    value = (listed.get("data") or {}).get("value") if isinstance(listed.get("data"), dict) else []
    imported = []
    for item in value or []:
        if not isinstance(item, dict):
            continue
        graph_id = str(item.get("id") or "")
        if not graph_id:
            continue
        existing = next((t for t in store.list() if t.graph_id == graph_id), None)
        status = "completed" if str(item.get("status") or "").lower() == "completed" else "notStarted"
        if existing:
            updated = store.update(
                existing.id,
                title=str(item.get("title") or existing.title),
                status=status,
                source="graph",
            )
            if updated:
                imported.append(updated.to_dict())
            continue
        task = store.create(
            title=str(item.get("title") or "Graph task"),
            status=status,
            source="graph",
            graph_id=graph_id,
        )
        imported.append(task.to_dict())
    return {"ok": True, "reason_code": "GRAPH_SYNC_FROM_OK", "imported": imported}


def sync_to_graph(
    store: AaisTaskStore,
    token: str | None,
    task_id: str,
    *,
    list_id: str = "tasks",
) -> dict[str, Any]:
    if not token:
        return {
            "ok": False,
            "needs_auth": True,
            "reason_code": "GRAPH_SYNC_NEEDS_AUTH",
            "error": "Set AAIS_MS_GRAPH_TOKEN for syncToGraph.",
        }
    task = store.get(task_id)
    if not task:
        return {"ok": False, "reason_code": "AAIS_TASK_NOT_FOUND", "error": f"No task {task_id}"}
    if task.graph_id:
        patch = call_graph(
            token,
            f"me/todo/lists/{list_id}/tasks/{task.graph_id}",
            method="PATCH",
            body={
                "title": task.title,
                "status": "completed" if task.status == "completed" else "notStarted",
            },
        )
        if not patch.get("ok"):
            return {"ok": False, "reason_code": patch.get("reason_code"), "error": patch.get("error")}
        return {"ok": True, "reason_code": "GRAPH_SYNC_TO_OK", "exported": [task.to_dict()]}
    created = graph_create_todo_task(token, task.title, list_id=list_id)
    if not created.get("ok"):
        return {"ok": False, "reason_code": created.get("reason_code"), "error": created.get("error")}
    data = created.get("data") if isinstance(created.get("data"), dict) else {}
    graph_id = str((data or {}).get("id") or "")
    updated = store.update(task.id, graph_id=graph_id or None, source="aais")
    return {
        "ok": True,
        "reason_code": "GRAPH_SYNC_TO_OK",
        "exported": [(updated or task).to_dict()],
    }
