"""Operator diplomatic accord registry (Mythic Stage 15 / Release 45)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ACCORD_VERSION = "operator_diplomatic_accord.v1"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_diplomatic_registry(*, repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or _repo_root()
    path = root / "governance" / "operator_diplomatic_registry.v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def adopted_accords(*, repo_root: Path | None = None) -> list[dict[str, Any]]:
    doc = load_diplomatic_registry(repo_root=repo_root)
    return list(doc.get("accords") or [])


def save_adopted_accord(accord: dict[str, Any], *, repo_root: Path | None = None) -> dict[str, Any]:
    from src.cen_governance_bridge import validate_law_state_approval

    record = {key: value for key, value in accord.items() if key != "cen_approval"}
    refusal = validate_law_state_approval(accord.get("cen_approval"), sink="diplomatic_accord", record=record)
    if refusal:
        raise PermissionError(f"CEN-dominated law state write refused: {refusal}")

    root = repo_root or _repo_root()
    path = root / "governance" / "operator_diplomatic_registry.v1.json"
    doc = load_diplomatic_registry(repo_root=root)
    accords = list(doc.get("accords") or [])
    accord_id = str(accord.get("accord_id") or "")
    accords = [a for a in accords if str(a.get("accord_id") or "") != accord_id]
    accords.append(accord)
    doc["accords"] = accords
    path.write_text(json.dumps(doc, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return accord


def validate_diplomatic_registry(*, repo_root: Path | None = None) -> list[str]:
    errors: list[str] = []
    doc = load_diplomatic_registry(repo_root=repo_root)
    if doc.get("operator_diplomatic_registry_version") != "operator_diplomatic_registry.v1":
        errors.append("invalid operator_diplomatic_registry_version")
    for accord in list(doc.get("accords") or []):
        aid = str(accord.get("accord_id") or "")
        if not aid:
            errors.append("accord missing accord_id")
        if accord.get("accord_version") != ACCORD_VERSION:
            errors.append(f"invalid accord_version on {aid}")
        if not accord.get("operator_promoted"):
            errors.append(f"registry accord must be operator_promoted: {aid}")
    return errors
