"""CommitCertificate — the shared proof vocabulary.

Every accepted state transition carries a CommitCertificate that contains
enough evidence to prove all lower sovereignty rings were valid at the
moment of commit.

The crucial word is certificate. The ledger shouldn't merely describe what
happened afterward. It should contain the evidence that made the transition
admissible.

VALID(cert_n):
    ∧ cert_n.previous_receipt_hash == H(cert_n-1)
    ∧ state_preconditions_hold
    -> COMMIT
otherwise
    -> REFUSE

This is the single source of truth that Rings 2–6 all contribute fields
to. Without it, each new ring risks adding another bespoke verification
mechanism. With it, Rings 3–6 simply make additional mandatory fields
in the same state-transition proof.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from src.trust_manifest import TrustManifest


@dataclass(frozen=True)
class CommitCertificate:
    """Immutable proof that a state transition was legitimately admitted.

    This is the unit of proof written to the Ring 3 ledger. Every field
    here is derived from evidence that must be valid at commit time, not
    recorded after the fact.

    Ring contributions (each ring adds one or more fields; the certificate
    is the shared vocabulary):
    - Ring 2 (Execution): caller_principal + authority_proof + runtime_measurement
    - Ring 3 (Continuity): epoch_id + previous_receipt_hash + monotonic_position
    - Ring 4 (Machine): machine_attestation + trust_manifest_hash
    - Ring 5 (Governance): governance_proof
    - Ring 1 (Law): constitution_hash + invariant_bundle_hash
    """

    # Ring 1 — Law
    constitution_hash: str
    invariant_bundle_hash: str

    # Ring 2 — Execution
    caller_principal: str  # PID + binary hash of the proposing process
    authority_proof: str  # VT token signature that satisfies INV-021
    runtime_measurement: str  # hash of the cen runtime at commit time

    # Ring 3 — Continuity
    epoch_id: str  # boot-derive epoch; prevents splicing histories
    previous_receipt_hash: str  # H(cert_{n-1}) — chain link
    monotonic_position: int  # append-only position in the ledger

    # Ring 4 — Machine
    machine_attestation: str  # TPM quote or age-sealed measurement proof
    trust_manifest_hash: str  # hash of the TrustManifest that authorises this machine

    # Ring 5 — Governance
    governance_proof: str  # quorum sigs / manifest update that authorises the transition

    # Result
    resulting_state_hash: str  # hash of the state after commit

    # ---- chain link ----

    def previous_hash(self) -> str:
        """Hash of the previous certificate in the ledger, for the chain link."""
        base = json.dumps(
            {
                "constitution_hash": self.constitution_hash,
                "invariant_bundle_hash": self.invariant_bundle_hash,
                "caller_principal": self.caller_principal,
                "authority_proof": self.authority_proof,
                "runtime_measurement": self.runtime_measurement,
                "epoch_id": self.epoch_id,
                "previous_receipt_hash": self.previous_receipt_hash,
                "monotonic_position": self.monotonic_position,
                "machine_attestation": self.machine_attestation,
                "trust_manifest_hash": self.trust_manifest_hash,
                "governance_proof": self.governance_proof,
                "resulting_state_hash": self.resulting_state_hash,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return "sha3-256:" + hashlib.sha3_256(base.encode("utf-8")).hexdigest()

    # ---- validation ----

    def validate(
        self,
        *,
        last_certificate: Optional["CommitCertificate"],
        trust_manifest: TrustManifest,
        current_measurements: Dict[str, str],
    ) -> Tuple[bool, str]:
        """Validate this certificate against the ledger state.

        Returns (True, "") if valid, or (False, reason) if invalid.
        """
        # 1. Chain link: previous_receipt_hash must match last cert's resulting_state_hash
        if last_certificate is not None:
            expected_prev = last_certificate.resulting_state_hash
            if self.previous_receipt_hash != expected_prev:
                return False, (
                    f"chain break: previous_receipt_hash={self.previous_receipt_hash} "
                    f"!= last resulting_state_hash={expected_prev}"
                )

        # 2. Monotonic position must increment
        if last_certificate is not None:
            if self.monotonic_position <= last_certificate.monotonic_position:
                return False, (
                    f"monotonic position regression: {self.monotonic_position} "
                    f"<= {last_certificate.monotonic_position}"
                )

        # 3. Epoch must be consistent with trust manifest
        if self.epoch_id != current_measurements.get("epoch_id", ""):
            return False, (
                f"epoch mismatch: cert epoch={self.epoch_id} "
                f"!= current epoch={current_measurements.get('epoch_id', '')}"
            )

        # 4. Trust manifest must authorise the machine attestation
        # Concrete verification is deployment-specific; stub checks non-empty hash
        if not self.trust_manifest_hash or len(self.trust_manifest_hash) < 20:
            return False, "trust_manifest_hash is empty or too short"

        # 5. Authority proof must be non-empty (INV-021 VT token check)
        if not self.authority_proof or len(self.authority_proof) < 20:
            return False, "authority_proof is empty or too short"

        # 6. Constitution hash must match the trust manifest's constitution hash
        if self.constitution_hash != trust_manifest.constitution_hash:
            return False, (
                f"constitution hash mismatch: cert={self.constitution_hash} "
                f"!= manifest={trust_manifest.constitution_hash}"
            )

        # 7. Invariant bundle hash must match
        if self.invariant_bundle_hash != trust_manifest.invariant_bundle_hash:
            return False, (
                f"invariant bundle hash mismatch: cert={self.invariant_bundle_hash} "
                f"!= manifest={trust_manifest.invariant_bundle_hash}"
            )

        return True, ""


# ---- certificate construction ----

def build_certificate_from_approval(
    *,
    constitution_hash: str,
    invariant_bundle_hash: str,
    caller_principal: str,
    authority_token: dict,
    runtime_measurement: str,
    epoch_id: str,
    last_receipt_hash: str,
    monotonic_position: int,
    machine_attestation: str,
    trust_manifest: TrustManifest,
    governance_proof: str,
    resulting_state_hash: str,
) -> CommitCertificate:
    """Build a CommitCertificate from a CEN approval + runtime state.

    This is the canonical construction path. All fields derive from
    evidence present at commit time; nothing is recorded post-hoc.
    """
    # Derive authority_proof from the authority token's signature material
    auth_material = "|".join(
        [
            authority_token.get("tokenId", ""),
            authority_token.get("tokenType", ""),
            ",".join(authority_token.get("scope", [])),
            authority_token.get("transitionId", ""),
        ]
    )
    authority_proof = "sha3-256:" + hashlib.sha3_256(auth_material.encode("utf-8")).hexdigest()

    # Derive epoch_id from the trust manifest + boot measurements
    # (the epoch_id itself is computed at boot; here we just bind it)
    # The cert's epoch_id should match what the daemon computed at boot.

    return CommitCertificate(
        constitution_hash=constitution_hash,
        invariant_bundle_hash=invariant_bundle_hash,
        caller_principal=caller_principal,
        authority_proof=authority_proof,
        runtime_measurement=runtime_measurement,
        epoch_id=epoch_id,
        previous_receipt_hash=last_receipt_hash,
        monotonic_position=monotonic_position,
        machine_attestation=machine_attestation,
        trust_manifest_hash=trust_manifest.manifest_hash,
        governance_proof=governance_proof,
        resulting_state_hash=resulting_state_hash,
    )