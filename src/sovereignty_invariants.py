"""INV-SOV-001 — the sovereignty inheritance axiom.

    No sovereignty ring may attest system validity without
    cryptographically binding the validity evidence of every
    sovereignty ring beneath it.

Rings and their evidence:

    R1 Law        constitution_hash + invariant_bundle_hash
    R2 Execution  caller_principal + authority_proof + runtime_measurement
    R3 Continuity  epoch_id + previous_receipt_hash + monotonic_position
    R4 Machine    machine_attestation + trust_manifest_hash
    R5 Governance governance_proof

This module is the single cross-ring gate: CommitCertificate.validate()
proves intra-certificate consistency, EpochLedger proves chain
continuity, TrustManifest legitimises measurements — a transition
commits only when all three agree at append time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from src.commit_certificate import CommitCertificate
from src.epoch_ledger import EpochLedger
from src.trust_manifest import TrustManifest

INV_SOV_001 = "INV-SOV-001"


@dataclass(frozen=True)
class SovereigntyVerdict:
    """Result of evaluating INV-SOV-001 over one proposed transition."""

    allowed: bool
    violations: Tuple[str, ...] = field(default_factory=tuple)
    continuity_broken: bool = False
    recovered_epoch: bool = False

    def to_json(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "violations": list(self.violations),
            "continuity_broken": self.continuity_broken,
            "recovered_epoch": self.recovered_epoch,
        }


def enforce_inv_sov_001(
    certificate: CommitCertificate,
    *,
    trust_manifest: TrustManifest,
    ledger: EpochLedger,
) -> SovereigntyVerdict:
    """Evaluate every ring's binding to all lower rings for one proposal."""
    violations: List[str] = []
    ok, reason = ledger.load_and_verify()
    if not ok:
        return SovereigntyVerdict(
            allowed=False,
            violations=(f"R3: ledger unverified: {reason}",),
            continuity_broken=True,
        )

    # ---- R1 Law ----
    if not certificate.constitution_hash:
        violations.append("R1: missing constitution_hash")
    if not certificate.invariant_bundle_hash:
        violations.append("R1: missing invariant_bundle_hash")

    # ---- R2 -> R1 ----
    if not certificate.caller_principal:
        violations.append("R2->R1: missing caller_principal")
    if len(certificate.authority_proof) < 20:
        violations.append(
            "R2->R1: authority proof empty or trivial (VT evidence required)"
        )
    if certificate.runtime_measurement != trust_manifest.cen_runtime_hash:
        violations.append(
            "R2->R1: runtime measurement does not match the manifest-certified runtime"
        )
    if certificate.constitution_hash != trust_manifest.constitution_hash:
        violations.append(
            f"R2->R1: constitution mismatch cert={certificate.constitution_hash[:24]}.. "
            f"manifest={trust_manifest.constitution_hash[:24]}.."
        )
    if certificate.invariant_bundle_hash != trust_manifest.invariant_bundle_hash:
        violations.append(
            "R2->R1: invariant bundle hash mismatch against the active manifest"
        )

    # ---- R3 -> R2 ----
    if certificate.epoch_id != ledger.current_epoch_id:
        violations.append(
            f"R3->R2: epoch mismatch cert={certificate.epoch_id[:24]}.. "
            f"ledger={ledger.current_epoch_id[:24]}.."
        )
    head = ledger.head_hash
    if certificate.previous_receipt_hash != head:
        violations.append(
            "R3->R2: previous_receipt_hash does not link to the live ledger head"
        )
    expected_position = ledger.position + 1
    if certificate.monotonic_position != expected_position:
        violations.append(
            f"R3->R2: monotonic regression {certificate.monotonic_position} "
            f"!= {expected_position}"
        )

    # ---- R4 -> R3 ----
    if certificate.trust_manifest_hash != trust_manifest.manifest_hash:
        violations.append(
            "R4->R3: trust manifest hash does not bind the active manifest"
        )
    if not certificate.machine_attestation:
        violations.append("R4->R3: missing machine attestation")

    # ---- R5 -> R4 (incl. post-discontinuity rule) ----
    recovered_epoch = ledger.current_epoch_is_recovery
    if ledger.continuity_broken and not recovered_epoch:
        violations.append(
            "R5->R3: post-discontinuity commits require a RECOVERY-opened epoch"
        )
    needs_governance = True
    if needs_governance and not certificate.governance_proof:
        violations.append(
            "R5->R4: governance proof required"
            + (
                " after trust discontinuity"
                if ledger.continuity_broken and not recovered_epoch
                else ""
            )
        )

    return SovereigntyVerdict(
        allowed=not violations,
        violations=tuple(violations),
        continuity_broken=ledger.continuity_broken,
        recovered_epoch=recovered_epoch,
    )


def commit_certified(
    ledger: EpochLedger,
    certificate: CommitCertificate,
    trust_manifest: TrustManifest,
):
    """Gate a COMMIT through INV-SOV-001, then land it in the ledger.

    The receipt's payload_digest carries the certificate's own hash so the
    persisted chain contains the evidence that made the transition
    admissible — not merely a record that something happened.
    Returns (verdict, receipt_dict); receipt is {} when refused.
    """
    verdict = enforce_inv_sov_001(
        certificate=certificate, trust_manifest=trust_manifest, ledger=ledger
    )
    if not verdict.allowed:
        return verdict, {}
    receipt = ledger.append_commit(
        payload_digest=certificate.previous_hash(),
        resulting_state_hash=certificate.resulting_state_hash,
        authority_ref=certificate.authority_proof[:64],
        notes=(
            f"inv={INV_SOV_001}",
            f"cert={certificate.previous_hash()}",
            f"caller={certificate.caller_principal[:96]}",
        ),
    )
    return verdict, receipt
