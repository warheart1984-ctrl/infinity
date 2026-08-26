"""Jarvis Continuity Ledger — MCP server.

Mythic: the ledger remembers so no agent has to pretend it does.
Engineering: a Model Context Protocol (stdio) server exposing the
Continuity Ledger's governed memory operations to ANY MCP client
(Claude Desktop, Cursor, custom agents). This server is a thin,
stateless client of the ledger's HTTP API — it holds NO records, NO
truth, and NO authority. It surfaces conflicts; it never resolves them.

Long-term interface contract:
- Tools map 1:1 to ledger REST endpoints (docs/ADAPTER_CONSUMERS.md).
- Every write carries source_agent + session_id + evidence: provenance is
  mandatory at the protocol layer, not optional convention.
- truth_scope is exposed explicitly: "live" excludes superseded/archived.
- Built on the official `mcp` low-level Server: no console probing, no
  framework magic, runs anywhere python3 runs.

Run:
    MEMORYBOARD_URL=http://127.0.0.1:8001 python -m services.memoryboard_mcp

Register (Claude/Cursor MCP config):
    {"command": "python", "args": ["-m", "services.memoryboard_mcp"]}
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
import mcp.server.stdio
import mcp.types as types
from mcp.server import Server

LEDGER_URL = os.environ.get("MEMORYBOARD_URL", "http://127.0.0.1:8001")
TIMEOUT = float(os.environ.get("MEMORYBOARD_TIMEOUT", "10"))

app = Server("jarvis-continuity-ledger")


class LedgerError(RuntimeError):
    pass


async def _request(method: str, path: str, *, params: dict | None = None, json_body: Any = None) -> Any:
    async with httpx.AsyncClient(base_url=LEDGER_URL, timeout=TIMEOUT) as client:
        response = await client.request(method, path, params=params, json=json_body)
    if response.status_code >= 400:
        raise LedgerError(f"ledger {method} {path} -> {response.status_code}: {response.text[:300]}")
    return response.json()


# ------------------------------------------------------------------ reads


async def ledger_health() -> dict[str, Any]:
    """Check the Continuity Ledger service and its schema version."""
    return await _request("GET", "/health")


async def retrieve_memories(
    query: str,
    limit: int = 10,
    truth_scope: str = "live",
    subject: str | None = None,
) -> dict[str, Any]:
    """Search governed memories. Returns memories + selections + conflicts.

    Surfaces disputes between records sharing a subject — it NEVER picks
    which one is true. Read 'conflicts' before trusting a single hit.
    truth_scope: "live" (default) excludes superseded/archived; "all"
    includes them for replay / why-was-this-recorded questions.
    """
    return await _request(
        "GET",
        "/api/jarvis/memory/retrieve",
        params={"query": query, "limit": limit, "truth_scope": truth_scope, **({"subject": subject} if subject else {})},
    )


async def list_conflicts(subject: str | None = None) -> dict[str, Any]:
    """List unresolved record disputes grouped by subject."""
    params = {"subject": subject} if subject else None
    return await _request("GET", "/api/jarvis/memory/conflicts", params=params)


async def get_memory(memory_id: str) -> dict[str, Any]:
    """Fetch one memory by id with full provenance (source_agent, session_id, evidence)."""
    data = await _request("GET", f"/api/jarvis/memory/{memory_id}")
    # Unwrap the ledger's replay envelope for direct agent consumption.
    result = dict(data.get("memory") or {})
    if data.get("selection"):
        result["selection"] = data["selection"]
    return result


async def list_memories(
    type_filter: str | None = None,
    session_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Browse memories by type (decision|fact|task|preference|architecture|research), session, or lifecycle status."""
    params: dict[str, Any] = {"limit": limit}
    if type_filter:
        params["type"] = type_filter
    if session_id:
        params["session_id"] = session_id
    if status:
        params["status"] = status
    return await _request("GET", "/api/jarvis/memory", params=params)


async def get_memory_board() -> dict[str, Any]:
    """Read the operator-facing memory board (active slots snapshot)."""
    return await _request("GET", "/api/jarvis/memory/board")


# ------------------------------------------------------------------ writes


async def store_memory(
    content: str,
    type: str,
    source_agent: str,
    session_id: str,
    confidence: float,
    evidence: list[dict[str, str]] | None = None,
    subject: str | None = None,
    supersedes: str | None = None,
    status: str = "draft",
) -> dict[str, Any]:
    """Record one governed memory. Provenance is mandatory.

    - type: decision | fact | task | preference | architecture | research
    - confidence: caller-asserted 0.0-1.0 (the ledger records claims, not truths)
    - evidence: [{kind, ref, note?}] — cite where this came from
    - supersedes: id of the record this REPLACES (recorded claim; never silent merge)
    - status: draft | verified | archived
    """
    body: dict[str, Any] = {
        "content": content,
        "type": type,
        "source_agent": source_agent,
        "session_id": session_id,
        "confidence": confidence,
        "evidence": evidence or [],
        "status": status,
    }
    if subject:
        body["subject"] = subject
    if supersedes:
        body["supersedes"] = supersedes
    data = await _request("POST", "/api/jarvis/memory", json_body=body)
    return data.get("memory") or data


