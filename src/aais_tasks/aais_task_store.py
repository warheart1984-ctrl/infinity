"""Durable AAIS task store under .runtime/aais_tasks/tasks.json.

# Mythic: AAIS task ledger
# Engineering: AaisTaskStore
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from src.aais_tasks.aais_task_model import AaisTask, TaskStatus, new_task, _utc_now


def _default_path(runtime_root: Path | None = None) -> Path:
    if runtime_root is not None:
        return Path(runtime_root) / "aais_tasks" / "tasks.json"
    configured = os.getenv("AAIS_RUNTIME_DIR")
    if configured:
        return Path(configured).expanduser() / "aais_tasks" / "tasks.json"
    return Path(__file__).resolve().parents[2] / ".runtime" / "aais_tasks" / "tasks.json"


class AaisTaskStore:
    def __init__(self, file_path: Path | None = None, *, runtime_root: Path | None = None) -> None:
        self._path = file_path or _default_path(runtime_root)
        self._lock = threading.Lock()

    def _load(self) -> list[AaisTask]:
        if not self._path.is_file():
            return []
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            rows = raw.get("tasks") if isinstance(raw, dict) else []
            if not isinstance(rows, list):
                return []
            return [AaisTask.from_dict(r) for r in rows if isinstance(r, dict)]
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, tasks: list[AaisTask]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updatedAt": _utc_now(),
            "tasks": [t.to_dict() for t in tasks],
        }
        self._path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def create(self, **kwargs: Any) -> AaisTask:
        with self._lock:
            tasks = self._load()
            task = new_task(
                str(kwargs.get("title") or "Untitled"),
                description=kwargs.get("description"),
                due_date=kwargs.get("due_date") or kwargs.get("dueDate"),
                status=kwargs.get("status") or "notStarted",
                priority=kwargs.get("priority") or "normal",
                tags=list(kwargs.get("tags") or []),
                source=kwargs.get("source") or "aais",
                graph_id=kwargs.get("graph_id") or kwargs.get("graphId"),
            )
            tasks.append(task)
            self._save(tasks)
            return task

    def list(self) -> list[AaisTask]:
        with self._lock:
            return self._load()

    def get(self, task_id: str) -> AaisTask | None:
        with self._lock:
            for t in self._load():
                if t.id == task_id:
                    return t
            return None

    def update(self, task_id: str, **patch: Any) -> AaisTask | None:
        with self._lock:
            tasks = self._load()
            for i, t in enumerate(tasks):
                if t.id != task_id:
                    continue
                data = t.to_dict()
                if "title" in patch and patch["title"] is not None:
                    data["title"] = str(patch["title"])
                if "description" in patch:
                    data["description"] = patch["description"]
                if "dueDate" in patch or "due_date" in patch:
                    data["dueDate"] = patch.get("dueDate", patch.get("due_date"))
                if "status" in patch and patch["status"]:
                    data["status"] = patch["status"]
                if "priority" in patch and patch["priority"]:
                    data["priority"] = patch["priority"]
                if "tags" in patch and patch["tags"] is not None:
                    data["tags"] = list(patch["tags"])
                if "source" in patch and patch["source"]:
                    data["source"] = patch["source"]
                if "graphId" in patch or "graph_id" in patch:
                    data["graphId"] = patch.get("graphId", patch.get("graph_id"))
                data["updatedAt"] = _utc_now()
                updated = AaisTask.from_dict(data)
                tasks[i] = updated
                self._save(tasks)
                return updated
            return None

    def update_status(self, task_id: str, status: TaskStatus) -> AaisTask | None:
        return self.update(task_id, status=status)
