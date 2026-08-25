"""AAES evidence receipts — Python port of @aaes-os/evidence-receipts v0.2.

Mythic: every claim seals itself before it may cross a membrane.
Engineering: deterministic sha3-256 receipt ids over stable-stringified
subjects, mirroring packages/evidence-receipts/src/index.ts in the AAES-OS
monorepo byte-for-byte so Node-issued and Python-issued ids agree.

Receipt ids cover claimLabel|subsystem|evidenceRefs|subjectHash only — they
are intentionally time-independent; issued_at is provenance metadata.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

EVIDENCE_RECEIPTS_VERSION = "aaes_evidence_receipts.v1"

RECEIPT_KINDS = (
    "fault", "patch", "mri", "trust", "attestation", "runtime", "generic",
)

CEN_SUBSYSTEM = "constitutional-enforcement-node"
MRI_SUBSYSTEM = "mri-instrument"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_stringify(value: Any) -> str:
    """Sorted-key compact JSON — matches TS stableStringify byte-for-byte."""
    if value is None or isinstance(value, (str, bool, int, float)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ",".join(stable_stringify(item) for item in value) + "]"
    if isinstance(value, dict):
        keys = sorted(value.keys(), key=str)
        return "{" + ",".join(
            f"{json.dumps(str(key), ensure_ascii=False)}:{stable_stringify(value[key])}"
            for key in keys
        ) + "}"
    return json.dumps(str(value), ensure_ascii=False)


def hash_json(value: Any) -> str:
    digest = hashlib.sha3_256(stable_stringify(value).encode("utf-8")).hexdigest()
    return f"sha3-256:{digest}"


def infer_kind(subsystem: str, claim_label: str) -> str:
    value = f"{subsystem} {claim_label}".lower()
    if "mri" in value:
        return "mri"
    if "trust" in value:
        return "trust"
    if "attestation" in value:
        return "attestation"
    if "runtime" in value:
        return "runtime"
    if "patch" in value:
        return "patch"
    if "fault" in value:
        return "fault"
    return "generic"


def create_evidence_receipt(
    *,
    claim_label: str,
    subsystem: str,
    evidence_refs: list[str],
    subject: Any,
    kind: str | None = None,
    issued_at: str | None = None,
) -> dict[str, Any]:
    refs = list(evidence_refs)
    subject_hash = hash_json(subject)
    resolved_kind = kind or infer_kind(subsystem, claim_label)
    material = "|".join([claim_label, subsystem, ",".join(refs), subject_hash])
    receipt_id = "evidence:" + hashlib.sha3_256(material.encode("utf-8")).hexdigest()
    return {
        "receipt_id": receipt_id,
        "kind": resolved_kind,
        "claim_label": claim_label,
        "subsystem": subsystem,
        "evidence_refs": refs,
        "subject_hash": subject_hash,
        "issued_at": issued_at or _utc_now_iso(),
    }


def create_cen_evidence_receipt(subject: dict[str, Any]) -> dict[str, Any]:
    """Seal a constitutional-enforcement-node decision as evidence."""
    return create_evidence_receipt(
        claim_label=f"cen:{str(subject.get('verdict') or '').lower()}:{str(subject.get('reason_code') or subject.get('reasonCode') or '').lower()}",
        subsystem=CEN_SUBSYSTEM,
        evidence_refs=[
            str(subject.get("receipt_id") or subject.get("receiptId") or ""),
            str(subject.get("transition_id") or subject.get("transitionId") or ""),
            str(subject.get("receipt_hash") or subject.get("receiptHash") or ""),
        ],
        subject=subject,
        kind="runtime",
    )


def create_mri_evidence_receipt(
    *,
    evidence_id: str,
    provenance: str,
    recency: float,
    reliability: float,
    cross_evidence_consistency: float,
    subject: Any,
) -> dict[str, Any]:
    """Seal MRI evidence provenance (document/log/interview/policy/hearsay)."""
    return create_evidence_receipt(
        claim_label="mri-evidence-provenance",
        subsystem=MRI_SUBSYSTEM,
        evidence_refs=[
            evidence_id,
            f"provenance:{provenance}",
            f"recency:{recency}",
            f"reliability:{reliability}",
            f"crossEvidenceConsistency:{cross_evidence_consistency}",
        ],
        subject=subject,
        kind="mri",
    )


def verify_receipt_hash(receipt: dict[str, Any]) -> bool:
    subject_hash = str(receipt.get("subject_hash") or receipt.get("subjectHash") or "")
    receipt_id = str(receipt.get("receipt_id") or receipt.get("receiptId") or "")
    return subject_hash.startswith("sha3-256:") and receipt_id.startswith("evidence:")
