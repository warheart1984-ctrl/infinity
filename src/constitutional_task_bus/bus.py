"""Constitutional Task Bus — single governed ingress for tasks & skills.

# Mythic: Constitutional Task Bus
# Engineering: ConstitutionalTaskBus

Flow: Intent → Evidence → Authority → Decision → ordered lane executions.
External providers are governed subcontracts under AAIS law.
No silent reroutes between providers.
"""

from __future__ import annotations

from typing import Any

from src.constitutional_task_bus.evidence import (
    build_replay_handoff,
    new_trace_id,
    seal_decision_evidence,
    seal_dispatch_evidence,
    seal_intent_evidence,
    try_create_run_ledger_row,
)
from src.constitutional_task_bus.intent_parser import TaskBusIntentParser
from src.constitutional_task_bus.lanes import (
    AnthropicStyleAnalysisLane,
    MicrosoftStyleTasksLane,
    OpenAiStyleToolsLane,
    PictureGenerationLane,
    TaskBusLaneAdapter,
)
from src.constitutional_task_bus.policy_engine import TaskBusPolicyEngine
from src.constitutional_task_bus.types import BusDispatchResult, LaneExecutionRecord


DEFAULT_DEEP_LINKS = {
    "image_generator": "/image-generator",
    "adaptive_music": "/adaptive-music",
    "workflows": "/workflows/templates",
    "plugins": "/operator/plugins",
    "task_bus": "/task-bus",
    "jarvis": "/jarvis",
}

# Default action per lane when operator sends a free-form ask
_DEFAULT_ACTION = {
    "microsoft_style_tasks": "plan",
    "openai_style_tools": "run_skill",
    "anthropic_style_analysis": "analyze",
    "picture_generation": "make_picture",
}