async def update_memory(memory_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Update mutable fields (content, confidence, status, subject) on one memory."""
    data = await _request("PATCH", f"/api/jarvis/memory/{memory_id}", json_body=fields)
    return data.get("memory") or data


async def archive_memory(memory_id: str) -> dict[str, Any]:
    """Archive a record (lifecycle, not deletion — history stays replayable)."""
    data = await _request("PATCH", f"/api/jarvis/memory/{memory_id}", json_body={"status": "archived"})
    return data.get("memory") or data


# ------------------------------------------------------------ MCP wiring

TOOL_DEFS: list[types.Tool] = [
    types.Tool(name="ledger_health", description=ledger_health.__doc__ or "", inputSchema={"type": "object", "properties": {}}),
    types.Tool(
        name="retrieve_memories",
        description=retrieve_memories.__doc__ or "",
        inputSchema={
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
                "truth_scope": {"enum": ["live", "all"], "default": "live"},
                "subject": {"type": "string"},
            },
        },
    ),
    types.Tool(
        name="list_conflicts",
        description=list_conflicts.__doc__ or "",
        inputSchema={
            "type": "object",
            "properties": {"subject": {"type": "string"}},
        },
    ),
    types.Tool(
        name="get_memory",
        description=get_memory.__doc__ or "",
        inputSchema={"type": "object", "required": ["memory_id"], "properties": {"memory_id": {"type": "string"}}},
    ),
    types.Tool(
        name="list_memories",
        description=list_memories.__doc__ or "",
        inputSchema={
            "type": "object",
            "properties": {
                "type_filter": {"enum": ["decision", "fact", "task", "preference", "architecture", "research"]},
                "session_id": {"type": "string"},
                "status": {"enum": ["draft", "verified", "archived"]},
                "limit": {"type": "integer", "default": 50},
            },
        },
    ),
    types.Tool(name="get_memory_board", description=get_memory_board.__doc__ or "", inputSchema={"type": "object", "properties": {}}),
    types.Tool(
        name="store_memory",
        description=store_memory.__doc__ or "",
        inputSchema={
            "type": "object",
            "required": ["content", "type", "source_agent", "session_id", "confidence"],
            "properties": {
                "content": {"type": "string"},
                "type": {"enum": ["decision", "fact", "task", "preference", "architecture", "research"]},
                "source_agent": {"type": "string"},
                "session_id": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "evidence": {"type": "array", "items": {"type": "object"}},
                "subject": {"type": "string"},
                "supersedes": {"type": "string"},
                "status": {"enum": ["draft", "verified", "archived"], "default": "draft"},
            },
        },
    ),
    types.Tool(
        name="update_memory",
        description=update_memory.__doc__ or "",
        inputSchema={
            "type": "object",
            "required": ["memory_id", "fields"],
            "properties": {
                "memory_id": {"type": "string"},
                "fields": {"type": "object"},
            },
        },
    ),
    types.Tool(
        name="archive_memory",
        description=archive_memory.__doc__ or "",
        inputSchema={"type": "object", "required": ["memory_id"], "properties": {"memory_id": {"type": "string"}}},
    ),
]

_DISPATCH = {
    "ledger_health": lambda a: ledger_health(),
    "retrieve_memories": lambda a: retrieve_memories(**a),
    "list_conflicts": lambda a: list_conflicts(subject=a.get("subject")),
    "get_memory": lambda a: get_memory(a["memory_id"]),
    "list_memories": lambda a: list_memories(
        type_filter=a.get("type_filter"), session_id=a.get("session_id"),
        status=a.get("status"), limit=a.get("limit", 50),
    ),
    "get_memory_board": lambda a: get_memory_board(),
    "store_memory": lambda a: store_memory(**a),
    "update_memory": lambda a: update_memory(a["memory_id"], a["fields"]),
    "archive_memory": lambda a: archive_memory(a["memory_id"]),
}


@app.list_tools()
async def _list_tools() -> list[types.Tool]:
    return TOOL_DEFS


@app.call_tool()
async def _call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    handler = _DISPATCH.get(name)
    if handler is None:
        raise LedgerError(f"unknown tool: {name}")
    try:
        result = await handler(arguments)
    except LedgerError as exc:
        # Refusals are evidence: surface the ledger's reason, never mask it.
        return [types.TextContent(type="text", text=json.dumps({"error": str(exc)}))]
    return [types.TextContent(type="text", text=json.dumps(result))]


async def serve() -> None:
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def main() -> None:
    import anyio

    anyio.run(serve)


if __name__ == "__main__":
    main()
