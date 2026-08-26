"""AAIS Task model.

# Mythic: AAIS To Do
# Engineering: AaisTask
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

TaskStatus = Literal["notStarted", "inProgress", "completed"]
TaskPriority = Literal["low", "normal", "high"]
TaskSource = Literal["aais", "graph", "crm", "gmail"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class AaisTask:
    id: str
    title: str
    created_at: str
    status: TaskStatus = "notStarted"
    description: str | None = None
    due_date: str | None = None
    priority: TaskPriority = "normal"
    tags: list[str] = field(default_factory=list)
    source: TaskSource = "aais"
    graph_id: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "createdAt": self.created_at,
            "dueDate": self.due_date,
            "status": self.status,
            "priority": self.priority,
            "tags": list(self.tags),
            "source": self.source,
            "graphId": self.graph_id,
            "updatedAt": self.updated_at,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> AaisTask:
        status = str(raw.get("status") or "notStarted")
        if status not in {"notStarted", "inProgress", "completed"}:
            status = "notStarted"
        priority = str(raw.get("priority") or "normal")
        if priority not in {"low", "normal", "high"}:
            priority = "normal"
        source = str(raw.get("source") or "aais")
        if source not in {"aais", "graph", "crm", "gmail"}:
            source = "aais"
        return cls(
            id=str(raw.get("id") or uuid4()),
            title=str(raw.get("title") or "Untitled")[:500],
            description=(str(raw["description"])[:8000] if raw.get("description") else None),
            created_at=str(raw.get("createdAt") or raw.get("created_at") or _utc_now()),
            due_date=(str(raw["dueDate"]) if raw.get("dueDate") else (str(raw["due_date"]) if raw.get("due_date") else None)),
            status=status,  # type: ignore[arg-type]
            priority=priority,  # type: ignore[arg-type]
            tags=[str(t) for t in (raw.get("tags") or [])][:32],
            source=source,  # type: ignore[arg-type]
            graph_id=(str(raw["graphId"]) if raw.get("graphId") else (str(raw["graph_id"]) if raw.get("graph_id") else None)),
            updated_at=(str(raw["updatedAt"]) if raw.get("updatedAt") else None),
        )


def new_task(
    title: str,
    *,
    description: str | None = None,
    due_date: str | None = None,
    status: TaskStatus = "notStarted",
    priority: TaskPriority = "normal",
    tags: list[str] | None = None,
    source: TaskSource = "aais",
    graph_id: str | None = None,
) -> AaisTask:
    now = _utc_now()
    return AaisTask(
        id=str(uuid4()),
        title=title[:500],
        description=description,
        created_at=now,
        due_date=due_date,
        status=status,
        priority=priority,
        tags=list(tags or []),
        source=source,
        graph_id=graph_id,
        updated_at=now,
    )
