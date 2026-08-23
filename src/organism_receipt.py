"""organism_receipt.v1 — Python adapter for the unified AI Organism receipt.

Mythic: one body, one law, one receipt.
Engineering: OrganismReceiptAdapter

Canonical form matches src/lirl/organismReceipt.js byte-for-byte: sorted
keys, no whitespace, UTF-8, sha256 ids prefixed "org:". See
docs/ORGANISM_RECEIPT_CONTRACT.md in Sovereign-X-Constitutional-Compute.

Honest maturity tags:
    lirl + amul dialects   - enforced (tests/test_organism_receipt.py)
    nx-replay/infinity-trace dialects - declared, not yet mapped
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any

try:
    from src.datetime_compat import UTC  # type: ignore
except Exception:  # pragma: no cover
    from datetime import timezone as UTC  # type: ignore

ORGANISM_RECEIPT_VERSION = "organism_receipt.v1"
OUTCOMES = ("accept", "reject", "escalate")
DIALECTS = ("lirl", "amul", "nx-replay", "infinity-trace")
SECTIONS = ("organ", "intent", "decision", "effect", "evidence", "replay", "continuity")


def canonical_json(value: Any) -> str:
    if value is None or isinstance(value, (str, int, float, bool)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ",".join(canonical_json(item) for item in value) + "]"
    return "{" + ",".join(
        f"{json.dumps(str(key), ensure_ascii=False)}:{canonical_json(value[key])}"
        for key in sorted(value.keys(), key=str)
    ) + "}"


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _digest_of(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
        return value
    return sha256_hex(canonical_json(value))


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def from_lirl(stored: dict[str, Any], *, endpoint: str = "http://127.0.0.1:7801") -> dict[str, Any]:
    """Mirror of the Node adapter — reads a LIRL stored evidence receipt."""
    verdict = str(stored.get("verdict") or "").upper()
    outcome = "accept" if verdict == "ACCEPT" else "reject"
    reasons = list(stored.get("reasons") or [])
    actor_id = str(stored.get("actorId") or "")
    actor_class = (
        actor_id.lower() if actor_id.lower() in ("governance", "runtime", "operator") else "agent"
    )
    packet_hash = ""
    raw_id = str(stored.get("receiptId") or "")
    if raw_id.startswith("evidence:"):
        packet_hash = raw_id[len("evidence:"):]
    receipt: dict[str, Any] = {
        "organism_receipt_version": ORGANISM_RECEIPT_VERSION,
        "receipt_id": "",
        "issued_at_utc": stored.get("issuedAt") or _utc_now_iso(),
        "organ": {
            "name": stored.get("subsystem") or "lirl-organism",
            "endpoint": endpoint,
            "dialect": "lirl",
            "actor_class": actor_class,
        },
        "intent": {
            "record_id": stored.get("intentId") or "",
            "kind": "action",
            "text_digest": _digest_of(stored.get("subjectHash")),
            "actor_id": actor_id,
            "actor_class": actor_class,
        },
        "decision": {
            "outcome": outcome,
            "legacy_verdict": verdict,
            "reason": "; ".join(reasons),
            "authority_chain": [
                {"check": "actor_identity", "allowed": outcome == "accept" or not any("anonymous" in r.lower() for r in reasons), "reason": reasons[0] if reasons else ""},
                {"check": "action_allowlist", "allowed": outcome == "accept", "reason": reasons[1] if len(reasons) > 1 else ""},
            ],
            "governance_mode": "strict",
        },
        "effect": {
            "action": stored.get("action") or "",
            "allowlist": [],
            "performed": bool(stored.get("memoryWritten")),
            "target": "memory",
            "adapter_kind": "local",
        },
        "evidence": {
            "claim_label": stored.get("claimLabel") or "",
            "request_digest": _digest_of(stored.get("subjectHash")),
            "response_digest": _digest_of(stored.get("evidenceRefs")),
            "timing": {"started_utc": "", "finished_utc": stored.get("issuedAt") or "", "duration_ms": 0},
            "constraints_applied": {"allowlist_enforced": True},
            "verification_result": [
                {"check": f"lirl_invariant_{index + 1}", "allowed": outcome == "accept" or index > 0, "reason": reason}
                for index, reason in enumerate(reasons)
            ],
        },
        "replay": {
            "packet_hash": packet_hash,
            "prev_hash": "",
            "deterministic": True,
            "non_determinism_reason": "",
        },
        "continuity": {
            "spine_id": f"{stored.get('subsystem') or 'lirl'}.spine",
            "sequence": int(stored.get("sequence") or 0),
            "head_hash": "",
            "continuity_intact": True,
            "joined_via": ":7801",
        },
    }
    receipt["receipt_id"] = "org:" + sha256_hex(canonical_json({**receipt}))
    return receipt


def from_amul(gdp_result: dict[str, Any], *, organ_name: str = "infinity-backend") -> dict[str, Any]:
    """Map a GovernedDirectPipelineAmul.run() result into organism_receipt.v1."""
    state = dict(gdp_result.get("constitutional_state") or {})
    gr = dict(state.get("governance_record") or {})
    csr = dict(state.get("csr") or {})
    evidence = dict(gdp_result.get("evidence") or {})
    replay = dict(gdp_result.get("replay") or {}) if gdp_result.get("replay") else {}
    intent = dict(gdp_result.get("intent") or {})
    decision_support: dict[str, Any] = {}
    nested_value = gdp_result.get("value")
    if isinstance(nested_value, dict) and isinstance(nested_value.get("decision_support"), dict):
        decision_support = dict(nested_value["decision_support"])
    elif isinstance(gdp_result.get("decision_support"), dict):
        decision_support = dict(gdp_result["decision_support"])
    outcome = str(decision_support.get("outcome") or (
        "accept" if gdp_result.get("ok") else "reject"
    ))
    authority_chain = [
        {"check": item.get("check"), "allowed": bool(item.get("allowed")), "reason": item.get("reason")}
        for item in (*(gr.get("authority_chain") or []), *(gr.get("validation_chain") or []))
        if isinstance(item, dict)
    ]
    annotations = dict(evidence.get("annotations") or {})
    request_snapshot = evidence.get("request_snapshot")
    response_view = evidence.get("response_snapshot")
    timing = dict(evidence.get("timing") or {})
    constraints_applied = dict(evidence.get("constraints_applied") or {})
    receipt = {
        "organism_receipt_version": ORGANISM_RECEIPT_VERSION,
        "receipt_id": "",
        "issued_at_utc": _utc_now_iso(),
        "organ": {
            "name": organ_name,
            "endpoint": "http://127.0.0.1:8000",
            "dialect": "amul",
            "actor_class": "runtime",
        },
        "intent": {
            "record_id": intent.get("record_id") or annotations.get("intent_record") or "",
            "kind": intent.get("kind") or "capability",
            "text_digest": _digest_of(intent.get("text")),
            "actor_id": str((request_snapshot or {}).get("operator_id") or "operator"),
        },
        "decision": {
            "outcome": outcome if outcome in OUTCOMES else ("accept" if gdp_result.get("ok") else "reject"),
            "legacy_verdict": "",
            "reason": str(gr.get("reason") or gdp_result.get("error") or ""),
            "authority_chain": authority_chain,
            "governance_mode": str(constraints_applied.get("governance_mode") or "strict"),
        },
        "effect": {
            "action": annotations.get("capability") or "",
            "allowlist": [],
            "performed": bool(gdp_result.get("ok")),
            "target": annotations.get("pipeline_id") or "",
            "adapter_kind": "provider" if replay and not replay.get("deterministic") else "local",
        },
        "evidence": {
            "claim_label": f"amul:{'accept' if gdp_result.get('ok') else 'reject'}:{annotations.get('pipeline_version') or ''}",
            "request_digest": _digest_of(request_snapshot),
            "response_digest": _digest_of(response_view),
            "timing": {
                "started_utc": timing.get("started_utc") or "",
                "finished_utc": timing.get("finished_utc") or "",
                "duration_ms": int(timing.get("duration_ms") or 0),
            },
            "constraints_applied": constraints_applied,
            "verification_result": list(evidence.get("verification_result") or []),
        },
        "replay": {
            "packet_hash": str(replay.get("packet_hash") or ""),
            "prev_hash": str(replay.get("prev_hash") or ""),
            "deterministic": bool(replay.get("deterministic")),
            "non_determinism_reason": str(replay.get("non_determinism_reason") or ""),
        },
        "continuity": {
            "spine_id": csr.get("pipeline_id") or "aais.governed_direct_pipeline.amul",
            "sequence": int(csr.get("entry_count") or 0),
            "head_hash": str(csr.get("head_hash") or ""),
            "continuity_intact": bool(csr.get("continuity_intact")),
            "joined_via": ":7801",
        },
    }
    receipt["receipt_id"] = "org:" + sha256_hex(canonical_json({**receipt}))
    return receipt


def validate_organism_receipt(receipt: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(receipt, dict):
        return False, ["receipt is not an object"]
    if receipt.get("organism_receipt_version") != ORGANISM_RECEIPT_VERSION:
        errors.append("organism_receipt_version must be organism_receipt.v1")
    for section in SECTIONS:
        value = receipt.get(section)
        if not isinstance(value, dict):
            errors.append(f"missing section: {section}")
    actor_id = str((receipt.get("intent") or {}).get("actor_id") or "")
    outcome = (receipt.get("decision") or {}).get("outcome")
    if outcome == "accept":
        if not actor_id.strip():
            errors.append("law 2: no anonymous actors — intent.actor_id required")
        elif actor_id.lower() == "anonymous":
            errors.append("law 2: anonymous actor is not lawful")
    elif not actor_id.strip() or actor_id.lower() == "anonymous":
        # Lawful refusal documenting an unlawful attempt — evidence stays valid,
        # but the recorded actor must be marked as attempted-anonymous.
        intent_section = receipt.get("intent") or {}
        if isinstance(intent_section, dict) and not str(intent_section.get("actor_class") or ""):
            errors.append("refusal receipts must record actor_class for the attempted identity")
    outcome = (receipt.get("decision") or {}).get("outcome")
    if outcome not in OUTCOMES:
        errors.append(f"decision.outcome must be one of {'|'.join(OUTCOMES)}")
    dialect = (receipt.get("organ") or {}).get("dialect")
    if dialect not in DIALECTS:
        errors.append(f"organ.dialect must be one of {'|'.join(DIALECTS)}")
    if not isinstance((receipt.get("effect") or {}).get("performed"), bool):
        errors.append("effect.performed must be boolean")
    continuity = receipt.get("continuity") or {}
    if not isinstance(continuity.get("continuity_intact"), bool):
        errors.append("continuity.continuity_intact must be boolean")
    return (len(errors) == 0), errors


def verify_receipt_id(receipt: dict[str, Any]) -> bool:
    receipt_id = str(receipt.get("receipt_id") or "")
    if not receipt_id.startswith("org:"):
        return False
    clone = dict(receipt)
    clone["receipt_id"] = ""
    return "org:" + sha256_hex(canonical_json(clone)) == receipt_id
