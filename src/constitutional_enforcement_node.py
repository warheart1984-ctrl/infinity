"""Constitutional Enforcement Node — Python port of @aaes-os/constitutional-enforcement-node.

Mythic: every crossing of the law is intercepted, judged, and sealed.
Engineering: EP-1 lifecycle (intercept -> evaluate -> allow/deny) with
replay detection, capability gates, authority-token validation
(VT|FT|MRT|RT), invariant evaluation, hash-chained enforcement receipts,
and deterministic sha3-256 receipt ids matching the TypeScript reference
byte-for-byte (receipt base keys stay TS-native camelCase per the Key
Identity Law in docs/contracts/ORGANISM_RECEIPT_CONTRACT.md).
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Callable

from src.invariant_registry import CONSTITUTIONAL_DIMENSIONS
from src.commit_certificate import CommitCertificate, build_certificate_from_approval

TRANSITION_TYPES = ("state_update", "law_mutation", "runtime_action", "evidence_commit")
VERDICTS = ("ALLOW", "DENY")
ENFORCEMENT_ACTIONS = ("ALLOW", "DENY", "FREEZE", "MANDATORY_REVIEW")
REASON_CODES = (
    "ALLOWED", "CAPABILITY_DENIED", "INVARIANT_VIOLATION", "INVALID_TRANSITION",
    "MALFORMED_TRANSITION", "REPLAY_DETECTED", "TOKEN_INVALID_SIGNATURE",
    "TOKEN_EXPIRED", "TOKEN_SCOPE_DENIED", "TOKEN_REPLAYED", "TOKEN_TRANSITION_MISMATCH",
)
RECEIPT_CATEGORIES = ("allow", "deny", "anomaly", "replay", "token_refusal")

AUTHORITY_TOKEN_TYPES = ("VT", "FT", "MRT", "RT")
AUTHORITY_TOKEN_DOMAIN = "AAES-CEN-AUTHORITY-TOKEN-v1"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=3, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _field(obj: dict[str, Any], snake: str, *camel: str) -> Any:
    if isinstance(obj, dict):
        if snake in obj:
            return obj.get(snake)
        for name in camel:
            if name in obj:
                return obj.get(name)
    return None


def stable_stringify(value: Any) -> str:
    """Sorted-key compact JSON; drops undefined-equivalent absent keys (no-op in Python)."""
    if value is None or isinstance(value, (str, bool, int, float)):
        return json_dumps(value)
    if isinstance(value, list):
        return "[" + ",".join(stable_stringify(item) for item in value) + "]"
    if isinstance(value, dict):
        keys = sorted((k for k in value.keys()), key=str)
        return "{" + ",".join(
            f"{json_dumps(str(key))}:{stable_stringify(value[key])}" for key in keys
        ) + "}"
    return json_dumps(str(value))


def json_dumps(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)


def hash_json(value: Any) -> str:
    digest = hashlib.sha3_256(stable_stringify(value).encode("utf-8")).hexdigest()
    return f"sha3-256:{digest}"


def authority_token_signature(token: dict[str, Any]) -> str:
    material = "|".join(
        [
            AUTHORITY_TOKEN_DOMAIN,
            str(token.get("tokenId") or ""),
            str(token.get("tokenType") or ""),
            ",".join(token.get("scope") or []),
            str(token.get("transitionId") or ""),
            str(token.get("issuedAt") or ""),
            str(token.get("expiresAt") or ""),
        ]
    )
    return hashlib.sha3_256(material.encode("utf-8")).hexdigest()


def issue_authority_token(
    *,
    token_id: str,
    token_type: str,
    scope: list[str],
    transition_id: str,
    expires_at: str,
    issued_at: str | None = None,
) -> dict[str, Any]:
    token: dict[str, Any] = {
        "tokenId": token_id,
        "tokenType": token_type,
        "scope": list(scope),
        "transitionId": transition_id,
        "expiresAt": expires_at,
        "issuedAt": issued_at or _utc_now_iso(),
        "signature": "",
    }
    token["signature"] = authority_token_signature(token)
    return token


def category_for_decision(decision: dict[str, Any]) -> str:
    verdict = decision.get("verdict")
    reason_code = str(decision.get("reasonCode") or "")
    if verdict == "ALLOW":
        return "allow"
    if reason_code == "REPLAY_DETECTED":
        return "replay"
    if reason_code.startswith("TOKEN_"):
        return "token_refusal"
    if reason_code in {"MALFORMED_TRANSITION", "INVALID_TRANSITION"}:
        return "anomaly"
    return "deny"


def validate_transition_shape(transition: dict[str, Any]) -> str | None:
    if not isinstance(transition, dict):
        return "transition object is required"
    transition_id = str(transition.get("transitionId") or "")
    if not transition_id.strip():
        return "transitionId is required"
    if not transition.get("transitionType"):
        return "transitionType is required"
    if not isinstance(transition.get("requestedCapabilities"), list):
        return "requestedCapabilities must be an array"
    context = transition.get("context") or {}
    runtime_context = _field(context, "runtime_context", "runtimeContext") or {}
    capabilities = _field(runtime_context, "capabilities")
    if not isinstance(capabilities, list):
        return "runtimeContext capabilities are required"
    if transition.get("payload") is None:
        return "payload is required"
    return None


def read_proposed_score(transition: dict[str, Any], dimension: str) -> float:
    payload = transition.get("payload")
    if isinstance(payload, dict) and isinstance(payload.get(dimension), (int, float)):
        return float(payload[dimension])
    context = transition.get("context") or {}
    snapshot = _field(context, "mri_snapshot", "mriSnapshot") or {}
    return float(snapshot[dimension])


class ResourceFloorInvariant:
    """Floor check over one constitutional dimension.

    When required_authority_token is set (e.g. INV-021 -> VT), the
    declaration is load-bearing: a transition whose PAYLOAD sets the
    dimension must carry an authority token of the declared type.
    Snapshot-only reads remain ungated — they observe state, they do
    not propose it.
    """

    def __init__(
        self,
        dimension: str,
        floor: float,
        *,
        required_authority_token: str | None = None,
        name: str | None = None,
    ):
        if dimension not in CONSTITUTIONAL_DIMENSIONS:
            raise ValueError(f"unknown constitutional dimension: {dimension}")
        self.dimension = dimension
        self.floor = floor
        self.name = name or f"{dimension} floor"
        self.required_authority_token = required_authority_token
        self.invariant_id = f"resource-floor:{dimension}:min:{_num(floor)}"

    def _check_payload_token_requirement(
        self, transition: dict[str, Any]
    ) -> dict[str, Any] | None:
        if not self.required_authority_token:
            return None
        payload = transition.get("payload")
        if not (isinstance(payload, dict) and isinstance(payload.get(self.dimension), (int, float))):
            return None  # observes snapshot only — not proposing the dimension
        token = transition.get("authorityToken") or transition.get("authority_token")
        if not token:
            return {
                "invariantId": self.invariant_id,
                "passed": False,
                "message": (
                    f"{self.name}: setting '{self.dimension}' requires a "
                    f"{self.required_authority_token} authority token"
                ),
                "action": "DENY",
            }
        token_type = str(token.get("tokenType") or "").upper()
        if token_type != str(self.required_authority_token).upper():
            return {
                "invariantId": self.invariant_id,
                "passed": False,
                "message": (
                    f"{self.name}: setting '{self.dimension}' requires a "
                    f"{self.required_authority_token} token, got {token_type or 'none'}"
                ),
                "action": "DENY",
            }
        return None

    def evaluate(self, transition: dict[str, Any]) -> dict[str, Any]:
        token_refusal = self._check_payload_token_requirement(transition)
        if token_refusal is not None:
            return token_refusal
        proposed = read_proposed_score(transition, self.dimension)
        passed = proposed >= self.floor
        return {
            "invariantId": self.invariant_id,
            "passed": passed,
            "message": (
                f"{self.dimension} satisfies floor {_num(self.floor)}"
                if passed
                else f"{self.dimension} {_num(proposed)} fell below constitutional floor {_num(self.floor)}"
            ),
            "action": "ALLOW" if passed else "DENY",
        }


def create_resource_floor_invariant(
    dimension: str,
    floor: float,
    *,
    required_authority_token: str | None = None,
    name: str | None = None,
) -> ResourceFloorInvariant:
    return ResourceFloorInvariant(
        dimension, floor, required_authority_token=required_authority_token, name=name
    )


_REQUIRE_RE = re.compile(
    rf"^require\s+({'|'.join(CONSTITUTIONAL_DIMENSIONS)})\s*>=\s*(\d+(?:\.\d+)?)$",
    re.IGNORECASE,
)


class CompiledDslInvariant:
    """``require``-syntax invariant compiled from source (CEN bridge dialect)."""

    def __init__(self, dimension: str, floor: float):
        self.dimension = dimension
        self.floor = floor
        self.invariant_id = f"idsl:{dimension}:min:{_num(floor)}"

    def evaluate(self, transition: dict[str, Any]) -> dict[str, Any]:
        proposed = read_proposed_score(transition, self.dimension)
        passed = proposed >= self.floor
        return {
            "invariantId": self.invariant_id,
            "passed": passed,
            "message": (
                f"{self.dimension} satisfies DSL floor {_num(self.floor)}"
                if passed
                else f"{self.dimension} {_num(proposed)} violated DSL floor {_num(self.floor)}"
            ),
            "action": "ALLOW" if passed else "DENY",
        }


def compile_invariant_dsl(source: str) -> CompiledDslInvariant:
    """CEN bridge DSL — legacy ``require <dim> >= <floor>`` only (rich IDSL-1
    lives in src/invariant_registry.py)."""
    match = _REQUIRE_RE.match(str(source or "").strip())
    if not match:
        raise ValueError(f"unsupported invariant DSL: {source}")
    dimension = match.group(1).lower()
    floor = float(match.group(2))
    if dimension not in CONSTITUTIONAL_DIMENSIONS:
        raise ValueError(f"unknown constitutional dimension: {dimension}")
    return CompiledDslInvariant(dimension, floor)


class ConstitutionalEnforcementNode:
    """Governed execution shell boundary: nothing commits without a receipt."""

    def __init__(
        self,
        *,
        invariants: list[Any],
        issued_at: Callable[[], str] | None = None,
    ):
        self._invariants = list(invariants)
        self._issued_at = issued_at or _utc_now_iso
        self._state_store: dict[str, Any] = {}
        self._ledger: list[dict[str, Any]] = []
        self._seen_transitions: set[str] = set()
        self._used_authority_tokens: set[str] = set()

    # ------------------------------------------------------------ EP-1 lifecycle

    def intercept(self, transition: dict[str, Any]) -> dict[str, Any]:
        return {"stage": "intercept", "transition": transition}

    def evaluate(self, intercepted: dict[str, Any]) -> dict[str, Any]:
        transition = intercepted["transition"]
        malformed = validate_transition_shape(transition)
        if malformed:
            return self._evaluated(
                transition, [], self._decision("DENY", "DENY", "MALFORMED_TRANSITION", malformed)
            )
        transition_id = str(transition.get("transitionId") or "")
        if transition_id in self._seen_transitions:
            return self._evaluated(
                transition, [], self._decision("DENY", "DENY", "REPLAY_DETECTED", "transition replay detected")
            )

        context = transition.get("context") or {}
        runtime_context = _field(context, "runtime_context", "runtimeContext") or {}
        granted = _field(runtime_context, "capabilities") or []
        capability_denied = next(
            (cap for cap in transition["requestedCapabilities"] if cap not in granted),
            None,
        )
        if capability_denied is not None:
            return self._evaluated(
                transition,
                [],
                self._decision("DENY", "DENY", "CAPABILITY_DENIED", f"capability denied: {capability_denied}"),
            )

        token_decision = self._validate_authority_token(transition)
        if token_decision is not None:
            return self._evaluated(transition, [], token_decision)

        evaluations = [invariant.evaluate(transition) for invariant in self._invariants]
        failed = next((evaluation for evaluation in evaluations if not evaluation["passed"]), None)
        if failed is not None:
            return self._evaluated(
                transition,
                evaluations,
                self._decision("DENY", failed.get("action") or "DENY", "INVARIANT_VIOLATION", failed["message"]),
            )

        return self._evaluated(
            transition, evaluations, self._decision("ALLOW", "ALLOW", "ALLOWED", "transition admitted by CEN")
        )

    def allow(self, evaluated: dict[str, Any], *, certificate: "CommitCertificate | None" = None) -> dict[str, Any]:
        return self._finish(evaluated, True, certificate=certificate)

    def deny(self, evaluated: dict[str, Any], *, certificate: "CommitCertificate | None" = None) -> dict[str, Any]:
        return self._finish(evaluated, False, certificate=certificate)

    def receipt(
        self,
        evaluated: dict[str, Any],
        *,
        certificate: "CommitCertificate | None" = None,
    ) -> dict[str, Any]:
        return self._create_receipt(
            evaluated["transition"], evaluated["decision"], evaluated["evaluations"], certificate=certificate
        )

    def execute(self, transition: dict[str, Any], *, certificate: "CommitCertificate | None" = None) -> dict[str, Any]:
        evaluated = self.evaluate(self.intercept(transition))
        if evaluated["decision"]["verdict"] == "ALLOW":
            return self.allow(evaluated, certificate=certificate)
        return self.deny(evaluated)

    def get_state(self, transition_id: str) -> Any:
        return self._state_store.get(transition_id)

    def receipts(self) -> list[dict[str, Any]]:
        return list(self._ledger)

    # ------------------------------------------------------------------ internals

    def _finish(self, evaluated: dict[str, Any], requested_commit: bool, *, certificate: "CommitCertificate | None" = None) -> dict[str, Any]:
        transition = evaluated["transition"]
        committed = requested_commit and evaluated["decision"]["verdict"] == "ALLOW"
        if committed:
            self._state_store[str(transition["transitionId"])] = transition["payload"]
        if str(transition.get("transitionId") or "").strip():
            self._seen_transitions.add(str(transition["transitionId"]))
        authority_token = transition.get("authorityToken") or transition.get("authority_token")
        if authority_token and evaluated["decision"]["reasonCode"] != "TOKEN_REPLAYED":
            self._used_authority_tokens.add(str(authority_token.get("tokenId")))
        receipt = self.receipt(evaluated, certificate=certificate)
        self._ledger.append(receipt)
        return {"decision": evaluated["decision"], "committed": committed, "receipt": receipt}

    def _validate_authority_token(self, transition: dict[str, Any]) -> dict[str, Any] | None:
        token = transition.get("authorityToken") or transition.get("authority_token")
        if not token:
            return None
        token_id = str(token.get("tokenId") or "")
        if token_id in self._used_authority_tokens:
            return self._decision("DENY", "DENY", "TOKEN_REPLAYED", "authority token replayed")
        if str(token.get("signature") or "") != authority_token_signature(token):
            return self._decision("DENY", "DENY", "TOKEN_INVALID_SIGNATURE", "authority token signature invalid")
        expires = _parse_ts(str(token.get("expiresAt") or ""))
        if expires <= _now_ts():
            return self._decision("DENY", "DENY", "TOKEN_EXPIRED", "authority token expired")
        if str(token.get("transitionId") or "") != str(transition.get("transitionId")):
            return self._decision("DENY", "DENY", "TOKEN_TRANSITION_MISMATCH", "authority token transition mismatch")
        missing_scope = next(
            (cap for cap in transition["requestedCapabilities"] if cap not in (token.get("scope") or [])),
            None,
        )
        if missing_scope is not None:
            return self._decision("DENY", "DENY", "TOKEN_SCOPE_DENIED", f"authority token missing scope: {missing_scope}")
        return None

    def _create_receipt(
        self,
        transition: dict[str, Any],
        decision: dict[str, Any],
        evaluations: list[dict[str, Any]],
        *,
        certificate: "CommitCertificate | None" = None,
    ) -> dict[str, Any]:
        previous_hash = self._ledger[-1]["receiptHash"] if self._ledger else None
        context = transition.get("context") or {}
        authority_token = transition.get("authorityToken") or transition.get("authority_token")
        base: dict[str, Any] = {
            "transitionId": transition.get("transitionId"),
            "transitionType": transition.get("transitionType"),
            "actor": (context.get("actor") if isinstance(context, dict) else None) or "unknown",
            "verdict": decision["verdict"],
            "action": decision["action"],
            "reasonCode": decision["reasonCode"],
            "reasonDetail": decision["reasonDetail"],
            "category": category_for_decision(decision),
            "stage": "receipt",
            "evaluations": evaluations,
            "mriSnapshotHash": hash_json(
                (_field(context, "mri_snapshot", "mriSnapshot") or {}) if isinstance(context, dict) else {}
            ),
            "payloadHash": hash_json(transition.get("payload")),
            # TS semantics: absent token means the key is omitted (undefined),
            # not null — null WOULD be hashed and change the receipt id.
            "previousReceiptHash": previous_hash,
            "issuedAt": self._issued_at(),
        }
        if authority_token:
            base["authorityTokenId"] = authority_token.get("tokenId")
        receipt_hash = hash_json(base)
        receipt = {"receiptId": f"cen:{receipt_hash[len("sha3-256:"):]}"} 
        receipt.update(base)
        receipt["receiptHash"] = receipt_hash
        if certificate is not None:
            base_cert = {
                "constitution_hash": certificate.constitution_hash,
                "invariant_bundle_hash": certificate.invariant_bundle_hash,
                "caller_principal": certificate.caller_principal,
                "authority_proof": certificate.authority_proof,
                "runtime_measurement": certificate.runtime_measurement,
                "epoch_id": certificate.epoch_id,
                "previous_receipt_hash": certificate.previous_receipt_hash,
                "monotonic_position": certificate.monotonic_position,
                "machine_attestation": certificate.machine_attestation,
                "trust_manifest_hash": certificate.trust_manifest_hash,
                "governance_proof": certificate.governance_proof,
                "resulting_state_hash": certificate.resulting_state_hash,
            }
            receipt["commitCertificate"] = base_cert
        return receipt

    def _evaluated(
        self,
        transition: dict[str, Any],
        evaluations: list[dict[str, Any]],
        decision: dict[str, Any],
    ) -> dict[str, Any]:
        return {"stage": "evaluate", "transition": transition, "evaluations": evaluations, "decision": decision}

    def _decision(
        self,
        verdict: str,
        action: str,
        reason_code: str,
        reason_detail: str,
    ) -> dict[str, Any]:
        return {
            "verdict": verdict,
            "action": action,
            "reasonCode": reason_code,
            "reasonDetail": reason_detail,
        }


def verify_enforcement_receipt(receipt: dict[str, Any]) -> bool:
    base = {key: value for key, value in receipt.items() if key not in ("receiptId", "receiptHash")}
    return bool(receipt.get("receiptHash")) and receipt["receiptHash"] == hash_json(base)


def _parse_ts(value: str) -> float:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return 0.0


def _now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


def _num(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return repr(value)
