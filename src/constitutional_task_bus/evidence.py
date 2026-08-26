"""Evidence and replay hooks for Constitutional Task Bus.

# Mythic: Trace & Evidence Logger / Replay Engine Hook
# Engineering: TaskBusEvidenceRecorder
"""

from __future__ import annotations

import uuid
from typing import Any

from src.aaes_evidence_receipts import create_evidence_receipt

TASK_BUS_SUBSYSTEM = "constitutional-task-bus"


def new_trace_id() -> str:
    return f"taskbus_{uuid.uuid4().hex}"


def seal_intent_evidence(*, trace_id: str, intent: dict[str, Any]) -> dict[str, Any]:
    return create_evidence_receipt(
        claim_label="task_bus:intent_classified",
        subsystem=TASK_BUS_SUBSYSTEM,
        evidence_refs=[trace_id],
        subject={
            "trace_id": trace_id,
            "kind": intent.get("kind"),
            "requested_lanes": list(intent.get("requested_lanes") or []),
        },
        kind="runtime",
    )


def seal_decision_evidence(
    *,
    trace_id: str,
    policy: dict[str, Any],
    prior_refs: list[str],
) -> dict[str, Any]:
    return create_evidence_receipt(
        claim_label="task_bus:authority_decision",
        subsystem=TASK_BUS_SUBSYSTEM,
        evidence_refs=list(prior_refs) + [trace_id],
        subject={
            "trace_id": trace_id,
            "allowed_lanes": list(policy.get("allowed_lanes") or []),
            "isolation": policy.get("isolation"),
            "decision_event_count": len(list(policy.get("decision_events") or [])),
        },
        kind="attestation",
    )


def seal_dispatch_evidence(
    *,
    trace_id: str,
    executions: list[dict[str, Any]],
    prior_refs: list[str],
) -> dict[str, Any]:
    return create_evidence_receipt(
        claim_label="task_bus:dispatch_complete",
        subsystem=TASK_BUS_SUBSYSTEM,
        evidence_refs=list(prior_refs) + [trace_id],
        subject={
            "trace_id": trace_id,
            "execution_statuses": [
                {"lane_id": e.get("lane_id"), "status": e.get("status"), "reason_code": e.get("reason_code")}
                for e in executions
            ],
        },
        kind="runtime",
    )


def build_replay_handoff(*, trace_id: str, run_id: str | None = None) -> dict[str, Any]:
    """Emit replayable identifiers; hand off to TemporalReplay / run ledger when present."""
    handoff = {
        "replayable": True,
        "trace_id": trace_id,
        "run_id": run_id,
        "subject_type": "task_bus_dispatch",
        "subject_id": run_id or trace_id,
        "temporal_replay_path": (
            f"/operator/replay/task_bus_dispatch/{run_id or trace_id}"
        ),
        "note": "Replay via operator TemporalReplay surface when ledger row exists.",
    }
    return handoff


def try_create_run_ledger_row(
    *,
    trace_id: str,
    title: str,
    meta: dict[str, Any],
) -> str | None:
    """Best-effort run ledger append — never crashes the bus."""
    try:
        from src.jarvis_operator import jarvis_operator

        run = jarvis_operator.create_run(
            session_id=str(meta.get("session_id") or "global"),
            title=title[:120] or f"Task Bus {trace_id}",
            kind="task_bus_dispatch",
            meta={**meta, "trace_id": trace_id},
        )
        if isinstance(run, dict):
            return str(run.get("run_id") or run.get("id") or "") or None
        return str(getattr(run, "run_id", "") or "") or None
    except Exception:
        return None
