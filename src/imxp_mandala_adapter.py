"""IMXP Mandala adapter — wraps mandala-link/1 packets into governance membrane events.

Mythic: the membrane breathes through every wire.
Engineering: ImxpMandalaAdapter maps mandala-link packets to membrane drift events
(MGM-0), consults adopted policies for admission (MGM-3, never bypassing
OTEM/UGR/mesh execution), and converts mandala capability grants into
operator_membrane_policy.v1 candidates (MGM-1) for the dual-gate adoption flow.

Packet fields accept both wire-spec snake_case (MANDALA_LINK_PROTOCOL.md) and
TypeScript-reference camelCase (mandala-link.ts). Canonical hashing matches
src/organism_receipt.py canonical_json so receipts stay byte-compatible.
"""

from __future__ import annotations

import hashlib
from typing import Any

from src.multi_organism_governance_membrane_registry import POLICY_VERSION

IMXP_MANDALA_ADAPTER_VERSION = "imxp_mandala_adapter.v1"
MANDALA_PROTOCOL = "mandala-link/1"

DRIFT_SOURCE = "mandala_link"
ADAPTER_DIALECT = "mandala-link"

PACKET_TYPES = (
    "image", "audio", "text", "video", "sensor",
    "scene", "render", "command", "response", "control",
)

CONTROL_SUBTYPES = frozenset({
    "pair_request", "pair_confirm", "pair_reject",
    "grant_create", "grant_revoke", "grant_update",
    "fetch", "chunk", "chunk_ack",
    "ping", "pong",
    "goodbye", "error",
    "discovery_advert", "discovery_response",
})

# mandala packet type -> membrane permeability channel
MANDALA_TYPE_TO_CHANNEL = {
    "image": "mesh_handoff",
    "audio": "mesh_handoff",
    "video": "mesh_handoff",
    "scene": "mesh_handoff",
    "render": "mesh_handoff",
    "text": "exchange_envelope",
    "command": "exchange_envelope",
    "response": "exchange_envelope",
    "control": "exchange_envelope",
    "sensor": "memory_cues",
}

# membrane permeability channel -> operator_membrane_policy.v1 policy_kind
CHANNEL_TO_POLICY_KIND = {
    "memory_cues": "memory_permeability",
    "exchange_envelope": "exchange_permeability",
    "mesh_handoff": "mesh_permeability",
    "ledger_federation": "ledger_permeability",
}


def _field(packet: dict[str, Any], snake: str, *camel: str) -> Any:
    if snake in packet:
        return packet.get(snake)
    for name in camel:
        if name in packet:
            return packet.get(name)
    return None


