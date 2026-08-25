"""Multi-provider task creation (Python twin of orchestrateTaskCreation).

# Mythic: Multi-provider task forge
# Engineering: orchestrate_task_creation
"""

from __future__ import annotations

from typing import Any

from src.aais_tasks.aais_tasks_adapter import AaisTasksAdapter
from src.operator_middleware_plugs.adapters.crm_adapter import CrmAdapter
from src.operator_middleware_plugs.clients.graph_client import graph_create_todo_task
from src.operator_middleware_plugs.oauth_token_store import resolve_graph_token


def _log(trace: dict[str, Any], provider: str, input_payload: Any, output: Any, justification: str) -> None:
    events = trace.setdefault("events", [])
    evidence = trace.setdefault("evidence", [])
    events.append(
        {
            "provider": provider,
            "lane": "task",
            "input": input_payload,
            "output": output,
            "justification": justification,
        }
    )
    evidence.append({"provider": provider, "justification": justification})


def default_adaptive_analyze(request: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
    intent = request.get("intent") or {}
    tags = list(intent.get("tags") or [])
    risk = ((request.get("policy") or {}).get("riskLevel") or (request.get("policy") or {}).get("risk_level") or "normal")
    decision: dict[str, Any] = {
        "mode": "normal",
        "allowedProviders": ["aais.tasks", "crm", "graph_tasks"],
        "proposedAdaptations": [],
    }
    if "high_risk" in tags or risk == "high":
        decision["mode"] = "conservative"
        decision["allowedProviders"] = ["aais.tasks"]
        decision["proposedAdaptations"] = ["Force AAIS-only on high-risk"]
        decision["forceSimulate"] = True
    elif "sales" in tags or "crm" in tags:
        decision["allowedProviders"] = ["aais.tasks", "crm"]
        decision["proposedAdaptations"] = ["Prefer CRM + AAIS"]
    elif "scheduling" in tags or "calendar" in tags:
        decision["allowedProviders"] = ["aais.tasks", "graph_tasks"]
        decision["proposedAdaptations"] = ["Prefer Graph + AAIS"]
    _log(trace, "adaptive_engine", {"tags": tags}, decision, f"Adaptive mode={decision['mode']}")
    return decision


def orchestrate_task_creation(
    request: dict[str, Any],
    policy: dict[str, Any],
    decision: dict[str, Any],
    trace: dict[str, Any],
    *,
    aais: AaisTasksAdapter | None = None,
    crm: CrmAdapter | None = None,
) -> dict[str, Any]:
    aais = aais or AaisTasksAdapter()
    crm = crm or CrmAdapter()
    tasks = list(request.get("tasks") or [])
    payload = tasks[0] if tasks else {"target": (request.get("intent") or {}).get("raw") or "Task", "action": "create", "constraints": {}}
    constraints = dict(payload.get("constraints") or {})
    result: dict[str, Any] = {}

    aais_out = aais.create_task(
        {
            "title": str(payload.get("target") or "Task")[:500],
            "description": str(payload.get("action") or ""),
            "dueDate": constraints.get("dueDate") or constraints.get("due_date"),
            "tags": list((request.get("intent") or {}).get("tags") or []) + list(constraints.get("tags") or []),
            "source": "aais",
        }
    )
    aais_task = aais_out.get("task") or {}
    result["aais"] = aais_task
    _log(trace, "aais.tasks", payload, aais_task, "AAIS primary task")

    approved = list(policy.get("approvedProviders") or policy.get("approved_providers") or [])
    allowed = list(decision.get("allowedProviders") or [])
    crm_allowed = ("crm" in approved) and (("crm" in allowed) if allowed else True)
    crm_lead = constraints.get("crmLeadId") or constraints.get("crm_lead_id")
    tags = [str(t).lower() for t in ((request.get("intent") or {}).get("tags") or [])]
    if crm_allowed and crm.is_connected() and (crm_lead or "crm" in tags):
        crm_out = crm.create_follow_up(aais_task, str(crm_lead) if crm_lead else None)
        result["crm"] = crm_out
        _log(trace, "crm", payload, crm_out, "CRM follow-up from AAIS task")
    else:
        reason = "adaptive/policy blocked crm" if not crm_allowed else ("no crmLeadId/tag" if not (crm_lead or "crm" in tags) else "CRM not connected")
        _log(trace, "crm", payload, {"skipped": True, "reason": reason}, f"skipped: {reason}")

    graph_allowed = (
        ("graph_tasks" in approved or "ms_tasks" in approved)
        and (("graph_tasks" in allowed) if allowed else True)
    )
    sync_graph = bool(constraints.get("syncGraph") or constraints.get("sync_graph"))
    raw = str(((request.get("intent") or {}).get("raw") or "")).lower()
    if not sync_graph and "sync" in raw and ("microsoft" in raw or "graph" in raw):
        sync_graph = True
    token = resolve_graph_token()
    if graph_allowed and sync_graph and token:
        graph_out = graph_create_todo_task(
            token,
            str(aais_task.get("title") or "Task"),
            due_date=aais_task.get("dueDate"),
        )
        result["graph"] = graph_out
        _log(trace, "graph_tasks", payload, graph_out, "Graph task from AAIS task")
    else:
        reason = (
            "adaptive/policy blocked graph_tasks"
            if not graph_allowed
            else ("syncGraph not set" if not sync_graph else "Graph token missing")
        )
        _log(trace, "graph_tasks", payload, {"skipped": True, "reason": reason}, f"skipped: {reason}")

    return result
