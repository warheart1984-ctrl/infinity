"""Sovereign gate router — the ONE governed write crossing for the demo.

Mythic: every proposal crosses the law exactly once, and the human
touches everything consequential.
Engineering:
  POST /sovereign/gate          propose an action; CEN judges it
  POST /sovereign/gate/approve  the HUMAN at this console mints a VT for
                                a specific awaited transition (challenge-
                                response; the token binds that transition id)
  POST /sovereign/gate/replay   re-judge a stored proposal on a fresh node;
                                identical verdict + receipt hash or failure

Effect mapping (demo constitution, aligned with infinity-runtime):
  read                        -> runtime_action, floors still apply
  write                       -> runtime_action + human approval required
                                 (await -> approve -> allow)
  deploy | authority_change | audit_delete
                              -> law_mutation without VT = DENIED by the
                                 bridge itself (cen_vt_required). The
                                 refusal receipt chains as evidence.

This router never weakens the bridge: gate_commit stays the only judge.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.cen_governance_bridge import cen_governance_bridge
from src.constitutional_enforcement_node import (
    authority_token_signature,
    issue_authority_token,
)

router = APIRouter(prefix="/sovereign/gate", tags=["sovereign-gate"])

# The gate's own append-only judgment history. Each judgment runs on a
# stateless node seeded with the previous gate receipt, so the gate ledger
# chains across judgments while every individual intent stays re-judgeable.
GATE_HISTORY: list[dict[str, Any]] = []


def gate_history_receipts() -> list[dict[str, Any]]:
    """Raw chained receipts for read-only consumers (/sovereign/state)."""
    return [entry["receipt"] for entry in GATE_HISTORY]


def gate_history_certificates() -> dict[str, dict[str, Any]]:
    return {entry["receipt"]["receiptId"]: entry["certificate"]
            for entry in GATE_HISTORY if entry.get("certificate")}

FORBIDDEN_EFFECTS = ("deploy", "authority_change", "audit_delete")
LAW_MUTATION_REQUIRED_TOKEN_TYPE = "VT"


class GateProposal(BaseModel):
    action: str = Field(min_length=1)
    target: str = Field(min_length=1)
    effect: str = Field(pattern="^(read|write|deploy|authority_change|audit_delete)$")
    risk: str = Field(pattern="^(low|medium|high|critical)$")
    actor: str = "operator"
    payload: dict[str, Any] = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    transition_id: str = Field(min_length=1)


class ReplayRequest(BaseModel):
    proposal: GateProposal
    expected_verdict: str = Field(pattern="^(allow|deny)$")
    expected_payload_hash: str = Field(min_length=1)
    expected_state_hash: str | None = None


def _transition_id(proposal: GateProposal) -> str:
    material = json.dumps(
        {
            "action": proposal.action,
            "target": proposal.target,
            "effect": proposal.effect,
            "risk": proposal.risk,
            "payload": proposal.payload,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]
    return f"transition:gate:{digest}"


def _judge(proposal: GateProposal, approval_token: dict[str, Any] | None) -> dict[str, Any]:
    """One crossing of the law on a STATELESS node.

    Same doctrine as gate_law_state_write: content-addressed transition ids
    must be re-judgeable (approve->retry, replay proofs); cross-attempt
    replay memory would let one judgment poison every future retry of the
    same intent. Replay safety lives in token binding + sink-side approval,
    not in node memory.
    """
    from src.constitutional_enforcement_node import ConstitutionalEnforcementNode

    fresh = ConstitutionalEnforcementNode(invariants=list(cen_governance_bridge._invariants))
    if GATE_HISTORY:
        # Seed the chain: this judgment links onto the previous gate receipt.
        fresh._ledger.append(dict(GATE_HISTORY[-1]["receipt"]))
    saved = cen_governance_bridge._node
    cen_governance_bridge._node = fresh
    try:
        return _judge_on_current_node(proposal, approval_token)
    finally:
        cen_governance_bridge._node = saved


def _record_history(shaped: dict[str, Any]) -> dict[str, Any]:
    receipt_id = shaped.get("receipt_id")
    cert = shaped.get("certificate")
    if receipt_id and not any(e["receipt"]["receiptId"] == receipt_id for e in GATE_HISTORY):
        node_receipts = cen_governance_bridge._node.receipts()
        raw = next((r for r in reversed(node_receipts)
                    if r["receiptId"] == receipt_id), None)
        if raw is not None:
            GATE_HISTORY.append({"receipt": raw, "certificate": cert})
    return shaped


def _judge_on_current_node(proposal: GateProposal, approval_token: dict[str, Any] | None) -> dict[str, Any]:
    transition_id = _transition_id(proposal)

    if proposal.effect in FORBIDDEN_EFFECTS:
        # Constitutionally forbidden: judge as law mutation with no VT so
        # the DENIAL itself becomes chained evidence.
        result = cen_governance_bridge.gate_commit(
            transition_id=transition_id,
            transition_type="law_mutation",
            payload={"action": proposal.action, "target": proposal.target,
                     "effect": proposal.effect, "risk": proposal.risk,
                     **proposal.payload},
            requested_capabilities=["law:mutate"],
            granted_capabilities=["workflow:execute", "state:commit", "law:mutate"],
            actor=proposal.actor,
            authority_token=None,
        )
        return _record_history(_shape(result, proposal, transition_id, approval=None))

    if proposal.effect == "write" and approval_token is None:
        # Consequential: wait for the human. No receipt yet — nothing judged.
        return {
            "verdict": "await_human_approval",
            "reason_codes": ["APPROVAL_REQUIRED"],
            "transition_id": transition_id,
            "proposal": proposal.model_dump(),
            "note": "This action exceeds current autonomy bounds. Approve to mint a bound VT.",
        }

    result = cen_governance_bridge.gate_commit(
        transition_id=transition_id,
        transition_type="runtime_action",
        payload={"action": proposal.action, "target": proposal.target,
                 "effect": proposal.effect, "risk": proposal.risk,
                 **proposal.payload},
        requested_capabilities=["state:commit"] if proposal.effect == "write" else ["state:read"],
        granted_capabilities=["workflow:execute", "state:commit", "state:read"],
        actor=proposal.actor,
        authority_token=approval_token,
    )
    return _record_history(_shape(result, proposal, transition_id, approval=approval_token))


def _shape(
    result: dict[str, Any],
    proposal: GateProposal,
    transition_id: str,
    *,
    approval: dict[str, Any] | None,
) -> dict[str, Any]:
    if result.get("outcome") == "approved":
        return {
            "verdict": "allow",
            "reason_codes": ["ALLOWED"],
            "transition_id": transition_id,
            "receipt_hash": result["cen_receipt_hash"],
            "receipt_id": result["cen_receipt_id"],
            "fingerprint": {
                # Time-free and chain-free: what replay must reproduce.
                "payload_hash": result["payload_hash"],
                "state_hash": (result.get("commitCertificate") or {}).get("resulting_state_hash"),
            },
            "certificate": result.get("commitCertificate"),
            "proposal": proposal.model_dump(),
        }
    # The bridge records WHY it refused in result["reason"]; the node's own
    # reasonCode is generic for forced refusals (INVARIANT_VIOLATION).
    bridge_reason = result.get("reason") or ""
    if bridge_reason == "cen_vt_required":
        mapped = ["CONSTITUTIONALLY_FORBIDDEN"]
    else:
        node_code = (result.get("decision") or {}).get("reasonCode") or ""
        mapped = [node_code or "CEN_DENIED"]
    return {
        "verdict": "deny",
        "reason_codes": mapped,
        "reason_detail": result.get("reason_detail"),
        "transition_id": transition_id,
        "receipt_hash": result.get("cen_receipt_hash"),
        "receipt_id": result.get("cen_receipt_id"),
        "fingerprint": {"payload_hash": None, "state_hash": None},
        "proposal": proposal.model_dump(),
    }


@router.post("")
def gate(proposal: GateProposal) -> dict[str, Any]:
    """Propose one action. The kernel judges; the console renders."""
    return _judge(proposal, approval_token=None)


@router.post("/approved")
def gate_approved(body: dict[str, Any]) -> dict[str, Any]:
    """Re-submit an approved proposal with its minted VT."""
    proposal = GateProposal(**body["proposal"])
    token = body.get("approval_token") or {}
    if str(token.get("tokenType") or "").upper() != LAW_MUTATION_REQUIRED_TOKEN_TYPE:
        return {"verdict": "deny", "reason_codes": ["INVALID_APPROVAL_TOKEN"],
                "transition_id": _transition_id(proposal), "proposal": body.get("proposal")}
    return _judge(proposal, approval_token=token)


@router.post("/approve")
def approve(body: ApprovalRequest) -> dict[str, Any]:
    """THE HUMAN ACT: mint a VT bound to exactly this awaited transition.

    Anyone who can reach this endpoint IS the operator — that is the demo's
    trust boundary, stated plainly.
    """
    token = issue_authority_token(
        token_id=f"vt-operator-{hashlib.sha256(body.transition_id.encode()).hexdigest()[:8]}",
        token_type=LAW_MUTATION_REQUIRED_TOKEN_TYPE,
        scope=["state:commit"],
        transition_id=body.transition_id,
        expires_at="2999-01-01T00:00:00.000Z",
    )
    return {"approval_token": token}


@router.post("/replay")
def replay(body: ReplayRequest) -> dict[str, Any]:
    """Replay determinism proof on a FRESH judge.

    Receipt hashes embed issued_at and chain position (provenance), so —
    exactly like infinity-runtime — determinism is claimed over the
    time-free evidence: verdict, payload hash, resulting state hash.
    """
    rejudged = _judge(body.proposal, approval_token=None)

    fp = rejudged.get("fingerprint") or {}
    checks = {
        "verdict_matches": rejudged.get("verdict") == body.expected_verdict,
        "payload_hash_matches": fp.get("payload_hash") == body.expected_payload_hash,
        "state_hash_matches": (
            body.expected_state_hash is None
            or fp.get("state_hash") == body.expected_state_hash
        ),
    }
    match = all(checks.values())
    return {
        "replay_ok": bool(match),
        **checks,
        "expected": {"verdict": body.expected_verdict,
                     "payload_hash": body.expected_payload_hash,
                     "state_hash": body.expected_state_hash},
        "replayed": {"verdict": rejudged.get("verdict"), **fp},
        "detail": ("identical verdict and time-free fingerprints from a fresh judge"
                   if match else
                   "REPLAY MISMATCH - evidence disagrees with itself"),
    }


def verify_token_shape(token: dict[str, Any]) -> bool:
    """Local helper used by tests; mirrors node-side signature check."""
    return bool(token.get("signature")) and token["signature"] == authority_token_signature(token)