class ConstitutionalTaskBus:
    """One ingress: AAIS → Task & Skills Bus."""

    def __init__(
        self,
        *,
        parser: TaskBusIntentParser | None = None,
        policy: TaskBusPolicyEngine | None = None,
        lanes: dict[str, TaskBusLaneAdapter] | None = None,
    ) -> None:
        self.parser = parser or TaskBusIntentParser()
        self.policy = policy or TaskBusPolicyEngine()
        self.lanes: dict[str, TaskBusLaneAdapter] = lanes or {
            "microsoft_style_tasks": MicrosoftStyleTasksLane(),
            "openai_style_tools": OpenAiStyleToolsLane(),
            "anthropic_style_analysis": AnthropicStyleAnalysisLane(),
            "picture_generation": PictureGenerationLane(),
        }

    def catalog(self) -> dict[str, Any]:
        return {
            "bus": "ConstitutionalTaskBus",
            "ingress": "dispatch_task_bus_request",
            "doctrine": "Intent → Evidence → Authority → Decision",
            "lanes": [lane.describe() for lane in self.lanes.values()],
            "deep_links": dict(DEFAULT_DEEP_LINKS),
            "not_claimed": [
                "Full Microsoft 365 / Graph OAuth UX",
                "ChatGPT skill store parity",
                "Claude Computer Use",
                "Silent cross-provider fallback",
            ],
        }

    def dispatch(self, payload: dict[str, Any] | None = None) -> BusDispatchResult:
        body = dict(payload or {})
        text = str(body.get("text") or body.get("prompt") or body.get("ask") or "").strip()
        hints = dict(body.get("hints") or {})
        if body.get("lanes"):
            hints["lanes"] = body.get("lanes")

        force_demo = bool(body.get("force_demo", True))
        if "force_demo" not in body and body.get("mode") == "live":
            force_demo = False
        require_live = bool(body.get("require_live", False))
        deny_lanes = [str(x) for x in list(body.get("deny_lanes") or [])]
        allow_lanes = body.get("allow_lanes")
        allow_list = [str(x) for x in allow_lanes] if allow_lanes is not None else None
        session_id = str(body.get("session_id") or "global")
        action_overrides = dict(body.get("actions") or {})

        trace_id = str(body.get("trace_id") or "").strip() or new_trace_id()
        decision_events: list[dict[str, Any]] = []
        evidence_refs: list[str] = []
        reason_codes: list[str] = []

        # 1) Intent
        intent = self.parser.classify(text, hints=hints)
        decision_events.append(
            {
                "event": "intent_classified",
                "reason_code": "TASK_BUS_INTENT_OK",
                "kind": intent.get("kind"),
                "requested_lanes": list(intent.get("requested_lanes") or []),
            }
        )

        # 2) Evidence (intent)
        intent_receipt = seal_intent_evidence(trace_id=trace_id, intent=intent)
        evidence_refs.append(intent_receipt["receipt_id"])

        # 3) Authority / policy
        policy = self.policy.decide(
            intent,
            force_demo=force_demo,
            deny_lanes=deny_lanes,
            allow_lanes=allow_list,
            require_live=require_live,
        )
        decision_events.extend(list(policy.get("decision_events") or []))
        for dec in policy.get("decisions") or []:
            if dec.get("reason_code"):
                reason_codes.append(str(dec["reason_code"]))

        decision_receipt = seal_decision_evidence(
            trace_id=trace_id,
            policy=policy,
            prior_refs=evidence_refs,
        )
        evidence_refs.append(decision_receipt["receipt_id"])

        # 4) Ordered executions — no silent reroute
        executions: list[LaneExecutionRecord] = []
        decision_map = {d["lane_id"]: d for d in (policy.get("decisions") or [])}

        # Preserve intent order for requested lanes
        for lane_id in list(intent.get("requested_lanes") or []):
            dec = decision_map.get(lane_id) or {
                "allowed": False,
                "reason_code": "TASK_BUS_LANE_MISSING_DECISION",
                "auth_status": "denied",
            }
            if not dec.get("allowed"):
                record = LaneExecutionRecord(
                    lane_id=lane_id,
                    status="denied",
                    reason_code=str(dec.get("reason_code") or "TASK_BUS_LANE_DENIED"),
                    mode="none",
                    result={"ok": False, "message": dec.get("activation_hint")},
                    decision_event={
                        "event": "lane_execution_skipped",
                        "lane_id": lane_id,
                        "reason_code": dec.get("reason_code"),
                    },
                )
                executions.append(record)
                decision_events.append(record.decision_event)
                reason_codes.append(record.reason_code)
                continue

            adapter = self.lanes.get(lane_id)
            if adapter is None:
                record = LaneExecutionRecord(
                    lane_id=lane_id,
                    status="error",
                    reason_code="TASK_BUS_LANE_NOT_REGISTERED",
                    mode="none",
                    result={"ok": False},
                    decision_event={
                        "event": "lane_missing",
                        "lane_id": lane_id,
                        "reason_code": "TASK_BUS_LANE_NOT_REGISTERED",
                        "message": "No silent substitute lane selected.",
                    },
                )
                executions.append(record)
                decision_events.append(record.decision_event)
                reason_codes.append(record.reason_code)
                continue

            auth_status = str(dec.get("auth_status") or "demo")
            mode = "live" if auth_status == "ready" and not force_demo else "demo"
            action = str(
                action_overrides.get(lane_id)
                or body.get("action")
                or _DEFAULT_ACTION.get(lane_id)
                or "run"
            )
            lane_payload = {
                "text": text,
                "prompt": text,
                "skill_id": body.get("skill_id"),
                **dict(body.get("lane_payload") or {}),
            }
            result = adapter.execute(
                action=action,
                payload=lane_payload,
                mode=mode,
                trace_id=trace_id,
            )

            # Explicit handoff (e.g. make_picture from analysis) — record, optionally run target
            if result.get("handoff_lane") and result.get("reason_code") == "TASK_BUS_PICTURE_HANDOFF":
                decision_events.append(dict(result.get("decision_event") or {
                    "event": "explicit_lane_handoff",
                    "from": lane_id,
                    "to": result.get("handoff_lane"),
                    "reason_code": "TASK_BUS_PICTURE_HANDOFF",
                }))
                target_id = str(result.get("handoff_lane"))
                if target_id in self.lanes and target_id not in {
                    e.lane_id for e in executions
                }:
                    # Only auto-run handoff if target already in allowed set OR explicitly requested
                    if target_id in (policy.get("allowed_lanes") or []) or target_id in (
                        intent.get("requested_lanes") or []
                    ):
                        pass  # will run in its own turn if listed
                    else:
                        # Explicit decision to also execute handoff target — recorded, not silent
                        decision_events.append(
                            {
                                "event": "handoff_execute_authorized",
                                "lane_id": target_id,
                                "reason_code": "TASK_BUS_EXPLICIT_HANDOFF_EXECUTE",
                                "from": lane_id,
                            }
                        )
                        target = self.lanes[target_id]
                        handoff_result = target.execute(
                            action="make_picture",
                            payload=lane_payload,
                            mode=mode,
                            trace_id=trace_id,
                        )
                        executions.append(
                            LaneExecutionRecord(
                                lane_id=target_id,
                                status="completed" if handoff_result.get("ok") else str(
                                    handoff_result.get("status") or "error"
                                ),
                                reason_code=str(
                                    handoff_result.get("reason_code")
                                    or "TASK_BUS_EXPLICIT_HANDOFF_EXECUTE"
                                ),
                                mode=mode,
                                result=handoff_result,
                                decision_event={
                                    "event": "handoff_lane_executed",
                                    "lane_id": target_id,
                                    "from": lane_id,
                                },
                            )
                        )

            status = "completed"
            if result.get("status") == "needs_auth" or result.get("reason_code") == "TASK_BUS_NEEDS_AUTH":
                status = "needs_auth"
            elif result.get("ok") is False:
                status = str(result.get("status") or "error")
            elif result.get("status") == "handoff":
                status = "handoff"

            reason = str(result.get("reason_code") or "TASK_BUS_LANE_EXECUTED")
            record = LaneExecutionRecord(
                lane_id=lane_id,
                status=status,
                reason_code=reason,
                mode=mode,
                result=result,
                decision_event={
                    "event": "lane_executed",
                    "lane_id": lane_id,
                    "status": status,
                    "mode": mode,
                    "reason_code": reason,
                },
            )
            executions.append(record)
            decision_events.append(record.decision_event)
            reason_codes.append(reason)

        exec_dicts = [e.to_dict() for e in executions]
        dispatch_receipt = seal_dispatch_evidence(
            trace_id=trace_id,
            executions=exec_dicts,
            prior_refs=evidence_refs,
        )
        evidence_refs.append(dispatch_receipt["receipt_id"])

        run_id = try_create_run_ledger_row(
            trace_id=trace_id,
            title=f"Task Bus: {text[:80] or intent.get('kind')}",
            meta={
                "session_id": session_id,
                "kind": intent.get("kind"),
                "lanes": [e.lane_id for e in executions],
            },
        )
        replay = build_replay_handoff(trace_id=trace_id, run_id=run_id)

        any_ok = any(e.status in {"completed", "handoff"} for e in executions)
        all_denied = bool(executions) and all(e.status == "denied" for e in executions)
        ok = bool(any_ok) and not all_denied
        if not executions:
            ok = False
            if "TASK_BUS_NO_LANES" not in reason_codes:
                reason_codes.append("TASK_BUS_NO_LANES")

        return BusDispatchResult(
            ok=ok,
            trace_id=trace_id,
            intent=intent,
            policy=policy,
            lane_plan=[d for d in (policy.get("decisions") or [])],
            executions=exec_dicts,
            evidence_refs=evidence_refs,
            decision_events=decision_events,
            replay=replay,
            deep_links=dict(DEFAULT_DEEP_LINKS),
            reason_codes=list(dict.fromkeys(reason_codes)),
        )


_BUS: ConstitutionalTaskBus | None = None


def get_task_bus() -> ConstitutionalTaskBus:
    global _BUS
    if _BUS is None:
        _BUS = ConstitutionalTaskBus()
    return _BUS


def dispatch_task_bus_request(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Primary ingress — AAIS → Task & Skills Bus."""
    result = get_task_bus().dispatch(payload)
    return result.to_dict()


def task_bus_status() -> dict[str, Any]:
    return get_task_bus().catalog()
