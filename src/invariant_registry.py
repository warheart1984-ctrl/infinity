"""Invariant registry + IDSL-1 compiler — Python port of @aaes-os/invariant-registry.

Mythic: the body's laws are named, numbered, and measured.
Engineering: canonical constitutional invariants (INV-xxx) with receipt
metadata, plus a no-eval IDSL-1 compiler supporting boolean AND/OR/NOT
clauses over the five constitutional dimensions and the legacy
``require <dimension> >= <floor>`` syntax. Mirrors
packages/invariant-registry/src/index.ts in the AAES-OS monorepo.
"""

from __future__ import annotations

import re
from typing import Any, Callable

CONSTITUTIONAL_DIMENSIONS = ("continuity", "governance", "memory", "coordination", "confidence")

ENFORCEMENT_ACTIONS = ("ALLOW", "DENY", "FREEZE", "MANDATORY_REVIEW")

AUTHORITY_TOKEN_TYPES = ("VT", "FT", "MRT", "RT")

CEN_SUBSYSTEM = "constitutional-enforcement-node"

_DIMENSION_RE = r"(continuity|governance|memory|coordination|confidence)"
_CLAUSE_RE = re.compile(
    rf"^{_DIMENSION_RE}\s*(<=|>=|==|<|>)\s*(-?\d+(?:\.\d+)?)$", re.IGNORECASE
)
_REQUIRE_RE = re.compile(
    rf"^require\s+{_DIMENSION_RE}\s*>=\s*(\d+(?:\.\d+)?)$", re.IGNORECASE
)
_IDSL_RE = re.compile(
    r"^WHEN (.+) THEN (ALLOW|DENY|FREEZE|MANDATORY_REVIEW) IF VIOLATED THEN DENY$",
    re.IGNORECASE,
)
_EXPRESSION_ALLOWLIST_RE = re.compile(
    r"^(continuity|governance|memory|coordination|confidence|\d|\s|[<>=.!()andornot-])+$",
    re.IGNORECASE,
)


def canonical_invariant(
    invariant_id: str,
    name: str,
    measured_dimensions: list[str],
    threshold: float,
    expression: str,
    severity: str,
    required_authority_token: str | None = None,
) -> dict[str, Any]:
    return {
        "id": invariant_id,
        "name": name,
        "measured_dimensions": list(measured_dimensions),
        "threshold": threshold,
        "expression": expression,
        "required_authority_token": required_authority_token,
        "receipt_metadata": {"subsystem": CEN_SUBSYSTEM, "severity": severity},
    }


CANONICAL_INVARIANTS: list[dict[str, Any]] = [
    canonical_invariant("INV-007", "Resource Floor", ["continuity"], 50, "continuity >= 50", "high"),
    canonical_invariant("INV-014", "Temporal Regularity", ["coordination"], 55, "coordination >= 55", "medium"),
    canonical_invariant("INV-021", "Identity Boundary", ["memory"], 60, "memory >= 60", "critical", "VT"),
    canonical_invariant("INV-003", "Governance Drift", ["governance"], 70, "governance >= 70", "high"),
    canonical_invariant("INV-031", "Coordination Floor", ["coordination"], 60, "coordination >= 60", "high"),
    canonical_invariant("INV-041", "Confidence Floor", ["confidence"], 70, "confidence >= 70", "medium"),
]