def normalize_packet(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a mandala packet (snake_case or camelCase) to canonical snake_case."""
    if not isinstance(raw, dict):
        return {}
    recipient = _field(raw, "recipient")
    return {
        "protocol": raw.get("protocol"),
        "version": raw.get("version"),
        "packet_id": _field(raw, "packet_id", "packetId"),
        "sender": raw.get("sender"),
        "recipient": recipient or "",
        "type": raw.get("type"),
        "subtype": raw.get("subtype"),
        "hop_limit": _field(raw, "hop_limit", "hopLimit"),
        "path": raw.get("path") or [],
        "timestamp": raw.get("timestamp"),
        "payload_hash": _field(raw, "payload_hash", "payloadHash"),
        "payload": raw.get("payload"),
        "signature": raw.get("signature"),
        "capability_ticket": _field(raw, "capability_ticket", "capabilityTicket"),
        "encryption": raw.get("encryption"),
    }


def canonical_json(value: Any) -> str:
    """Sorted-key compact JSON — mirrors src/organism_receipt.py."""
    try:
        from src.organism_receipt import canonical_json as receipt_canonical

        return receipt_canonical(value)
    except Exception:
        import json

        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_payload_hash(payload: Any) -> str:
    digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def verify_payload_hash(packet: dict[str, Any]) -> bool:
    declared = str(packet.get("payload_hash") or "")
    if not declared:
        return False
    if "payload" not in packet or packet.get("payload") is None:
        return True  # large payload omitted; FETCH flow verifies out of band
    return declared == compute_payload_hash(packet.get("payload"))


def validate_mandala_packet(packet: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    normalized = normalize_packet(packet)
    if normalized.get("protocol") != MANDALA_PROTOCOL:
        errors.append(f"protocol must be {MANDALA_PROTOCOL}")
    if normalized.get("version") != 1:
        errors.append("version must be 1")
    for field in ("packet_id", "sender", "type", "timestamp", "payload_hash", "signature"):
        if not normalized.get(field):
            errors.append(f"missing {field}")
    if not isinstance(normalized.get("hop_limit"), int):
        errors.append("hop_limit must be integer")
    if not isinstance(normalized.get("path"), list):
        errors.append("path must be a list")
    ptype = str(normalized.get("type") or "")
    if ptype and ptype not in PACKET_TYPES:
        errors.append(f"unknown type: {ptype}")
    if ptype == "control":
        subtype = str(normalized.get("subtype") or "")
        if subtype and subtype not in CONTROL_SUBTYPES:
            errors.append(f"unknown control subtype: {subtype}")
    if not verify_payload_hash(normalized):
        errors.append("payload_hash mismatch")
    return (len(errors) == 0), errors


def packet_channel(packet_type: str) -> str:
    return MANDALA_TYPE_TO_CHANNEL.get(str(packet_type or "").lower(), "exchange_envelope")


class ImxpMandalaAdapter:
    """Thin wrapper between mandala-link traffic and the governance membrane."""

    def __init__(self, runtime: Any | None = None):
        if runtime is None:
            from src.multi_organism_governance_membrane_runtime import (
                multi_organism_governance_membrane_runtime,
            )

            runtime = multi_organism_governance_membrane_runtime
        self._runtime = runtime

    # ------------------------------------------------------------------ MGM-3

    def admit_packet(self, packet: dict[str, Any], *, session_id: str | None = None) -> dict[str, Any]:
        """MGM-3 admission-only consult. Execution stays behind OTEM/UGR/mesh gates."""
        valid, errors = validate_mandala_packet(packet)
        event = self.packet_to_membrane_event(packet, validation_errors=errors)
        if not valid:
            return {
                "outcome": "blocked",
                "adapter_version": IMXP_MANDALA_ADAPTER_VERSION,
                "reason": "invalid_packet",
                "errors": errors,
                "drift_event": event,
            }
        normalized = normalize_packet(packet)
        envelope = {
            "consent_id": normalized.get("capability_ticket"),
            "channel": packet_channel(str(normalized.get("type"))),
            "sender": normalized.get("sender"),
            "packet_id": normalized.get("packet_id"),
            "signature": normalized.get("signature"),
        }
        permeability = self._runtime.check_exchange_permeability(envelope)
        result: dict[str, Any] = {
            "outcome": "admitted" if permeability.get("allowed") else "blocked",
            "adapter_version": IMXP_MANDALA_ADAPTER_VERSION,
            "mgm_class": "MGM-3",
            "channel": envelope["channel"],
            "permeability": permeability,
            "drift_event": event,
            "claim_label": "asserted",
        }
        if session_id and hasattr(self._runtime, "_emit_membrane_drift_ledger"):
            try:
                self._runtime._emit_membrane_drift_ledger(session_id, event)
            except Exception:
                pass
        return result

    def packet_to_membrane_event(
        self, packet: dict[str, Any], *, validation_errors: list[str] | None = None
    ) -> dict[str, Any]:
        """Shape a mandala packet as a membrane_drift.v1 event (MGM-0 observation)."""
        normalized = normalize_packet(packet)
        severity = "nominal" if not validation_errors else "attention"
        summary = (
            f"mandala {normalized.get('type')} packet via {packet_channel(str(normalized.get('type')))}"
        )
        if validation_errors:
            summary = f"invalid mandala packet: {'; '.join(validation_errors[:3])}"
        try:
            event = self._runtime._drift_event(
                severity=severity, source=DRIFT_SOURCE, summary=summary
            )
        except Exception:
            from uuid import uuid4

            from src.multi_organism_governance_membrane_runtime import DRIFT_VERSION, _utc_now_iso

            event = {
                "drift_version": DRIFT_VERSION,
                "drift_id": f"mdrift_{uuid4().hex[:12]}",
                "severity": severity,
                "source": DRIFT_SOURCE,
                "summary": summary,
                "mgm_class": "MGM-0",
                "observed_at": _utc_now_iso(),
            }
        event["mandala_packet_id"] = normalized.get("packet_id")
        event["mandala_sender"] = normalized.get("sender")
        event["capability_ticket"] = normalized.get("capability_ticket")
        return event

    # ------------------------------------------------------------------ MGM-1

    def grant_to_policy_candidate(self, grant: dict[str, Any]) -> dict[str, Any]:
        """Convert a mandala CapabilityGrant into an operator_membrane_policy.v1 candidate."""
        if not isinstance(grant, dict) or grant.get("revoked"):
            return {"outcome": "blocked", "reason": "grant_revoked_or_invalid"}
        peer_id = str(_field(grant, "peer_id", "peerId") or "")
        grant_id = str(_field(grant, "grant_id", "grantId") or "")
        if not peer_id or not grant_id:
            return {"outcome": "blocked", "reason": "grant_missing_peer_or_id"}

        capabilities = list(grant.get("capabilities") or [])
        constraints_override = dict(_field(grant, "constraints_override", "constraintsOverride") or {})
        if not capabilities:
            single_type = _field(grant, "capability_type", "capabilityType") or _field(grant, "type", "capabilityId")
            capabilities = [{"type": single_type}]

        channels: list[str] = []
        require_confirmation = bool(constraints_override.get("require_confirmation") or constraints_override.get("requireConfirmation"))
        for cap in capabilities:
            if not isinstance(cap, dict):
                continue
            cap_constraints = dict(cap.get("constraints") or {})
            if cap_constraints.get("requireConfirmation"):
                require_confirmation = True
            channel = packet_channel(str(cap.get("type")))
            if channel not in channels:
                channels.append(channel)

        if len(channels) == 1:
            policy_kind = CHANNEL_TO_POLICY_KIND.get(channels[0], "composite")
        else:
            policy_kind = "composite"

        consent_requirements: dict[str, Any] = {"dual_consent": require_confirmation}
        expires_at = _field(grant, "expires_at", "expiresAt")
        if expires_at is not None:
            consent_requirements["expires_at_unix"] = expires_at
            consent_requirements["auto_expire"] = True

        candidate = {
            "policy_version": POLICY_VERSION,
            "policy_kind": policy_kind,
            "summary": (
                f"Mandala capability grant {grant_id[:12]} for peer {peer_id[:16]} "
                f"over {', '.join(channels)}"
            ),
            "charter_ref": {"source": ADAPTER_DIALECT, "peer_id": peer_id},
            "permitted_channels": channels,
            "consent_requirements": consent_requirements,
            "evidence_refs": [f"mandala_grant:{grant_id}", f"mandala_peer:{peer_id}"],
            "stability_score": self._stability_score(grant),
            "mgm_class": "MGM-1",
            "mandala_grant": {
                "grant_id": grant_id,
                "peer_id": peer_id,
                "context_profile": _field(grant, "context_profile", "contextProfile"),
                "granted_by": _field(grant, "granted_by", "grantedBy"),
                "dialect": ADAPTER_DIALECT,
            },
        }
        builder = getattr(self._runtime, "_build_candidate", None)
        if callable(builder):
            merged = builder(
                summary=candidate["summary"],
                policy_kind=policy_kind,
                charter_ref=candidate["charter_ref"],
                permitted_channels=channels,
                consent_requirements=consent_requirements,
                stability_score=candidate["stability_score"],
            )
            # Deterministic id: the same grant must yield the same candidate,
            # so operator-minted VT tokens bind across proposal and adoption.
            merged["candidate_id"] = (
                f"pcand_mandala_{hashlib.sha256(grant_id.encode()).hexdigest()[:12]}"
            )
            merged["evidence_refs"] = candidate["evidence_refs"]
            merged["mandala_grant"] = candidate["mandala_grant"]
            return merged
        candidate["candidate_id"] = f"pcand_mandala_{hashlib.sha256(grant_id.encode()).hexdigest()[:12]}"
        candidate["claim_label"] = "asserted"
        candidate["operator_promoted"] = False
        return candidate

    def propose_policy_from_grant(
        self,
        grant: dict[str, Any],
        *,
        operator_approved: bool = False,
        jarvis_authorization: dict[str, Any] | None = None,
        session_id: str = "global",
        authority_token: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Full dual-gate path: grant -> candidate -> adopt_membrane_policy."""
        candidate = self.grant_to_policy_candidate(grant)
        if candidate.get("outcome") == "blocked":
            return candidate
        persist = getattr(self._runtime, "_persist_candidate", None)
        if callable(persist):
            try:
                persist(candidate)
            except Exception:
                pass
        auth = dict(jarvis_authorization or {})
        if not (operator_approved and auth.get("authorized")):
            # MGM-1 proposal only — dual gate stays closed until both consents arrive.
            return {"outcome": "proposed", "candidate": candidate, "mgm_class": "MGM-1"}
        adopt = getattr(self._runtime, "adopt_membrane_policy", None)
        if not callable(adopt):
            return {"outcome": "proposed", "candidate": candidate}
        return adopt(
            candidate,
            operator_approved=operator_approved,
            jarvis_authorization=jarvis_authorization,
            session_id=session_id,
            authority_token=authority_token,
        )

    @staticmethod
    def _stability_score(grant: dict[str, Any]) -> float:
        score = 0.6
        granted_by = str(_field(grant, "granted_by", "grantedBy") or "").lower()
        if granted_by == "human":
            score += 0.2
        pairing = str(grant.get("pairing_method") or grant.get("pairingMethod") or "").lower()
        if pairing in {"qr", "nfc", "pre-shared"}:
            score += 0.1
        trust = str(grant.get("trust_level") or grant.get("trustLevel") or "").lower()
        if trust == "full":
            score += 0.1
        return round(min(score, 1.0), 2)


imxp_mandala_adapter = ImxpMandalaAdapter()
