"""Task & Skills Bus contracts — Python mirrors of operator TS interfaces.

# Mythic: Constitutional Task Bus contracts
# Engineering: TaskSkillsContracts
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


IntentType = Literal["task", "skill", "workflow", "picture", "mixed"]
RiskLevel = Literal["low", "normal", "high"]
LaneStatus = Literal["ok", "needs_auth", "denied", "error", "demo"]


def _pick(d: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in d and d[key] is not None:
            return d[key]
    return default


@dataclass
class Intent:
    raw: str
    type: IntentType
    confidence: float
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ParsedTask:
    id: str
    action: str
    target: str
    constraints: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ParsedSkill:
    id: str
    action: str
    target: str
    style: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ParsedPicture:
    id: str
    action: str
    target: str
    engine: str | None = None
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TaskSkillsContext:
    user: str
    workspace: str | None = None
    project: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PolicyDecisionInput:
    risk_level: RiskLevel = "normal"
    allowed_providers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_level": self.risk_level,
            "riskLevel": self.risk_level,
            "allowed_providers": list(self.allowed_providers),
            "allowedProviders": list(self.allowed_providers),
        }


@dataclass
class PolicyDecision:
    approved_providers: list[str]
    blocked_providers: list[str]
    reason: str | None = None
    matched_rule_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AuthorityChain:
    requester: str
    approver: str | None = None
    source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProviderCallEvent:
    id: str
    request_id: str
    provider: str
    lane: str
    input: dict[str, Any]
    output: dict[str, Any] | None = None
    error: str | None = None
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceRecord:
    id: str
    request_id: str
    provider: str
    justification: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReplayTrace:
    request_id: str
    events: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    trace_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OrchestratorResult:
    request_id: str
    outputs: dict[str, Any]
    trace: ReplayTrace
    ok: bool = True
    intent: dict[str, Any] = field(default_factory=dict)
    policy: dict[str, Any] = field(default_factory=dict)
    lane_plan: list[dict[str, Any]] = field(default_factory=list)
    authority: dict[str, Any] = field(default_factory=dict)
    reason_codes: list[str] = field(default_factory=list)
    deep_links: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "requestId": self.request_id,
            "ok": self.ok,
            "outputs": self.outputs,
            "trace": self.trace.to_dict(),
            "trace_id": self.trace.trace_id or self.request_id,
            "intent": self.intent,
            "policy": self.policy,
            "lane_plan": self.lane_plan,
            "authority": self.authority,
            "evidence_refs": [e.get("id") for e in self.trace.evidence if isinstance(e, dict)],
            "reason_codes": list(self.reason_codes),
            "deep_links": dict(self.deep_links),
            "decision_events": list(self.trace.events),
        }


@dataclass
class TaskSkillsRequest:
    request_id: str
    intent: Intent
    context: TaskSkillsContext
    tasks: list[ParsedTask] = field(default_factory=list)
    skills: list[ParsedSkill] = field(default_factory=list)
    pictures: list[ParsedPicture] = field(default_factory=list)
    policy: PolicyDecisionInput = field(default_factory=PolicyDecisionInput)
    force_demo: bool = True
    require_live: bool = False
    deny_providers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "requestId": self.request_id,
            "intent": self.intent.to_dict(),
            "context": self.context.to_dict(),
            "tasks": [t.to_dict() for t in self.tasks],
            "skills": [s.to_dict() for s in self.skills],
            "pictures": [p.to_dict() for p in self.pictures],
            "policy": self.policy.to_dict(),
            "force_demo": self.force_demo,
            "require_live": self.require_live,
            "deny_providers": list(self.deny_providers),
        }


# Provider lane ids used by policy + adapters
PROVIDER_LANES = (
    "ms_tasks",
    "ms_docs",
    "gpt_tools",
    "gpt_reasoning",
    "claude_writer",
    "claude_research",
    "image_gen",
    "mandala",
)