def create_invariant_registry(seed: list[dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    registry: dict[str, dict[str, Any]] = {}
    for definition in seed or []:
        register_invariant(registry, definition)
    return registry


def register_invariant(registry: dict[str, dict[str, Any]], definition: dict[str, Any]) -> dict[str, Any]:
    registry[definition["id"]] = definition
    return definition


def get_invariant(registry: dict[str, dict[str, Any]], invariant_id: str) -> dict[str, Any]:
    try:
        return registry[invariant_id]
    except KeyError:
        raise KeyError(f"invariant not found: {invariant_id}") from None


class CompiledInvariant:
    """Result of compiling an IDSL/require source — evaluate(transition) is pure."""

    def __init__(self, invariant_id: str, evaluate: Callable[[dict[str, Any]], dict[str, Any]]):
        self.invariant_id = invariant_id
        self._evaluate = evaluate

    def evaluate(self, transition: dict[str, Any]) -> dict[str, Any]:
        return self._evaluate(transition)


def compile_invariant_dsl(source: str) -> CompiledInvariant:
    """Compile legacy ``require`` syntax or IDSL-1 without eval."""
    normalized_source = str(source or "").strip()
    if re.match(r"^require\s+", normalized_source, re.IGNORECASE):
        return _compile_require(normalized_source)
    return _compile_idsl(normalized_source)


def _compile_require(source: str) -> CompiledInvariant:
    match = _REQUIRE_RE.match(source.strip())
    if not match:
        raise ValueError(f"unsupported invariant DSL: {source}")
    dimension = match.group(1).lower()
    floor = float(match.group(2))
    invariant_id = f"idsl:{dimension}:min:{_format_number(floor)}"

    def evaluate(transition: dict[str, Any]) -> dict[str, Any]:
        proposed = read_dimension(transition, dimension)
        passed = proposed >= floor
        return {
            "invariant_id": invariant_id,
            "passed": passed,
            "message": (
                f"{dimension} satisfies DSL floor {_format_number(floor)}"
                if passed
                else f"{dimension} {_format_number(proposed)} violated DSL floor {_format_number(floor)}"
            ),
            "action": "ALLOW" if passed else "DENY",
        }

    return CompiledInvariant(invariant_id, evaluate)


def _compile_idsl(source: str) -> CompiledInvariant:
    normalized = re.sub(r"\s+", " ", str(source or "").strip())
    match = _IDSL_RE.match(normalized)
    if not match:
        raise ValueError(f"unsupported IDSL syntax: {source}")
    expression = match.group(1) or ""
    action = (match.group(2) or "DENY").upper()
    if not _EXPRESSION_ALLOWLIST_RE.match(expression):
        raise ValueError(f"unsupported IDSL syntax: {source}")
    invariant_id = f"idsl:{hash_label(expression)}:{action.lower()}"

    def evaluate(transition: dict[str, Any]) -> dict[str, Any]:
        violated = _evaluate_expression(expression, transition)
        return {
            "invariant_id": invariant_id,
            "passed": not violated,
            "action": action if violated else "ALLOW",
            "message": (
                f"IDSL condition violated: {expression}"
                if violated
                else "IDSL condition satisfied"
            ),
        }

    return CompiledInvariant(invariant_id, evaluate)


def _evaluate_expression(expression: str, transition: dict[str, Any]) -> bool:
    """OR of AND-groups: any group where every clause holds means violated."""
    or_parts = re.split(r"\s+OR\s+", expression, flags=re.IGNORECASE)
    return any(
        all(_evaluate_clause(and_part.strip(), transition) for and_part in _split_and(or_part))
        for or_part in or_parts
    )


def _split_and(part: str) -> list[str]:
    return re.split(r"\s+AND\s+", part, flags=re.IGNORECASE)


def _evaluate_clause(clause: str, transition: dict[str, Any]) -> bool:
    negated = bool(re.match(r"^NOT\s+", clause, re.IGNORECASE))
    clean = re.sub(r"^NOT\s+", "", clause, flags=re.IGNORECASE).replace("(", "").replace(")", "").strip()
    match = _CLAUSE_RE.match(clean)
    if not match:
        raise ValueError(f"unsupported IDSL clause: {clause}")
    dimension = match.group(1).lower()
    operator = match.group(2)
    threshold = float(match.group(3))
    value = read_dimension(transition, dimension)
    result = _compare(value, operator, threshold)
    return (not result) if negated else result


def read_dimension(transition: dict[str, Any], dimension: str) -> float:
    payload = transition.get("payload")
    if isinstance(payload, dict) and isinstance(payload.get(dimension), (int, float)):
        return float(payload[dimension])
    context = transition.get("context") or {}
    snapshot = context.get("mri_snapshot") or context.get("mriSnapshot") or {}
    value = snapshot.get(dimension)
    if not isinstance(value, (int, float)):
        raise ValueError(f"missing dimension value: {dimension}")
    return float(value)


def _compare(value: float, operator: str, threshold: float) -> bool:
    if operator == "<":
        return value < threshold
    if operator == "<=":
        return value <= threshold
    if operator == ">":
        return value > threshold
    if operator == ">=":
        return value >= threshold
    if operator == "==":
        return value == threshold
    raise ValueError(f"unsupported operator: {operator}")


def hash_label(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:48]


def _format_number(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return repr(value)
