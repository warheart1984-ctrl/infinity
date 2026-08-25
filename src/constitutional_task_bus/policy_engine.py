"""Policy decisions for Constitutional Task Bus lanes.

# Mythic: Policy Engine
# Engineering: TaskBusPolicyEngine
"""

from __future__ import annotations

import os
from typing import Any

from src.constitutional_task_bus.types import LaneDecision


# Env keys that unlock live (non-demo) mode per lane. Absent → needs_auth / demo.
LANE_AUTH_ENV: dict[str, tuple[str, ...]] = {
    "microsoft_style_tasks": (
        "AAIS_MS_GRAPH_TOKEN",
        "MICROSOFT_GRAPH_TOKEN",
        "MS_GRAPH_ACCESS_TOKEN",
    ),
    "openai_style_tools": ("OPENAI_API_KEY",),
    "anthropic_style_analysis": ("ANTHROPIC_API_KEY",),
    "picture_generation": (),  # AAIS local image path; no vendor key required
}


def _env_present(names: tuple[str, ...]) -> bool:
    return any(bool(str(os.getenv(name) or "").strip()) for name in names)


def _auth_status_for(lane_id: str, *, force_demo: bool) -> tuple[str, str | None]:
    if force_demo:
        return "demo", None
    envs = LANE_AUTH_ENV.get(lane_id, ())
    if lane_id == "picture_generation":
        if os.getenv("AAIS_DISABLE_IMAGE_GENERATION", "false").lower() == "true":
            return (
                "demo",
                "Image generation disabled (AAIS_DISABLE_IMAGE_GENERATION); demo/plan mode.",
            )
        return "ready", None
    if not envs:
        return "demo", None
    if _env_present(envs):
        return "ready", None
    hint = f"Set one of: {', '.join(envs)}"
    return "needs_auth", hint


class TaskBusPolicyEngine:
    """Decide which lanes may run — every deny carries a reason_code."""

    def decide(
        self,
        intent: dict[str, Any],
        *,
        force_demo: bool = True,
        deny_lanes: list[str] | None = None,
        allow_lanes: list[str] | None = None,
        require_live: bool = False,
        isolate_risky: bool = True,
    ) -> dict[str, Any]:
        requested = list(intent.get("requested_lanes") or [])
        deny_set = {str(x) for x in (deny_lanes or [])}
        allow_set = {str(x) for x in (allow_lanes or [])} if allow_lanes else None

        decisions: list[LaneDecision] = []
        decision_events: list[dict[str, Any]] = []

        if not requested:
            event = {
                "event": "policy_deny_empty_intent",
                "reason_code": "TASK_BUS_NO_LANES",
                "message": "No lanes classified; refuse silent provider pick.",
            }
            decision_events.append(event)
            return {
                "allowed_lanes": [],
                "decisions": [],
                "decision_events": decision_events,
                "isolation": "jarvis",
                "require_live": require_live,
                "force_demo": force_demo,
            }

        # Risky code/workflow work → Forge isolation note (still under bus law)
        isolation = "jarvis"
        if isolate_risky and (
            "openai_style_tools" in requested
            and (intent.get("hits") or {}).get("workflow")
        ):
            isolation = "forge_isolated"
            decision_events.append(
                {
                    "event": "isolation_selected",
                    "reason_code": "TASK_BUS_FORGE_ISOLATION",
                    "lane_id": "openai_style_tools",
                    "message": "Workflow/code lane marked Forge-isolated; no silent jarvis substitute.",
                }
            )

        for lane_id in requested:
            if lane_id in deny_set:
                dec = LaneDecision(
                    lane_id=lane_id,
                    allowed=False,
                    reason_code="TASK_BUS_LANE_DENIED",
                    authority="observe",
                    auth_status="denied",
                    activation_hint="Lane explicitly denied by operator/policy.",
                )
                decisions.append(dec)
                decision_events.append(
                    {
                        "event": "lane_denied",
                        "lane_id": lane_id,
                        "reason_code": dec.reason_code,
                        "message": dec.activation_hint,
                    }
                )
                continue

            if allow_set is not None and lane_id not in allow_set:
                dec = LaneDecision(
                    lane_id=lane_id,
                    allowed=False,
                    reason_code="TASK_BUS_LANE_NOT_IN_ALLOWLIST",
                    authority="observe",
                    auth_status="denied",
                    activation_hint="Lane not in allow_lanes allowlist.",
                )
                decisions.append(dec)
                decision_events.append(
                    {
                        "event": "lane_denied",
                        "lane_id": lane_id,
                        "reason_code": dec.reason_code,
                        "message": dec.activation_hint,
                    }
                )
                continue

            auth_status, hint = _auth_status_for(lane_id, force_demo=force_demo)
            if require_live and auth_status == "needs_auth":
                dec = LaneDecision(
                    lane_id=lane_id,
                    allowed=False,
                    reason_code="TASK_BUS_NEEDS_AUTH",
                    authority="assist",
                    auth_status="needs_auth",
                    activation_hint=hint,
                )
                decisions.append(dec)
                decision_events.append(
                    {
                        "event": "lane_denied",
                        "lane_id": lane_id,
                        "reason_code": dec.reason_code,
                        "message": hint or "Credentials required for live mode.",
                    }
                )
                continue

            # Demo is allowed when keys missing — explicit, not a silent vendor switch
            if auth_status == "needs_auth" and not require_live:
                decision_events.append(
                    {
                        "event": "lane_demo_authorized",
                        "lane_id": lane_id,
                        "reason_code": "TASK_BUS_DEMO_FAIL_CLOSED",
                        "message": hint or "Running deterministic demo; live provider not activated.",
                    }
                )
                auth_status = "demo"

            dec = LaneDecision(
                lane_id=lane_id,
                allowed=True,
                reason_code="TASK_BUS_LANE_ALLOWED",
                authority="execute" if isolation == "forge_isolated" and lane_id == "openai_style_tools" else "assist",
                auth_status=auth_status,
                activation_hint=hint,
            )
            decisions.append(dec)
            decision_events.append(
                {
                    "event": "lane_allowed",
                    "lane_id": lane_id,
                    "reason_code": dec.reason_code,
                    "auth_status": auth_status,
                    "authority": dec.authority,
                }
            )

        allowed = [d.lane_id for d in decisions if d.allowed]
        return {
            "allowed_lanes": allowed,
            "decisions": [d.to_dict() for d in decisions],
            "decision_events": decision_events,
            "isolation": isolation,
            "require_live": require_live,
            "force_demo": force_demo,
        }
