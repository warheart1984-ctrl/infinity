"""AAIS host ingress — delegates to canonical aais-middleware TypeScript package.

# Mythic: Constitutional Task Bus
# Engineering: dispatch_task_bus_request → Node runRequest
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _middleware_root() -> Path:
    return _repo_root() / "aais-middleware"


def _dispatch_cli() -> Path:
    return _middleware_root() / "bin" / "dispatch.mjs"


def _ensure_built() -> Path:
    """Prefer compiled orchestrator; build if missing."""
    dist_entry = (
        _middleware_root() / "dist" / "src" / "orchestrator" / "task_orchestrator.js"
    )
    if dist_entry.is_file():
        return dist_entry
    # Best-effort build
    try:
        subprocess.run(
            ["npm", "run", "build"],
            cwd=str(_middleware_root()),
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except Exception:
        pass
    return dist_entry


def dispatch_task_bus_request(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Single ingress: spawn Node CLI for aais-middleware runRequest()."""
    body = dict(payload or {})
    cli = _dispatch_cli()
    _ensure_built()
    if not cli.is_file():
        return {
            "ok": False,
            "error": "aais-middleware CLI missing",
            "reason_codes": ["TASK_BUS_MIDDLEWARE_MISSING"],
        }

    env = os.environ.copy()
    try:
        proc = subprocess.run(
            ["node", str(cli), json.dumps(body)],
            cwd=str(_middleware_root()),
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": "middleware dispatch timed out",
            "reason_codes": ["TASK_BUS_TIMEOUT"],
        }
    except FileNotFoundError:
        return {
            "ok": False,
            "error": "node runtime not found",
            "reason_codes": ["TASK_BUS_NODE_MISSING"],
        }

    raw = (proc.stdout or "").strip()
    if not raw:
        return {
            "ok": False,
            "error": proc.stderr or "empty middleware response",
            "reason_codes": ["TASK_BUS_MIDDLEWARE_EMPTY"],
            "exit_code": proc.returncode,
        }
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "error": "middleware returned non-JSON",
            "stderr": proc.stderr,
            "stdout_excerpt": raw[:500],
            "reason_codes": ["TASK_BUS_MIDDLEWARE_PARSE"],
        }

    # Normalize snake_case echoes for AAIS consumers
    if isinstance(result, dict):
        result.setdefault("request_id", result.get("requestId"))
        result.setdefault("trace_id", result.get("traceId"))
        if "evidence_refs" not in result and isinstance(result.get("trace"), dict):
            evidence = result["trace"].get("evidence") or []
            result["evidence_refs"] = [
                e.get("id") for e in evidence if isinstance(e, dict) and e.get("id")
            ]
        if "decision_events" not in result and isinstance(result.get("trace"), dict):
            result["decision_events"] = list(
                result["trace"].get("decisionEvents") or []
            )
        result.setdefault("lane_plan", result.get("lanePlan"))
        result.setdefault("reason_codes", result.get("reasonCodes") or [])
        result.setdefault("deep_links", result.get("deepLinks") or {})
        cache_trace(result)
    return result


def task_bus_status() -> dict[str, Any]:
    cli = _dispatch_cli()
    _ensure_built()
    if not cli.is_file():
        return {"ok": False, "error": "aais-middleware missing"}
    try:
        proc = subprocess.run(
            ["node", str(cli), "--status"],
            cwd=str(_middleware_root()),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        data = json.loads((proc.stdout or "{}").strip() or "{}")
        data["ok"] = True
        return data
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# In-memory trace cache from last dispatches (optional GET)
_TRACE_CACHE: dict[str, dict[str, Any]] = {}


def cache_trace(result: dict[str, Any]) -> None:
    tid = str(result.get("trace_id") or result.get("traceId") or "")
    if tid:
        _TRACE_CACHE[tid] = result
        # also index by request id
        rid = str(result.get("request_id") or result.get("requestId") or "")
        if rid:
            _TRACE_CACHE[rid] = result


def get_cached_trace(trace_id: str) -> dict[str, Any] | None:
    return _TRACE_CACHE.get(trace_id)


def recent_traces(*, limit: int = 20) -> list[dict[str, Any]]:
    """UI-safe recent dispatch summaries (no secrets)."""
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key, result in reversed(list(_TRACE_CACHE.items())):
        tid = str(result.get("trace_id") or result.get("traceId") or key)
        if tid in seen:
            continue
        seen.add(tid)
        trace = result.get("trace") if isinstance(result.get("trace"), dict) else {}
        events = list(trace.get("events") or [])
        rows.append(
            {
                "trace_id": tid,
                "request_id": result.get("request_id") or result.get("requestId"),
                "ok": result.get("ok"),
                "intent": result.get("intent"),
                "event_count": len(events),
                "providers": sorted(
                    {str(e.get("provider")) for e in events if isinstance(e, dict) and e.get("provider")}
                ),
                "adaptive": result.get("adaptive"),
            }
        )
        if len(rows) >= limit:
            break
    return rows
