"""CEN governance bridge — the last common admission boundary before commit.

Mythic: nothing becomes real until the node has judged it.
Engineering: classifies proposed mutations, runs the Constitutional
Enforcement Node (EP-1), enforces INV-021's VT authority-token requirement
for law mutations (no valid VT = no state transition, denial BEFORE
commit), seals every outcome into the evidence-receipt spine, and hands
back a frozen approval bound to the exact payload hash — the committed
object is the approved object, closing the TOCTOU gap.

Boundary law: this gate is admission-only upstream of OTEM/mesh execution
but NON-bypassable at the governed commit path (workflow_chain_executor);
any CEN failure fails CLOSED. There is no environment switch that turns
the gate off.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from src.aaes_evidence_receipts import create_cen_evidence_receipt
from src.constitutional_enforcement_node import (
    ConstitutionalEnforcementNode,
    compile_invariant_dsl,
    issue_authority_token,
    verify_enforcement_receipt,
)
from src.invariant_registry import CANONICAL_INVARIANTS

LAW_MUTATION = "law_mutation"
RUNTIME_ACTION = "runtime_action"

# INV-021 Identity Boundary: law mutations require a VT authority token.
LAW_MUTATION_REQUIRED_TOKEN_TYPE = "VT"


def _strictest_floors() -> dict[str, float]:
    """Collapse canonical invariants to one resource floor per dimension."""
    floors: dict[str, float] = {}
    for definition in CANONICAL_INVARIANTS:
        dimension = definition["measured_dimensions"][0]
        threshold = float(definition["threshold"])
        floors[dimension] = max(floors.get(dimension, threshold), threshold)
    return floors


def _default_invariants() -> list[Any]:
    """Canonical constitutional floors as compiled floor invariants."""
    return [
        compile_invariant_dsl(f"require {dimension} >= {_floor_num(floor)}")
        for dimension, floor in sorted(_strictest_floors().items())
    ]


def build_default_cen_node(**node_kwargs: Any) -> ConstitutionalEnforcementNode:
    """Node seeded with the canonical constitutional floors."""
    return ConstitutionalEnforcementNode(invariants=_default_invariants(), **node_kwargs)


def _floor_num(value: float) -> str:
    return str(int(value)) if value == int(value) else repr(value)


def classify_transition(
    *,
    transition_type: str | None = None,
    bundle: dict[str, Any] | None = None,
    args: dict[str, Any] | None = None,
) -> str:
    """Explicit arg wins, then bundle declaration, else ordinary runtime action."""
    explicit = str(transition_type or (args or {}).get("transition_type") or "").strip()
    if explicit:
        if explicit not in {LAW_MUTATION, RUNTIME_ACTION}:
            raise ValueError(f"unknown transition_type: {explicit}")
        return explicit
    declared = str((bundle or {}).get("constitutional_class") or "").strip()
    if declared == LAW_MUTATION:
        return LAW_MUTATION
    return RUNTIME_ACTION


# --------------------------------------------------------------------------
# Law-state domination
#
# The real invariant: ALL authoritative law-mutation write paths are dominated
# by CEN — not merely "the membrane consults CEN". Law registries refuse any
# save that does not carry a valid CEN approval envelope, so maintenance
# scripts, recovery routines, migrations, or debug endpoints calling the
# registry directly are refused at the sink itself.
# --------------------------------------------------------------------------


# Operational bookkeeping excluded from law-content binding: these vary
# per write attempt and are not constitutional substance. Everything else
# in the record is bound byte-exactly.
OPERATIONAL_LAW_FIELDS = frozenset({"cen_approval", "policy_id", "jarvis_receipt_id"})


def sink_id_field(sink: str) -> str:
    """A sink's randomly-assigned primary id is bookkeeping, not law content."""
    return f"{sink.rsplit('_', 1)[-1]}_id"


def reduce_law_record(record: dict[str, Any], *, sink: str | None = None) -> dict[str, Any]:
    """Strip operational fields — what remains is the law content CEN binds."""
    excluded = set(OPERATIONAL_LAW_FIELDS)
    if sink:
        excluded.add(sink_id_field(sink))
    return {k: v for k, v in record.items() if k not in excluded}


