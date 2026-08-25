"""Thin HTTP client adapter for the Jarvis Memoryboard service (Continuity Ledger + AMUL).

The memoryboard runs as a standalone service (see ``jarvis-memoryboard/`` in this
repository). Per its ADAPTER_CONSUMERS.md contract, downstream consumers must:

1. Read via the ledger API and never invent missing provenance.
2. Treat ``conflicts[].unresolved=true`` as open — never assume one memory is true.
3. Write back only through the ledger POST/PATCH write path (single write path).
4. Import no foreign domain semantics from the ledger.

This module transports ledger payloads as plain dicts and enforces those rules
client-side where practical.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8001"
DEFAULT_TIMEOUT_SECONDS = 10.0


def default_base_url() -> str:
    return os.getenv("JARVIS_MEMORYBOARD_URL", DEFAULT_BASE_URL).rstrip("/")


class MemoryboardError(RuntimeError):
    """Raised when the memoryboard service returns an error response."""

    def __init__(self, status_code: int, detail: Any):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"memoryboard {status_code}: {detail}")


class UnresolvedConflictError(RuntimeError):
    """Raised when a caller demands settled truth while conflicts remain open."""


class JarvisMemoryboardClient:
    """Read-mostly client for the Continuity Ledger with a guarded write path."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        self._base_url = (base_url or default_base_url()).rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url, transport=transport, timeout=timeout
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "JarvisMemoryboardClient":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs) -> Any:
        response = self._client.request(method, path, **kwargs)
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise MemoryboardError(response.status_code, detail)
        if not response.content:
            return None
        return response.json()

    # ------------------------------------------------------------------
    # health
    # ------------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    # ------------------------------------------------------------------
    # read-only ledger access
    # ------------------------------------------------------------------

    def get_board(self) -> dict[str, Any]:
        return self._request("GET", "/api/jarvis/memory/board")

    def retrieve(self, query: str, **params) -> list[dict[str, Any]]:
        payload = self._request(
            "GET", "/api/jarvis/memory/retrieve", params={"q": query, **params}
        )
        memories = payload.get("memories", []) if isinstance(payload, dict) else payload
        return [m for m in memories if m.get("unresolved") is not True]

    def settled_retrieve(self, query: str, **params) -> list[dict[str, Any]]:
        """Retrieve and refuse to answer over open conflicts.

        The ledger treats unresolved conflicts as open questions. Callers that
        need settled truth must fail loudly rather than silently pick a side.
        """
        result = self._request(
            "GET", "/api/jarvis/memory/conflicts", params={"subject": query}
            if query
            else {}
        )
        conflicts = (
            result.get("conflicts", [])
            if isinstance(result, dict)
            else (result or [])
        )
        open_conflicts = [c for c in conflicts if c.get("unresolved")]
        if open_conflicts:
            raise UnresolvedConflictError(
                f"{len(open_conflicts)} unresolved conflict(s) for subject {query!r}"
            )
        return self.retrieve(query, **params)

    def list_conflicts(self, subject: str | None = None) -> list[dict[str, Any]]:
        params = {"subject": subject} if subject else {}
        result = self._request("GET", "/api/jarvis/memory/conflicts", params=params)
        return result.get("conflicts", []) if isinstance(result, dict) else (result or [])

    def list_memories(self, **params) -> list[dict[str, Any]]:
        payload = self._request("GET", "/api/jarvis/memory", params=params)
        return payload.get("memories", []) if isinstance(payload, dict) else payload

    def get_memory(self, memory_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/jarvis/memory/{memory_id}")

    def resolve_memory(self, memory_id: str, resolution: str) -> dict[str, Any]:
        """Resolve a memory at summary/detail/evidence resolution (read-only view)."""
        return self._request(
            "GET",
            f"/api/jarvis/memory/{memory_id}/resolve",
            params={"resolution": resolution},
        )

    def emr_status(self) -> dict[str, Any]:
        return self._request("GET", "/api/jarvis/memory/emr/status")

    # ------------------------------------------------------------------
    # single write path (ledger POST/PATCH only)
    # ------------------------------------------------------------------

    def create_memory(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/jarvis/memory", json=body)

    def patch_memory(self, memory_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._request("PATCH", f"/api/jarvis/memory/{memory_id}", json=body)

    # ------------------------------------------------------------------
    # EMR excitation / reinforcement (state physics, not truth)
    # ------------------------------------------------------------------

    def emr_excite(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/jarvis/memory/emr/excite", json=body)

    def emr_reinforce(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/jarvis/memory/emr/reinforce", json=body)

    # ------------------------------------------------------------------
    # AMUL LTM substrate
    # ------------------------------------------------------------------

    def amul_field_status(self) -> dict[str, Any]:
        return self._request("GET", "/api/jarvis/memory/amul/field/status")

    def amul_verify_field(self) -> dict[str, Any]:
        return self._request("POST", "/api/jarvis/memory/amul/field/verify")

    def amul_anchor_all(self, actor: str = "project-infinity") -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/jarvis/memory/amul/anchor",
            json={"anchor_all": True, "actor": actor},
        )

    def amul_lineage(self, memory_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/jarvis/memory/amul/lineage/{memory_id}")
