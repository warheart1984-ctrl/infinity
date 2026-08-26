"""AMUL Service Bridge — Adaptive / Modular / Universal / Logical exchange membrane.

Mythic: the governed membrane between Jarvis and the outer world.
Engineering: CapabilityBridgeAmulMembrane

    Adaptive    normalizes any capability surface (local module, engine, lane)
                into Capability Contracts
    Modular     contract | adapter | constitutional gate | evidence | replay
    Universal   one invocation grammar:
                bind -> justify -> execute -> capture -> verify -> replay
    Logical     the Service Bridge Oath enforced in code, fail-closed.

Jarvis never calls a raw service. Jarvis invokes a governed capability and
receives {value, evidence, replay, constitutional_state} plus decision
support (accept | reject | escalate).

Honest maturity tags:
    contract derivation        - enforced (tests/test_capability_bridge_amul.py)
    constitutional gate        - enforced (authority, validation, evidence, replay)
    evidence envelope          - enforced (five required sections)
    replay chain               - enforced (sha-linked append-only packets)
    deterministic replay       - enforced for packets annotated deterministic
    non-deterministic replay   - annotated and refused (declared, not reproduced)
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

try:  # runtime package ships datetime_compat; tests may import standalone
    from src.datetime_compat import UTC  # type: ignore
except Exception:  # pragma: no cover - fallback for isolated use
    from datetime import timezone as UTC  # type: ignore

MEMBRANE_ID = "aais.capability_service_bridge.amul"
MEMBRANE_VERSION = "0.1-amul"
EVIDENCE_SECTIONS = (
    "request_snapshot",
    "response_snapshot",
    "timing",
    "constraints_applied",
    "verification_result",
)
REPLAY_FORMAT = "amul_replay_packet.v1"
GOVERNANCE_MODES = ("strict", "assist", "experimental")

# Mythic: the Service Bridge Oath — five laws of the membrane.
OATH_LAWS = (
    {
        "law": "oath_justification",
        "statement": "No capability without justification",
    },
    {
        "law": "oath_evidence",
        "statement": "No external action without evidence",
    },
    {
        "law": "oath_replay",
        "statement": "No evidence without replay",
    },
    {
        "law": "oath_audit",
        "statement": "No replay without audit",
    },
    {
        "law": "oath_continuity",
        "statement": "No audit without constitutional continuity",
    },
)


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _canonical_hash(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CapabilityContract:
    """What a capability claims it can do, and what proof it owes."""

    name: str
    action: str
    label: str = ""
    inputs: tuple[dict[str, Any], ...] = ()
    outputs: tuple[str, ...] = ()
    constraints: dict[str, Any] = field(default_factory=dict)
    evidence_required: tuple[str, ...] = EVIDENCE_SECTIONS
    replay_format: str = REPLAY_FORMAT

    @classmethod
    def from_route_spec(cls, spec: dict[str, Any]) -> "CapabilityContract":
        input_fields = tuple(
            {
                "id": str(item.get("id") or ""),
                "type": str(item.get("type") or "text"),
                "required": bool(item.get("required")),
            }
            for item in (spec.get("input_fields") or [])
            if isinstance(item, dict) and item.get("id")
        )
        return cls(
            name=str(spec.get("capability_id") or ""),
            action=str(spec.get("action") or ""),
            label=str(spec.get("tool_label") or spec.get("capability_label") or ""),
            inputs=input_fields,
            outputs=("response", "tool_result"),
            constraints={
                "governance_modes": list(
                    spec.get("governance_modes") or DEFAULT_GOVERNANCE_MODES_FALLBACK
                ),
                "default_governance_mode": str(
                    spec.get("default_governance_mode") or "strict"
                ),
                "provider_modes": list(spec.get("provider_modes") or ()),
                "endpoint": str(spec.get("endpoint") or ""),
            },
        )

    @property
    def route_key(self) -> tuple[str, str]:
        return (_normalize_key(self.name), _normalize_key(self.action))

    def required_input_ids(self) -> tuple[str, ...]:
        return tuple(
            str(item.get("id"))
            for item in self.inputs
            if isinstance(item, dict) and item.get("required")
        )


DEFAULT_GOVERNANCE_MODES_FALLBACK = ("strict", "assist", "experimental")


@dataclass(frozen=True)
class Justification:
    """Why Jarvis is invoking this capability at all."""

    intent: str
    rationale: str
    operator_id: str = "operator"
    session_id: str = ""
    degraded: bool = False

    def is_valid(self) -> bool:
        return bool(str(self.intent).strip()) and bool(str(self.rationale).strip())


def degraded_justification(capability: str, action: str) -> Justification:
    """Assist/experimental lanes may proceed with an explicitly degraded record."""
    return Justification(
        intent=f"operator_selection:{capability}.{action}",
        rationale=(
            "Auto-attested operator selection under non-strict governance mode; "
            "no explicit justification was supplied."
        ),
        degraded=True,
    )


@dataclass
class GateDecision:
    """One decision-chain record from the Constitutional Gate."""

    check: str
    allowed: bool
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"check": self.check, "allowed": self.allowed, "reason": self.reason}


class ConstitutionalGate:
    """Authority, validation, evidence completeness, replay integrity."""

    def check_authority(
        self,
        contract: CapabilityContract,
        justification: Justification | None,
        *,
        governance_mode: str,
    ) -> GateDecision:
        if governance_mode not in GOVERNANCE_MODES:
            return GateDecision("authority", False, f"unknown governance_mode: {governance_mode}")
        if justification is None or not justification.is_valid():
            if governance_mode == "strict":
                return GateDecision(
                    "authority",
                    False,
                    "oath_justification: no capability without justification",
                )
            return GateDecision(
                "authority",
                True,
                "degraded justification auto-attested under non-strict mode",
            )
        return GateDecision("authority", True, "justification accepted")

    def validate_arguments(self, contract: CapabilityContract, args: dict[str, Any]) -> GateDecision:
        missing = [
            input_id
            for input_id in contract.required_input_ids()
            if args.get(input_id) in (None, "")
        ]
        if missing:
            return GateDecision(
                "validation",
                False,
                f"missing required inputs per capability contract: {', '.join(missing)}",
            )
        return GateDecision("validation", True, "arguments satisfy capability contract")

    def check_evidence_completeness(self, evidence: dict[str, Any]) -> GateDecision:
        missing = [section for section in EVIDENCE_SECTIONS if not evidence.get(section)]
        if missing:
            return GateDecision(
                "evidence_completeness",
                False,
                f"evidence sections absent: {', '.join(missing)}",
            )
        return GateDecision("evidence_completeness", True, "all evidence sections present")

    def check_replay_integrity(self, replay_engine: "ReplayEngine") -> GateDecision:
        ok, bad_at = replay_engine.verify_chain()
        if not ok:
            return GateDecision(
                "replay_integrity",
                False,
                f"replay chain broken at sequence {bad_at}",
            )
        return GateDecision("replay_integrity", True, "replay chain intact")

    def evaluate(
        self,
        *,
        contract: CapabilityContract,
        justification: Justification | None,
        args: dict[str, Any],
        governance_mode: str,
        evidence: dict[str, Any] | None = None,
        replay_engine: "ReplayEngine | None" = None,
    ) -> list[GateDecision]:
        chain: list[GateDecision] = []
        chain.append(self.check_authority(contract, justification, governance_mode=governance_mode))
        if not chain[-1].allowed:
            return chain
        chain.append(self.validate_arguments(contract, args))
        if not chain[-1].allowed:
            return chain
        if evidence is not None:
            chain.append(self.check_evidence_completeness(evidence))
        if replay_engine is not None:
            chain.append(self.check_replay_integrity(replay_engine))
        return chain


class EvidenceEnvelope:
    """Every external interaction produces auditable evidence."""

    @staticmethod
    def build(
        *,
        request: dict[str, Any],
        response: dict[str, Any],
        started_utc: str,
        finished_utc: str,
        duration_ms: int,
        constraints_applied: dict[str, Any],
        verification_result: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "request_snapshot": copy.deepcopy(request or {}),
            "response_snapshot": copy.deepcopy(response or {}),
            "timing": {
                "started_utc": started_utc,
                "finished_utc": finished_utc,
                "duration_ms": duration_ms,
            },
            "constraints_applied": copy.deepcopy(constraints_applied or {}),
            "verification_result": copy.deepcopy(verification_result),
        }


class ReplayEngine:
    """Append-only sha-linked replay packets with constitutional audit trail."""

    def __init__(self) -> None:
        self._packets: list[dict[str, Any]] = []
        self._genesis_hash = _canonical_hash({"membrane": MEMBRANE_ID, "genesis": True})

    def record(
        self,
        *,
        capability: str,
        action: str,
        deterministic: bool,
        non_determinism_reason: str = "",
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        previous = self._packets[-1] if self._packets else None
        prev_hash = str(previous["packet_hash"]) if previous else self._genesis_hash
        core = {
            "sequence": len(self._packets) + 1,
            "capability": capability,
            "action": action,
            "deterministic": bool(deterministic),
            "non_determinism_reason": str(non_determinism_reason or ""),
            "recorded_at_utc": _utc_now_iso(),
            "payload": copy.deepcopy(payload or {}),
        }
        packet = {**core, "prev_hash": prev_hash}
        packet["packet_hash"] = _canonical_hash(packet)
        self._packets.append(packet)
        return dict(packet)

    def packets(self) -> list[dict[str, Any]]:
        return [dict(packet) for packet in self._packets]

    def verify_chain(self) -> tuple[bool, int | None]:
        expected_prev = self._genesis_hash
        for packet in self._packets:
            if packet.get("prev_hash") != expected_prev:
                return False, int(packet.get("sequence") or 0)
            core = {key: value for key, value in packet.items() if key != "packet_hash"}
            if _canonical_hash(core) != packet.get("packet_hash"):
                return False, int(packet.get("sequence") or 0)
            expected_prev = str(packet.get("packet_hash"))
        return True, None

    def state(self) -> dict[str, Any]:
        verified, bad_at = self.verify_chain()
        last = self._packets[-1] if self._packets else None
        return {
            "format": REPLAY_FORMAT,
            "packet_count": len(self._packets),
            "chain_intact": verified,
            "broken_at_sequence": bad_at,
            "head_hash": str(last["packet_hash"]) if last else self._genesis_hash,
        }

    def verify_response(self, sequence: int, response: Any) -> tuple[bool, str]:
        """Re-derive a packet's response digest and compare — deterministic replay check."""
        for packet in self._packets:
            if packet.get("sequence") != sequence:
                continue
            if not packet.get("deterministic"):
                reason = str(packet.get("non_determinism_reason") or "")
                return False, (
                    f"refused: non-deterministic packet ({reason})".strip()
                    or "refused: non-deterministic packet"
                )
            payload = packet.get("payload") or {}
            expected = str(payload.get("response_digest") or "")
            actual = _canonical_hash(self.__class__._digest_view(response))
            if not expected:
                return False, "packet carries no response digest"
            return actual == expected, "" if actual == expected else "response digest mismatch"
        return False, f"no replay packet at sequence {sequence}"

    @staticmethod
    def _digest_view(response: Any) -> dict[str, Any]:
        if isinstance(response, dict):
            summary = {
                "keys": sorted(str(key) for key in response.keys()),
                "ok": response.get("ok"),
                "status": response.get("status"),
                "provider": response.get("provider"),
                "model": response.get("model"),
            }
            tool_result = response.get("tool_result")
            if isinstance(tool_result, dict):
                summary["tool_status"] = tool_result.get("status")
            capability_meta = response.get("capability")
            if isinstance(capability_meta, dict):
                summary["bridge_ok"] = capability_meta.get("ok")
            return summary
        return {"kind": type(response).__name__}


