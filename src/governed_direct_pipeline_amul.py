"""AMUL Governed Direct Pipeline — the constitutional execution artery.

Mythic: the governed path of action between Jarvis and the world.
Engineering: GovernedDirectPipelineAmul

Not a workflow. Not an API chain. A governed path:

    Jarvis -> Intent Gate          -> Intent Record (IR)
           -> Constitutional Gate  -> Governance Record (GR)
           -> Capability Bridge    -> Capability Execution Record (CER)
           -> Evidence Engine      -> Evidence Packet (EP)
           -> Replay Engine        -> Replay Packet (RP)
           -> Audit Spine          -> Constitutional State Record (CSR)
           -> Jarvis decides       -> accept | reject | escalate

Laws enforced in code, fail-closed:
    no intent without authority
    no capability without validation
    no execution without evidence
    no evidence without replay
    no replay without audit
    no audit without constitutional continuity

Honest maturity tags:
    intent classification      - heuristic (declared; keyword rules, enforced tests)
    constitutional gate        - enforced (authority, validation, CCC continuity)
    capability bridge          - delegates to the Service Bridge AMUL membrane
    evidence engine            - enforced (five sections, inherited from membrane)
    replay engine              - enforced (sha-linked packets, inherited from membrane)
    audit spine                - enforced (append-only hash-linked records)
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

try:
    from src.datetime_compat import UTC  # type: ignore
except Exception:  # pragma: no cover - isolated use fallback
    from datetime import timezone as UTC  # type: ignore

from src.capability_service_bridge_amul import (
    AmulMembrane,
    CapabilityContract,
    Justification,
    _canonical_hash,
    degraded_justification,
    jarvis_decision,
)

PIPELINE_AMUL_ID = "aais.governed_direct_pipeline.amul"
PIPELINE_AMUL_VERSION = "0.1-amul"

INTENT_KINDS = ("query", "capability", "action", "constitutional_decision")
ADAPTER_KINDS = ("local", "provider")

_QUERY_MARKERS = ("?", "what ", "why ", "how ", "when ", "who ", "where ", "which ")
_DECISION_PREFIXES = ("decision:", "constitutional:", "ruling:")
_ACTION_PREFIXES = ("action:", "do:", "run:")
_CAPABILITY_PREFIXES = ("capability:", "invoke:")


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _now_ts() -> float:
    return datetime.now(UTC).timestamp()


# ---------------------------------------------------------------------------
# Stage 1 — Intent Gate (IG)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IntentRecord:
    """IR — what Jarvis asked for, classified under declared heuristics."""

    record_id: str
    kind: str
    text: str
    emitted_by: str
    classified_at_utc: str
    classification_note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "kind": self.kind,
            "text": self.text[:400],
            "emitted_by": self.emitted_by,
            "classified_at_utc": self.classified_at_utc,
            "classification_note": self.classification_note,
        }


class IntentGate:
    """Classify Jarvis intent into query | capability | action | constitutional_decision."""

    def __init__(self) -> None:
        self._counter = 0

    def classify(self, text: Any, *, emitted_by: str = "jarvis") -> IntentRecord:
        self._counter += 1
        clean = str(text or "").strip()
        lowered = clean.lower()
        if not lowered:
            return IntentRecord(
                record_id=f"ir-{self._counter}",
                kind="",
                text="",
                emitted_by=emitted_by,
                classified_at_utc=_utc_now_iso(),
                classification_note="empty intent — authority cannot attach",
            )
        kind = ""
        note = "heuristic keyword classification"
        if lowered.startswith(_DECISION_PREFIXES):
            kind = "constitutional_decision"
        elif lowered.startswith(_CAPABILITY_PREFIXES):
            kind = "capability"
        elif lowered.startswith(_ACTION_PREFIXES):
            kind = "action"
        elif any(marker in lowered for marker in _QUERY_MARKERS):
            kind = "query"
        else:
            kind = "action"
            note = "heuristic fallback: imperative form assumed"
        return IntentRecord(
            record_id=f"ir-{self._counter}",
            kind=kind,
            text=clean,
            emitted_by=emitted_by,
            classified_at_utc=_utc_now_iso(),
            classification_note=note,
        )


# ---------------------------------------------------------------------------
# Governed Capability Units (GCU) — adaptive normalization of any surface
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GovernedCapabilityUnit:
    name: str
    action: str
    adapter_kind: str
    contract: CapabilityContract

    @property
    def route_key(self) -> tuple[str, str]:
        return (str(self.name).strip().lower(), str(self.action).strip().lower())


def gcu_from_contract(contract: CapabilityContract) -> GovernedCapabilityUnit:
    provider_modes = tuple(contract.constraints.get("provider_modes") or ())
    adapter_kind = "local" if provider_modes == ("deterministic",) else "provider"
    return GovernedCapabilityUnit(
        name=contract.name,
        action=contract.action,
        adapter_kind=adapter_kind,
        contract=contract,
    )


# ---------------------------------------------------------------------------
# Stage 2 — Constitutional Gate (CG)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GovernanceRecord:
    """GR — the constitutional verdict that must exist before execution."""

    record_id: str
    ok: bool
    reason: str
    authority_chain: tuple[dict[str, Any], ...] = ()
    validation_chain: tuple[dict[str, Any], ...] = ()
    risk_constraints: dict[str, Any] = field(default_factory=dict)
    continuity_check: dict[str, Any] = field(default_factory=dict)
    inference_contract: dict[str, Any] = field(default_factory=dict)
    produced_at_utc: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "ok": self.ok,
            "reason": self.reason,
            "authority_chain": list(self.authority_chain),
            "validation_chain": list(self.validation_chain),
            "risk_constraints": copy.deepcopy(self.risk_constraints),
            "continuity_check": copy.deepcopy(self.continuity_check),
            "inference_contract": copy.deepcopy(self.inference_contract),
            "produced_at_utc": self.produced_at_utc,
        }


class PipelineConstitutionalGate:
    """Authority chain, validation chain, risk constraints, CCC, CIC."""

    def __init__(self) -> None:
        self._counter = 0

    def evaluate(
        self,
        *,
        gcu: GovernedCapabilityUnit,
        justification: Justification | None,
        args: dict[str, Any],
        governance_mode: str,
        continuity: dict[str, Any],
        inference_contract: dict[str, Any] | None,
        risk_constraints: dict[str, Any] | None,
    ) -> GovernanceRecord:
        self._counter += 1
        record_id = f"gr-{self._counter}"
        stamp = _utc_now_iso()

        def decision(ok: bool, reason: str, authority: list, validation: list) -> GovernanceRecord:
            return GovernanceRecord(
                record_id=record_id,
                ok=ok,
                reason=reason,
                authority_chain=tuple(authority),
                validation_chain=tuple(validation),
                risk_constraints=copy.deepcopy(risk_constraints or {}),
                continuity_check=copy.deepcopy(continuity or {}),
                inference_contract=copy.deepcopy(inference_contract or {}),
                produced_at_utc=stamp,
            )

        authority: list[dict[str, Any]] = []
        validation: list[dict[str, Any]] = []

        if governance_mode not in ("strict", "assist", "experimental"):
            authority.append({"check": "mode", "allowed": False, "reason": f"unknown governance_mode: {governance_mode}"})
            return decision(False, "no intent without authority", authority, validation)

        if justification is None or not justification.is_valid():
            if governance_mode == "strict":
                authority.append({
                    "check": "justification",
                    "allowed": False,
                    "reason": "no capability without justification",
                })
                return decision(False, "no intent without authority", authority, validation)
            authority.append({
                "check": "justification",
                "allowed": True,
                "reason": "degraded justification auto-attested (non-strict)",
            })
        else:
            authority.append({"check": "justification", "allowed": True, "reason": "justification accepted"})

        if not continuity.get("intact"):
            authority.append({
                "check": "ccc_continuity",
                "allowed": False,
                "reason": f"constitutional continuity broken: {continuity.get('detail')}",
            })
            return decision(False, "no audit without constitutional continuity", authority, validation)

        missing = [
            str(item.get("id"))
            for item in gcu.contract.inputs
            if isinstance(item, dict) and item.get("required") and args.get(item.get("id")) in (None, "")
        ]
        if missing:
            validation.append({
                "check": "contract_inputs",
                "allowed": False,
                "reason": f"missing required inputs per capability contract: {', '.join(missing)}",
            })
            return decision(False, "no capability without validation", authority, validation)
        validation.append({"check": "contract_inputs", "allowed": True, "reason": "arguments satisfy GCU contract"})

        return decision(True, "governance approved", authority, validation)


# ---------------------------------------------------------------------------
# Stages 3–6 records
# ---------------------------------------------------------------------------


def capability_execution_record(membrane_result: dict[str, Any]) -> dict[str, Any]:
    """CER — distilled view of the Service Bridge membrane invocation."""
    return {
        "ok": bool(membrane_result.get("ok")),
        "error": membrane_result.get("error"),
        "has_value": membrane_result.get("value") is not None,
        "response_view": (
            membrane_result["evidence"]["response_snapshot"]
            if isinstance(membrane_result.get("evidence"), dict)
            else {}
        ),
        "decision_support": copy.deepcopy(membrane_result.get("decision_support")),
    }


class AuditSpine:
    """AS — append-only hash-linked store; every entry chained to the last."""

    def __init__(self) -> None:
        self._entries: list[dict[str, Any]] = []
        self._genesis = _canonical_hash({"spine": PIPELINE_AMUL_ID, "genesis": True})

    def append(self, *, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        previous = self._entries[-1] if self._entries else None
        prev_hash = str(previous["hash"]) if previous else self._genesis
        core = {
            "sequence": len(self._entries) + 1,
            "kind": kind,
            "payload_digest": _canonical_hash(payload),
            "recorded_at_utc": _utc_now_iso(),
        }
        entry = {**core, "prev_hash": prev_hash}
        entry["hash"] = _canonical_hash(entry)
        self._entries.append(entry)
        return dict(entry)

    def entries(self) -> list[dict[str, Any]]:
        return [dict(entry) for entry in self._entries]

    def verify(self) -> tuple[bool, int | None]:
        expected_prev = self._genesis
        for entry in self._entries:
            if entry.get("prev_hash") != expected_prev:
                return False, int(entry.get("sequence") or 0)
            core = {key: value for key, value in entry.items() if key != "hash"}
            if _canonical_hash(core) != entry.get("hash"):
                return False, int(entry.get("sequence") or 0)
            expected_prev = str(entry.get("hash"))
        return True, None

    def csr(self, *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        """Produce the Constitutional State Record for the current spine state."""
        intact, broken_at = self.verify()
        head = self._entries[-1] if self._entries else None
        record = {
            "csr_version": "amul_csr.v1",
            "pipeline_id": PIPELINE_AMUL_ID,
            "pipeline_version": PIPELINE_AMUL_VERSION,
            "entry_count": len(self._entries),
            "kinds_index": [entry["kind"] for entry in self._entries],
            "head_hash": str(head["hash"]) if head else self._genesis,
            "continuity_intact": intact,
            "broken_at_sequence": broken_at,
        }
        if extra:
            record.update(copy.deepcopy(extra))
        return record


# ---------------------------------------------------------------------------
# Orchestrator — the governed direct path
# ---------------------------------------------------------------------------


class GovernedDirectPipelineAmul:
    """intent -> authority -> validation -> capability -> evidence -> replay -> audit."""

    def __init__(
        self,
        *,
        membrane: AmulMembrane | None = None,
        spine: AuditSpine | None = None,
        bridge: Any = None,
    ) -> None:
        self.membrane = membrane or AmulMembrane()
        self.spine = spine or AuditSpine()
        self.intent_gate = IntentGate()
        self.constitutional_gate = PipelineConstitutionalGate()
        self.bridge = bridge

    # -- GCU registry --------------------------------------------------------

    def register_gcu_from_contract(self, contract: CapabilityContract) -> GovernedCapabilityUnit:
        gcu = gcu_from_contract(contract)
        self.membrane.register_contract(contract)
        return gcu

    def register_gcus_from_membrane(self, membrane: AmulMembrane) -> int:
        count = 0
        for contract in membrane.contracts().values():
            self.register_gcu_from_contract(contract)
            count += 1
        return count

    def resolve_gcu(self, capability: str, action: str) -> GovernedCapabilityUnit | None:
        key = (str(capability).strip().lower(), str(action).strip().lower())
        contract = self.membrane.contracts().get(key)
        return gcu_from_contract(contract) if contract else None

    def gcus(self) -> list[GovernedCapabilityUnit]:
        return [gcu_from_contract(c) for c in self.membrane.contracts().values()]

    # -- the governed run ------------------------------------------------------

    def run(
        self,
        *,
        intent_text: Any,
        capability: str,
        action: str,
        args: dict[str, Any] | None = None,
        justification: Justification | None = None,
        governance_mode: str = "strict",
        executor: Callable[[dict[str, Any]], Any] | None = None,
        inference_contract: dict[str, Any] | None = None,
        risk_constraints: dict[str, Any] | None = None,
        emitted_by: str = "jarvis",
    ) -> dict[str, Any]:
        started_utc = _utc_now_iso()
        started_perf = _now_ts()
        run_args = dict(args or {})
        effective_mode = governance_mode if governance_mode in ("strict", "assist", "experimental") else "strict"

        def finish(result: dict[str, Any]) -> dict[str, Any]:
            result.setdefault("decision_support", jarvis_decision(result))
            return result

        # Stage 1 — Intent Gate
        ir = self.intent_gate.classify(intent_text, emitted_by=emitted_by)
        if not ir.kind:
            return finish(self._refused(ir, None, "no intent without authority: empty intent"))

        # Stage 2 — Constitutional Gate (bind first: capability identity is needed)
        gcu = self.resolve_gcu(capability, action)
        if gcu is None:
            return finish(self._refused(ir, None, f"unregistered capability unit: {capability}/{action}"))

        continuity = {"intact": True, "detail": ""}
        intact, broken_at = self.spine.verify()
        if not intact:
            continuity = {"intact": False, "detail": f"audit spine broken at sequence {broken_at}"}

        gr = self.constitutional_gate.evaluate(
            gcu=gcu,
            justification=justification,
            args=run_args,
            governance_mode=effective_mode,
            continuity=continuity,
            inference_contract=inference_contract,
            risk_constraints=risk_constraints,
        )
        self.spine.append(kind="IR", payload=ir.as_dict())
        if not gr.ok:
            self.spine.append(kind="GR_REFUSED", payload=gr.as_dict())
            return finish(
                self._refused(
                    ir,
                    gr,
                    f"{gr.reason}: {next((c['reason'] for c in (*gr.authority_chain, *gr.validation_chain) if not c['allowed']), '')}",
                )
            )
        self.spine.append(kind="GR", payload=gr.as_dict())

        # Stage 3 — Capability Bridge (the Service Bridge membrane speaks here)
        effective_justification = justification
        if effective_justification is None:
            effective_justification = degraded_justification(gcu.name, gcu.action)
        try:
            membrane_result = self.membrane.invoke(
                gcu.name,
                gcu.action,
                run_args,
                executor=self._resolve_executor(executor, gcu.name, gcu.action),
                justification=effective_justification,
                governance_mode=effective_mode,
                constraints={
                    "pipeline_id": PIPELINE_AMUL_ID,
                    "intent_id": ir.record_id,
                    "governance_record": gr.record_id,
                    "risk_constraints": copy.deepcopy(risk_constraints or {}),
                },
                deterministic_hint=(gcu.adapter_kind == "local"),
            )
        except Exception as exc:  # membrane itself failed — capture fail-closed
            membrane_result = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "value": None}
        cer = capability_execution_record(membrane_result)
        self.spine.append(kind="CER", payload=cer)

        # Stage 4 — Evidence Engine (packet inherited from the membrane)
        ep = dict(membrane_result.get("evidence") or {})
        ep.setdefault("annotations", {})
        ep["annotations"].update(
            {
                "pipeline_id": PIPELINE_AMUL_ID,
                "pipeline_version": PIPELINE_AMUL_VERSION,
                "intent_record": ir.record_id,
                "governance_record": gr.record_id,
            }
        )

        # Stage 5 — Replay Engine (packet inherited from the membrane)
        rp = copy.deepcopy(membrane_result.get("replay"))

        # Laws 3–5: execution implies evidence implies replay
        if membrane_result.get("ok"):
            missing_sections = [
                section
                for section in ("request_snapshot", "response_snapshot", "timing", "constraints_applied")
                if not ep.get(section)
            ]
            if missing_sections or rp is None:
                failure = {
                    "ok": False,
                    "error": f"evidence/replay law violated: missing={missing_sections or []} replay={'absent' if rp is None else 'present'}",
                    "value": membrane_result.get("value"),
                    "evidence": ep,
                    "replay": rp,
                }
                self.spine.append(kind="LAW_VIOLATION", payload={"error": failure["error"]})
                return finish(failure)

        # Stage 6 — Audit Spine closes over EP/RP digests
        self.spine.append(kind="EP", payload={"digest_source": "membrane.evidence", "annotations": ep.get("annotations")})
        self.spine.append(
            kind="RP",
            payload=(
                {
                    "sequence": rp.get("sequence"),
                    "packet_hash": rp.get("packet_hash"),
                    "deterministic": rp.get("deterministic"),
                }
                if isinstance(rp, dict)
                else {"absent": True}
            ),
        )
        csr = self.spine.csr(extra={"closed_run": {"intent": ir.record_id, "governance": gr.record_id}})
        self.spine.append(kind="CSR", payload={"csr_head": csr["head_hash"], "entry_count": csr["entry_count"]})

        result = {
            "ok": bool(membrane_result.get("ok")),
            "error": membrane_result.get("error"),
            "value": membrane_result.get("value"),
            "intent": ir.as_dict(),
            "evidence": ep,
            "replay": rp,
            "constitutional_state": {
                "pipeline_id": PIPELINE_AMUL_ID,
                "pipeline_version": PIPELINE_AMUL_VERSION,
                "governance_record": gr.as_dict(),
                "csr": csr,
            },
        }
        return finish(result)

    # -- helpers -------------------------------------------------------------

    def _resolve_executor(
        self,
        executor: Callable[[dict[str, Any]], Any] | None,
        capability: str,
        action: str,
    ) -> Callable[[dict[str, Any]], Any]:
        if executor is not None:
            return executor
        if self.bridge is not None:
            # Mythic: the artery drives the raw governed path; the membrane above
            # remains the single constitutional layer for this invocation.
            return lambda run_args: self.bridge.execute_selection(
                capability,
                action,
                args=run_args,
            )
        raise ValueError("GDP requires an executor (bridge-backed or explicit callable)")

    def _refused(self, ir: IntentRecord | None, gr: GovernanceRecord | None, error: str) -> dict[str, Any]:
        if ir is not None:
            self.spine.append(kind="IR", payload=ir.as_dict())
        if gr is not None:
            self.spine.append(kind="GR_REFUSED", payload=gr.as_dict())
        csr = self.spine.csr(extra={"refusal": error})
        self.spine.append(kind="CSR", payload={"csr_head": csr["head_hash"], "entry_count": csr["entry_count"]})
        return {
            "ok": False,
            "error": error,
            "value": None,
            "intent": ir.as_dict() if ir is not None else {},
            "evidence": {},
            "replay": None,
            "constitutional_state": {"pipeline_id": PIPELINE_AMUL_ID, "csr": csr},
        }


def pipeline_for_bridge(bridge: Any) -> GovernedDirectPipelineAmul:
    """Compose a GDP whose GCUs come from an AAIS bridge and whose default
    executor routes through the bridge's AMUL membrane (Service Bridge as CB)."""
    pipeline = GovernedDirectPipelineAmul(bridge=bridge, membrane=bridge._amul_membrane())
    pipeline.register_gcus_from_membrane(bridge._amul_membrane())
    return pipeline
