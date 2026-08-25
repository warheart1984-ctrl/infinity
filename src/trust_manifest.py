"""TrustManifest — canonical allowlist that bridges hardware measurement
to constitutional legitimacy.

This is the single source of truth for Ring 4 (machine sovereignty):
what measurements are lawful, what runtime is permitted, and what
constitution authorises the current manifest.

The TPM proves measurements. The manifest says which measurements are
lawful. The constitution determines who may sign a new manifest.

Ring 4 invariant: hardware can only attest; the manifest legitimises.
Without this layer, hardware attestation quietly becomes sovereign.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class TrustManifest:
    """Immutable declaration of what constitutes an acceptable machine instance.

    Invariants:
    - manifest_hash binds parent + measurements + constitution + runtime +
      classifier + invariant bundle + mutation gateway + allowed PCRs +
      schema versions + minimum security epoch + signatures.
    - parent_manifest_hash creates the inheritance chain (Ring 5→4→3→2).
    - TPM proves measurements; manifest says which are permitted; constitution
      says who may sign a new manifest.
    """

    manifest_hash: str
    parent_manifest_hash: Optional[str]
    constitution_hash: str
    cen_runtime_hash: str
    classifier_hash: str
    invariant_bundle_hash: str
    mutation_gateway_hash: str
    allowed_pcrs: Dict[int, str]
    allowed_kernel_measurements: Tuple[str, ...]
    allowed_bootloader_measurements: Tuple[str, ...]
    ledger_schema_version: int
    authority_schema_version: int
    min_security_epoch: int
    signatures: Tuple[str, ...]

    # ---- roundtrip ----

    @classmethod
    def from_json(cls, data: dict) -> "TrustManifest":
        return cls(
            manifest_hash=data["manifest_hash"],
            parent_manifest_hash=data.get("parent_manifest_hash"),
            constitution_hash=data["constitution_hash"],
            cen_runtime_hash=data["cen_runtime_hash"],
            classifier_hash=data["classifier_hash"],
            invariant_bundle_hash=data["invariant_bundle_hash"],
            mutation_gateway_hash=data["mutation_gateway_hash"],
            allowed_pcrs=dict(data["allowed_pcrs"]),
            allowed_kernel_measurements=tuple(data["allowed_kernel_measurements"]),
            allowed_bootloader_measurements=tuple(data["allowed_bootloader_measurements"]),
            ledger_schema_version=int(data["ledger_schema_version"]),
            authority_schema_version=int(data["authority_schema_version"]),
            min_security_epoch=int(data["min_security_epoch"]),
            signatures=tuple(data["signatures"]),
        )

    def to_json(self) -> dict:
        return {
            "manifest_hash": self.manifest_hash,
            "parent_manifest_hash": self.parent_manifest_hash,
            "constitution_hash": self.constitution_hash,
            "cen_runtime_hash": self.cen_runtime_hash,
            "classifier_hash": self.classifier_hash,
            "invariant_bundle_hash": self.invariant_bundle_hash,
            "mutation_gateway_hash": self.mutation_gateway_hash,
            "allowed_pcrs": dict(self.allowed_pcrs),
            "allowed_kernel_measurements": list(self.allowed_kernel_measurements),
            "allowed_bootloader_measurements": list(self.allowed_bootloader_measurements),
            "ledger_schema_version": self.ledger_schema_version,
            "authority_schema_version": self.authority_schema_version,
            "min_security_epoch": self.min_security_epoch,
            "signatures": list(self.signatures),
        }

    # ---- verification helpers ----

    def verify_signatures(self, steward_pubkeys: dict[str, str]) -> bool:
        """Verify that at least the threshold number of steward signatures are valid.

        Concrete steward-cryptography is provided by the constitution/authority system.
        This method is a stub — each deployment fills in the verification logic.
        """
        if not self.signatures:
            return False
        # Each signature is expected to be a hex string; in production these are
        # verified against known steward public keys. For now we count non-empty sigs.
        valid = sum(
            1
            for sig in self.signatures
            if sig and isinstance(sig, str) and len(sig) > 10
        )
        return valid >= max(2, len(steward_pubkeys) // 2 + 1)


# ---- default manifest generation ----

def default_manifest_hash(*,
                          manifest_hash: str = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
                          parent_manifest_hash: Optional[str] = None,
                          constitution_hash: str = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
                          ) -> "TrustManifest":
    """Construct a minimal TrustManifest with genesis hashes.

    Deployments replace the hash values with real measurements at boot.
    """
    return TrustManifest(
        manifest_hash=manifest_hash,
        parent_manifest_hash=parent_manifest_hash,
        constitution_hash=constitution_hash,
        cen_runtime_hash="sha256:0000000000000000000000000000000000000000000000000000000000000000",
        classifier_hash="sha256:0000000000000000000000000000000000000000000000000000000000000000",
        invariant_bundle_hash="sha256:0000000000000000000000000000000000000000000000000000000000000000",
        mutation_gateway_hash="sha256:0000000000000000000000000000000000000000000000000000000000000000",
        allowed_pcrs={},
        allowed_kernel_measurements=(),
        allowed_bootloader_measurements=(),
        ledger_schema_version=1,
        authority_schema_version=1,
        min_security_epoch=1,
        signatures=(),
    )


# ---- ledger-key derivation ----

def manifest_ledger_key(manifest: TrustManifest) -> str:
    """Derive a ledger key from the manifest for Ring 3 persistence.

    Every receipt generated during a boot epoch carries this epoch key,
    making splice-resistant history possible (Ring 3 fix).
    """
    base = json.dumps(
        {
            "manifest_hash": manifest.manifest_hash,
            "constitution_hash": manifest.constitution_hash,
            "cen_runtime_hash": manifest.cen_runtime_hash,
            "min_security_epoch": manifest.min_security_epoch,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha3-256:" + __import__("hashlib").sha3_256(base.encode("utf-8")).hexdigest()