def jarvis_decision(governed_result: dict[str, Any]) -> dict[str, Any]:
    """Reduce a governed result to accept | reject | escalate with a reason."""
    if not governed_result.get("ok"):
        return {
            "decision": "reject",
            "reason": str(governed_result.get("error") or "invocation failed"),
        }
    state = dict(governed_result.get("constitutional_state") or {})
    decisions = state.get("decision_chain") or []
    blocked = [d for d in decisions if isinstance(d, dict) and not d.get("allowed")]
    if blocked:
        return {
            "decision": "reject",
            "reason": str(blocked[0].get("reason") or "constitutional gate refused"),
        }
    verification = [d for d in decisions if isinstance(d, dict) and d.get("check") == "replay_integrity"]
    replay = dict(governed_result.get("replay") or {})
    if not replay.get("deterministic"):
        return {
            "decision": "escalate",
            "reason": str(
                replay.get("non_determinism_reason")
                or "non-deterministic capability requires operator review"
            ),
        }
    if verification and not verification[0].get("allowed"):
        return {"decision": "escalate", "reason": "replay integrity unverified"}
    return {"decision": "accept", "reason": "governed result verified end to end"}


class AmulMembrane:
    """The invocation grammar: bind → justify → execute → capture → verify → replay."""

    def __init__(self, *, replay_engine: ReplayEngine | None = None) -> None:
        self._contracts: dict[tuple[str, str], CapabilityContract] = {}
        self._gate = ConstitutionalGate()
        self.replay = replay_engine or ReplayEngine()

    # -- registry -----------------------------------------------------------

    def register_contract(self, contract: CapabilityContract) -> None:
        self._contracts[contract.route_key] = contract

    def contracts(self) -> dict[tuple[str, str], CapabilityContract]:
        return dict(self._contracts)

    def has_contract(self, capability: str, action: str) -> bool:
        return (_normalize_key(capability), _normalize_key(action)) in self._contracts

    def contract_for(self, capability: str, action: str) -> CapabilityContract:
        key = (_normalize_key(capability), _normalize_key(action))
        if key not in self._contracts:
            raise KeyError(f"unregistered capability contract: {capability}/{action}")
        return self._contracts[key]

    # -- invocation ---------------------------------------------------------

    def invoke(
        self,
        capability: str,
        action: str,
        args: dict[str, Any],
        *,
        executor: Callable[[dict[str, Any]], Any],
        justification: Justification | None = None,
        governance_mode: str = "strict",
        constraints: dict[str, Any] | None = None,
        deterministic_hint: bool | None = None,
    ) -> dict[str, Any]:
        started_utc = _utc_now_iso()
        started_perf = datetime.now(UTC).timestamp()
        try:
            contract = self.contract_for(capability, action)
        except KeyError as exc:
            return self._refused(str(exc), started_utc)

        effective_mode = governance_mode if governance_mode in GOVERNANCE_MODES else "strict"

        pre_chain = self._gate.evaluate(
            contract=contract,
            justification=justification,
            args=dict(args or {}),
            governance_mode=effective_mode,
        )
        if any(not decision.allowed for decision in pre_chain):
            finished = _utc_now_iso()
            duration_ms = max(0, round((datetime.now(UTC).timestamp() - started_perf) * 1000))
            evidence = EvidenceEnvelope.build(
                request={"args": copy.deepcopy(args or {}), "justification_supplied": justification is not None},
                response={"blocked": True},
                started_utc=started_utc,
                finished_utc=finished,
                duration_ms=duration_ms,
                constraints_applied={
                    **(constraints or {}),
                    "governance_mode": effective_mode,
                    "membrane_version": MEMBRANE_VERSION,
                },
                verification_result=[d.as_dict() for d in pre_chain],
            )
            packet = self.replay.record(
                capability=contract.name,
                action=contract.action,
                deterministic=True,
                payload={"outcome": "blocked", "decision_chain": [d.as_dict() for d in pre_chain]},
            )
            result = {
                "ok": False,
                "error": next((d.reason for d in pre_chain if not d.allowed), "blocked"),
                "value": None,
                "evidence": evidence,
                "replay": self._replay_view(packet),
                "constitutional_state": {
                    "membrane_id": MEMBRANE_ID,
                    "membrane_version": MEMBRANE_VERSION,
                    "decision_chain": [d.as_dict() for d in pre_chain],
                    "continuity": {"sequence": packet["sequence"], "head_hash": packet["packet_hash"]},
                },
            }
            result["decision_support"] = jarvis_decision(result)
            return result

        effective_justification = justification
        if effective_justification is None:
            effective_justification = degraded_justification(contract.name, contract.action)

        # Mythic: the adapter speaks to the outer world so Jarvis never has to.
        try:
            value = executor(dict(args or {}))
            execute_error = None
        except Exception as exc:  # fail-closed capture of adapter failures
            value = None
            execute_error = f"{type(exc).__name__}: {exc}"

        finished_utc = _utc_now_iso()
        duration_ms = max(0, round((datetime.now(UTC).timestamp() - started_perf) * 1000))

        post_chain = self._gate.evaluate(
            contract=contract,
            justification=effective_justification,
            args=dict(args or {}),
            governance_mode=effective_mode,
            evidence=None,
            replay_engine=self.replay,
        )
        response_snapshot = (
            {"error": execute_error} if execute_error else self._summarize(value)
        )
        pre_evidence = EvidenceEnvelope.build(
            request={
                "args": copy.deepcopy(args or {}),
                "intent": effective_justification.intent,
                "rationale": effective_justification.rationale,
                "operator_id": effective_justification.operator_id,
                "session_id": effective_justification.session_id,
                "justification_degraded": effective_justification.degraded,
            },
            response=response_snapshot,
            started_utc=started_utc,
            finished_utc=finished_utc,
            duration_ms=duration_ms,
            constraints_applied={
                **(constraints or {}),
                "governance_mode": effective_mode,
                "contract_constraints": copy.deepcopy(contract.constraints),
                "membrane_version": MEMBRANE_VERSION,
            },
            verification_result=[d.as_dict() for d in post_chain],
        )
        final_chain = self._gate.evaluate(
            contract=contract,
            justification=effective_justification,
            args=dict(args or {}),
            governance_mode=effective_mode,
            evidence=pre_evidence,
            replay_engine=self.replay,
        )
        evidence = dict(pre_evidence)
        evidence["verification_result"] = [d.as_dict() for d in post_chain + final_chain]

        deterministic = deterministic_hint
        non_det_reason = ""
        if deterministic is None:
            provider_touched = bool((response_snapshot or {}).get("provider"))
            deterministic = not provider_touched
            non_det_reason = "provider-backed capability output" if provider_touched else ""
        elif not deterministic:
            non_det_reason = "declared non-deterministic by pipeline adapter classification"

        packet = self.replay.record(
            capability=contract.name,
            action=contract.action,
            deterministic=bool(deterministic),
            non_determinism_reason=non_det_reason,
            payload={
                "outcome": "error" if execute_error else "completed",
                "request_args": copy.deepcopy(args or {}),
                "response_digest": _canonical_hash(response_snapshot),
            },
        )

        ok = execute_error is None and all(d.allowed for d in final_chain)
        result = {
            "ok": ok,
            "error": execute_error,
            "value": value,
            "evidence": evidence,
            "replay": self._replay_view(packet),
            "constitutional_state": {
                "membrane_id": MEMBRANE_ID,
                "membrane_version": MEMBRANE_VERSION,
                "decision_chain": [d.as_dict() for d in post_chain + final_chain],
                "continuity": {
                    "sequence": packet["sequence"],
                    "prev_hash": packet["prev_hash"],
                    "head_hash": packet["packet_hash"],
                },
            },
        }
        result["decision_support"] = jarvis_decision(result)
        return result

    # -- helpers ------------------------------------------------------------

    def _refused(self, error: str, started_utc: str) -> dict[str, Any]:
        refusal_chain = [{"check": "bind", "allowed": False, "reason": error}]
        evidence = EvidenceEnvelope.build(
            request={},
            response={"blocked": True},
            started_utc=started_utc,
            finished_utc=_utc_now_iso(),
            duration_ms=0,
            constraints_applied={"membrane_version": MEMBRANE_VERSION},
            verification_result=list(refusal_chain),
        )
        result = {
            "ok": False,
            "error": error,
            "value": None,
            "evidence": evidence,
            "replay": None,
            "constitutional_state": {
                "membrane_id": MEMBRANE_ID,
                "membrane_version": MEMBRANE_VERSION,
                "decision_chain": refusal_chain,
                "continuity": None,
            },
        }
        result["decision_support"] = jarvis_decision(result)
        return result

    @staticmethod
    def _summarize(value: Any) -> dict[str, Any]:
        return ReplayEngine._digest_view(value)

    @staticmethod
    def _replay_view(packet: dict[str, Any]) -> dict[str, Any]:
        return {
            "format": REPLAY_FORMAT,
            "sequence": packet["sequence"],
            "packet_hash": packet["packet_hash"],
            "prev_hash": packet["prev_hash"],
            "deterministic": packet["deterministic"],
            "non_determinism_reason": packet["non_determinism_reason"],
            "recorded_at_utc": packet["recorded_at_utc"],
        }


def _normalize_key(value: str) -> str:
    return str(value or "").strip().lower()