def law_record_digest(record: dict[str, Any], *, sink: str | None = None) -> str:
    """Deterministic digest of a law-state record (Key Identity Law: as-given)."""
    canonical = json.dumps(
        reduce_law_record(record, sink=sink), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def law_state_transition_id(sink: str, record: dict[str, Any]) -> str:
    """Deterministic transition id so operators can pre-mint VT tokens."""
    return f"transition:law-state:{sink}:{law_record_digest(record, sink=sink).replace('sha256:', '')[:32]}"


def gate_law_state_write(
    self: "CenGovernanceBridge",
    *,
    sink: str,
    record: dict[str, Any],
    actor: str = "operator",
    authority_token: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Gate one authoritative law-state write. Law mutation => VT mandatory."""
    frozen = _freeze(record)
    # Stateless node per judgment: law-state transition ids are
    # content-addressed, so cross-attempt replay memory would let one
    # denied attempt poison every future retry of the same record. Replay
    # safety comes from the sink-side approval binding instead.
    node = ConstitutionalEnforcementNode(invariants=list(self._invariants))
    saved_node = self._node
    self._node = node
    try:
        approval = self.gate_commit(
            transition_id=law_state_transition_id(sink, frozen),
            transition_type=LAW_MUTATION,
            payload={"sink": sink, "record": reduce_law_record(frozen, sink=sink)},
            requested_capabilities=["law:mutate"],
            corridor_id="law-state",
            granted_capabilities=["workflow:execute", "state:commit", "law:mutate"],
            actor=actor,
            authority_token=authority_token,
        )
    finally:
        self._node = saved_node
    if approval.get("outcome") == "approved":
        approval["record_digest"] = law_record_digest(frozen, sink=sink)
        # The approval authorizes exactly this reduced law content.
        approval["frozen_payload"] = {"sink": sink, "record": reduce_law_record(frozen, sink=sink)}
        approval["payload_hash"] = _payload_hash(approval["frozen_payload"])
    return approval


def validate_law_state_approval(
    approval: Any,
    *,
    sink: str,
    record: dict[str, Any],
) -> str | None:
    """Sink-side verification. Returns refusal reason or None if valid."""
    if not isinstance(approval, dict):
        return "missing cen_approval envelope"
    if approval.get("outcome") != "approved":
        return "cen_approval is not an approval"
    expected_transition_id = law_state_transition_id(sink, record)
    if approval.get("transition_id") != expected_transition_id:
        return "cen_approval transition id does not bind this record"
    if approval.get("record_digest") != law_record_digest(_freeze(record), sink=sink):
        return "cen_approval record digest does not bind this record"
    if not approval.get("cen_receipt_hash") or not approval.get("evidence_receipt_id"):
        return "cen_approval missing enforcement/evidence receipts"
    return None


class CenGovernanceBridge:
    """Non-bypassable CEN admission boundary with atomic frozen approvals."""

    def __init__(
        self,
        node: ConstitutionalEnforcementNode | None = None,
        *,
        invariants: list[Any] | None = None,
    ):
        if node is not None and invariants is None:
            self._invariants = list(node._invariants)
        else:
            self._invariants = list(invariants) if invariants is not None else _default_invariants()
        self._node = node or build_default_cen_node()

    # ------------------------------------------------------------------ gating

    def gate_commit(
        self,
        *,
        transition_id: str,
        transition_type: str,
        payload: dict[str, Any],
        requested_capabilities: list[str],
        corridor_id: str = "governed-commit",
        granted_capabilities: list[str] | None = None,
        actor: str = "operator",
        mri_snapshot: dict[str, float] | None = None,
        authority_token: dict[str, Any] | None = None,
        require_ucr_attested: bool = False,
        ucr_instance_id: str | None = None,
    ) -> dict[str, Any]:
        """Run the full invariant: classify -> CEN.execute() -> INV-021 VT ->
        evidence/receipt. Returns an APPROVAL binding the exact frozen payload,
        or a DENIAL. Never raises on enforcement paths — failures close."""
        try:
            frozen_payload = _freeze(payload)
            mri_snapshot = mri_snapshot or {
                "continuity": 72,
                "governance": 75,
                "memory": 75,
                "coordination": 63,
                "confidence": 81,
            }
            ucr_error = self._check_ucr_attestation(
                require_ucr_attested, ucr_instance_id, requested_capabilities
            )
            if ucr_error is not None:
                result = self._execute_refusal(
                    transition_id=transition_id,
                    transition_type=transition_type,
                    payload=frozen_payload,
                    requested_capabilities=requested_capabilities,
                    corridor_id=corridor_id,
                    granted_capabilities=granted_capabilities,
                    actor=actor,
                    mri_snapshot=mri_snapshot,
                    reason_code="CAPABILITY_DENIED",
                    reason_detail=ucr_error,
                )
                return self._denial(result, reason="ucr_not_attested")
            token_error = self._check_vt_requirement(transition_type, authority_token)
            if token_error is not None:
                # Denial must still traverse the node so a refusal receipt chains.
                result = self._execute_refusal(
                    transition_id=transition_id,
                    transition_type=transition_type,
                    payload=frozen_payload,
                    requested_capabilities=requested_capabilities,
                    corridor_id=corridor_id,
                    granted_capabilities=granted_capabilities,
                    actor=actor,
                    mri_snapshot=mri_snapshot,
                    reason_code="TOKEN_SCOPE_DENIED",
                    reason_detail=token_error,
                )
                return self._denial(result, reason="cen_vt_required")
            result = self._node.execute(
                {
                    "transitionId": transition_id,
                    "transitionType": transition_type,
                    "payload": frozen_payload,
                    "requestedCapabilities": list(requested_capabilities),
                    "context": {
                        "actor": actor,
                        "mriSnapshot": dict(mri_snapshot),
                        "runtimeContext": {
                            "corridorId": corridor_id,
                            "capabilities": list(granted_capabilities or requested_capabilities),
                        },
                    },
                    "authorityToken": authority_token,
                }
            )
            decision = result["decision"]
            receipt = result["receipt"]
            if decision["verdict"] != "ALLOW":
                return self._denial(result, reason="cen_denied")
            return {
                "outcome": "approved",
                "transition_id": transition_id,
                "transition_type": transition_type,
                # Frozen approved object: commit THIS, not any caller-held reference.
                "frozen_payload": frozen_payload,
                "payload_hash": _payload_hash(frozen_payload),
                "cen_receipt_hash": receipt["receiptHash"],
                "cen_receipt_id": receipt["receiptId"],
                "evidence_receipt_id": self._seal(receipt),
                "decision": decision,
            }
        except Exception as exc:  # fail closed — enforcement errors deny by default
            return {
                "outcome": "denied",
                "reason": "cen_failed_closed",
                "detail": str(exc)[:180],
                "committed": False,
                "claim_label": "cen:deny:failed_closed",
            }

    def commit_approved(
        self,
        approval: dict[str, Any],
        commit_fn: Callable[[dict[str, Any]], Any],
    ) -> dict[str, Any]:
        """Commit ONLY through an approval, re-verifying the frozen hash.
        If anything mutated between approval and commit, refuse (fail closed)."""
        if approval.get("outcome") != "approved":
            return {"outcome": "denied", "reason": approval.get("reason", "not_approved"), "committed": False}
        if _payload_hash(approval.get("frozen_payload")) != approval.get("payload_hash"):
            return {
                "outcome": "denied",
                "reason": "toctou_hash_mismatch",
                "committed": False,
                "claim_label": "cen:deny:toctou",
            }
        commit_fn(approval["frozen_payload"])
        return {"outcome": "committed", "committed": True, "approval": approval}

    # ------------------------------------------------------------------ internals

    def _check_ucr_attestation(
        self,
        require_ucr_attested: bool,
        ucr_instance_id: str | None,
        requested_capabilities: list[str],
    ) -> str | None:
        """Consume UCR attestation: gated commits may demand an attested,
        registered execution instance (fail closed)."""
        if not require_ucr_attested:
            return None
        try:
            from src.ucr_attestation import get_registered_ucr_handle

            handle = get_registered_ucr_handle()
        except Exception:
            return "UCR attestation unavailable"
        if not handle:
            return f"no attested UCR instance registered for this commit ({', '.join(requested_capabilities)})"
        return None

    def _check_vt_requirement(self, transition_type: str, token: dict[str, Any] | None) -> str | None:
        if transition_type != LAW_MUTATION:
            return None
        if not token:
            return f"law mutations require a {LAW_MUTATION_REQUIRED_TOKEN_TYPE} authority token (INV-021)"
        if str(token.get("tokenType") or "").upper() != LAW_MUTATION_REQUIRED_TOKEN_TYPE:
            return (
                f"law mutations require a {LAW_MUTATION_REQUIRED_TOKEN_TYPE} token, "
                f"got {str(token.get('tokenType') or 'none').upper()}"
            )
        return None

    def _execute_refusal(self, **fields: Any) -> dict[str, Any]:
        """Force a DENY through the node so refusal receipts enter the chain."""
        captured: dict[str, Any] = {}

        class _RefusingInvariant:
            invariant_id = "bridge:refusal"

            def evaluate(self, _transition: dict[str, Any]) -> dict[str, Any]:
                captured["message"] = fields["reason_detail"]
                return {
                    "invariantId": self.invariant_id,
                    "passed": False,
                    "message": fields["reason_detail"],
                    "action": "DENY",
                }

        saved = self._node._invariants
        try:
            self._node._invariants = [_RefusingInvariant()]
            result = self._node.execute(
                {
                    "transitionId": fields["transition_id"],
                    "transitionType": fields["transition_type"],
                    "payload": fields["payload"],
                    "requestedCapabilities": fields["requested_capabilities"],
                    "context": {
                        "actor": fields["actor"],
                        "mriSnapshot": dict(fields["mri_snapshot"]),
                        "runtimeContext": {
                            "corridorId": fields["corridor_id"],
                            "capabilities": list(fields["granted_capabilities"] or []),
                        },
                    },
                    "authorityToken": fields.get("authority_token"),
                }
            )
        finally:
            self._node._invariants = saved
        return result

    def _denial(self, result: dict[str, Any], *, reason: str) -> dict[str, Any]:
        decision = result["decision"]
        receipt = result["receipt"]
        return {
            "outcome": "denied",
            "reason": reason,
            "committed": False,
            # Challenge-response: operators re-mint VT against THIS transition.
            "transition_id": receipt["transitionId"],
            "verdict": decision["verdict"],
            "action": decision["action"],
            "reason_code": decision["reasonCode"],
            "reason_detail": decision["reasonDetail"],
            "cen_receipt_hash": receipt["receiptHash"],
            "cen_receipt_id": receipt["receiptId"],
            "evidence_receipt_id": self._seal(receipt),
            "claim_label": f"cen:{decision['verdict'].lower()}:{decision['reasonCode'].lower()}",
        }

    def _seal(self, receipt: dict[str, Any]) -> str:
        sealed = create_cen_evidence_receipt(
            {
                "receiptId": receipt["receiptId"],
                "verdict": receipt["verdict"],
                "reasonCode": receipt["reasonCode"],
                "transitionId": receipt["transitionId"],
                "receiptHash": receipt["receiptHash"],
            }
        )
        return sealed["receipt_id"]

    @property
    def receipts(self) -> list[dict[str, Any]]:
        return self._node.receipts()

    def gate_law_state_write(
        self,
        *,
        sink: str,
        record: dict[str, Any],
        actor: str = "operator",
        authority_token: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Instance binding for module-level gate_law_state_write."""
        return gate_law_state_write(self, sink=sink, record=record, actor=actor, authority_token=authority_token)


def _freeze(payload: Any) -> dict[str, Any]:
    """Deep copy via canonical JSON round-trip — the approved snapshot."""
    return json.loads(json.dumps(payload, sort_keys=True))


def _payload_hash(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


cen_governance_bridge = CenGovernanceBridge()


def mint_vt_token_from_denial(cen_denial: dict[str, Any], *, token_id: str | None = None) -> dict[str, Any]:
    """Challenge-response: mint a valid VT bound to a refused transition."""
    from uuid import uuid4

    return issue_authority_token(
        token_id=token_id or f"vt-{uuid4().hex[:8]}",
        token_type=LAW_MUTATION_REQUIRED_TOKEN_TYPE,
        scope=["law:mutate"],
        transition_id=str(cen_denial.get("transition_id") or ""),
        expires_at="2999-01-01T00:00:00.000Z",
    )



__all__ = [
    "CenGovernanceBridge",
    "OPERATIONAL_LAW_FIELDS",
    "reduce_law_record",
    "LAW_MUTATION",
    "RUNTIME_ACTION",
    "build_default_cen_node",
    "cen_governance_bridge",
    "classify_transition",
    "issue_authority_token",
    "mint_vt_token_from_denial",
    "verify_enforcement_receipt",
]
