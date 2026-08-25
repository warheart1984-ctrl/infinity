"""Sovereign gate router — THE single sanctioned TS↔Python write crossing.

POST /sovereign/gate is a thin wrapper over CenGovernanceBridge.gate_commit().
No enforcement logic lives here: classification, invariant evaluation,
INV-021 VT checks, receipts, and certificates all belong to the bridge.

Contract:
- 200 {outcome: "approved", cen_receipt_id, commitCertificate{...},
       evidence_receipt_id}
- 200 {outcome: "denied", reason_code, reason_detail, transition_id, ...}
  Denials are 200 on purpose: refusals are evidence, and the denial body is
  the challenge-response material callers re-mint against
  (mint_vt_token_from_denial).
- 503 only when the bridge fails closed (cen_failed_closed).

This file is the ONLY router permitted to define a write method under
/sovereign/*. app/sovereign_router.py remains read-only by construction
(test_router_defines_no_write_methods pins that).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.cen_governance_bridge import CenGovernanceBridge, cen_governance_bridge

router = APIRouter(prefix="/sovereign", tags=["sovereign-gate"])

# Process-local gate binding; tests may rebind to an isolated bridge instance
# exactly like app.sovereign_router._reader.
_bridge: CenGovernanceBridge = cen_governance_bridge

VALID_TRANSITION_TYPES = {"runtime_action", "law_mutation"}

REQUIRED_FIELDS = ("transition_id", "transition_type", "payload", "requested_capabilities")


def _validate_gate_body(body: object) -> tuple[dict | None, str]:
    """Return (normalised_fields, "") or (None, reason_detail).

    Shape validation only — never policy. Policy belongs to the bridge.
    """
    if not isinstance(body, dict):
        return None, "body must be a JSON object"
    for field in REQUIRED_FIELDS:
        if field not in body or body[field] is None:
            return None, f"missing required field: {field}"
    if not isinstance(body["transition_id"], str) or not body["transition_id"].strip():
        return None, "transition_id must be a non-empty string"
    if body["transition_type"] not in VALID_TRANSITION_TYPES:
        return None, (
            f"transition_type must be one of {sorted(VALID_TRANSITION_TYPES)}"
        )
    if not isinstance(body["payload"], dict):
        return None, "payload must be a JSON object"
    caps = body["requested_capabilities"]
    if not isinstance(caps, list) or not caps or not all(
        isinstance(cap, str) and cap.strip() for cap in caps
    ):
        return None, "requested_capabilities must be a non-empty array of strings"
    granted = body.get("granted_capabilities")
    if granted is not None and (
        not isinstance(granted, list)
        or not all(isinstance(cap, str) and cap.strip() for cap in granted)
    ):
        return None, "granted_capabilities must be an array of strings"
    actor = body.get("actor")
    if actor is not None and (not isinstance(actor, str) or not actor.strip()):
        return None, "actor must be a non-empty string"
    token = body.get("authority_token")
    if token is not None and not isinstance(token, dict):
        return None, "authority_token must be a JSON object"
    normalised = {
        "transition_id": body["transition_id"].strip(),
        "transition_type": body["transition_type"],
        "payload": body["payload"],
        "requested_capabilities": [str(cap).strip() for cap in caps],
        "granted_capabilities": (
            [str(cap).strip() for cap in granted] if granted is not None else None
        ),
        "actor": str(actor).strip() if actor else "operator",
        "authority_token": token,
    }
    return normalised, ""


@router.post("/gate")
async def sovereign_gate(request: Request) -> JSONResponse:
    """Admit one governed state transition through the CEN boundary."""
    try:
        body = await request.json()
    except Exception:
        body = None

    fields, malformed_reason = _validate_gate_body(body)
    if fields is None:
        result = _bridge.record_malformed_refusal(
            submitted=body if isinstance(body, dict) else {},
            reason_detail=malformed_reason,
        )
        return JSONResponse(status_code=200, content=result)

    result = _bridge.gate_commit(
        transition_id=fields["transition_id"],
        transition_type=fields["transition_type"],
        payload=fields["payload"],
        requested_capabilities=fields["requested_capabilities"],
        granted_capabilities=fields["granted_capabilities"],
        actor=fields["actor"],
        authority_token=fields["authority_token"],
    )

    outcome = result.get("outcome")
    if outcome == "approved":
        return JSONResponse(status_code=200, content=result)
    if result.get("reason") == "cen_failed_closed":
        # Bridge could not safely decide — say so, do not mask as evidence.
        return JSONResponse(status_code=503, content=result)
    # Refusals are evidence: 200 carries the re-mintable challenge shape.
    return JSONResponse(status_code=200, content=result)


__all__ = ["router", "_validate_gate_body"]
