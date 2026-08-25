"""Spreadsheet export plug — replaces pending_plug native.spreadsheet.export.

# Mythic: Spreadsheet export
# Engineering: SpreadsheetExportMiddlewarePlug
"""

from __future__ import annotations

from typing import Any

from src.operator_middleware_plugs.contract import (
    MiddlewarePlug,
    MiddlewarePlugAction,
    MiddlewarePlugDescriptor,
)


class SpreadsheetExportMiddlewarePlug(MiddlewarePlug):
    plug_id = "native.spreadsheet.export"

    def describe(self) -> MiddlewarePlugDescriptor:
        return MiddlewarePlugDescriptor(
            plug_id=self.plug_id,
            display_name="Spreadsheet Export",
            provider="aais",
            authority_level="assist",
            actions=[
                MiddlewarePlugAction("export", "Export rows", "Deterministic CSV/JSON export plan"),
            ],
            auth_status="demo",
            activation_hint="Local AAIS export — no cloud spreadsheet OAuth required for demo.",
        )

    def execute(self, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = dict(payload or {})
        action = (action or "export").strip() or "export"
        rows = list(payload.get("rows") or [{"metric": "demo", "value": 1}])
        return self._demo(
            action,
            f"Demo spreadsheet export ({len(rows)} rows).",
            {"format": payload.get("format") or "csv", "rows": rows, "path_hint": "/tmp/aais_export_demo.csv"},
        )
