"""Constitutional Task Bus shared types and result contracts.

# Mythic: Constitutional Task Bus
# Engineering: ConstitutionalTaskBusTypes
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


LANE_IDS = (
    "microsoft_style_tasks",
    "openai_style_tools",
    "anthropic_style_analysis",
    "picture_generation",
)

INTENT_KINDS = ("task", "skill", "workflow", "picture", "mixed", "unknown")

AUTH_STATUSES = ("ready", "needs_auth", "demo", "denied")


@dataclass
class LaneDecision:
    """Policy decision for one lane — never silent."""

    lane_id: str
    allowed: bool
    reason_code: str
    authority: str = "assist"
    auth_status: str = "demo"
    activation_hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LaneExecutionRecord:
    """Ordered lane outcome recorded under one bus trace."""

    lane_id: str
    status: str  # completed | denied | needs_auth | skipped | error
    reason_code: str
    mode: str  # demo | live
    result: dict[str, Any] = field(default_factory=dict)
    decision_event: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BusDispatchResult:
    """Normalized egress from dispatch_task_bus_request()."""

    ok: bool
    trace_id: str
    intent: dict[str, Any]
    policy: dict[str, Any]
    lane_plan: list[dict[str, Any]]
    executions: list[dict[str, Any]]
    evidence_refs: list[str]
    decision_events: list[dict[str, Any]]
    replay: dict[str, Any]
    deep_links: dict[str, str] = field(default_factory=dict)
    reason_codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
