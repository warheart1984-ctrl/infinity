"""Sovereign state reader — read-only middleware over the constitutional stack.

Mythic: the ledger may be witnessed, never negotiated.
Engineering: exposes ledger head, boot epoch, recent verdicts, and commit
certificates through ReadOnlyView semantics. There is NO write path here —
not disabled, ABSENT. The class defines no mutation methods, holds no
bridge references that could gate commits, and sanitizes every receipt to
an explicit field allowlist before it leaves the boundary.

Ring 2 alignment: this module runs in any process (api, console, frontend
backend-for-frontend) because it needs exactly what a ReadOnlyView gets —
read access to the receipt chain, nothing else.
"""

from __future__ import annotations

from typing import Any

from src.mutation_capabilities import ReadOnlyView
from src.trust_manifest import TrustManifest

# Explicit allowlist: if a receipt gains new fields later, they do NOT leak
# through this boundary until someone consciously adds them here.
_RECEIPT_PUBLIC_FIELDS = (
    "receiptId",
    "transitionId",
    "transitionType",
    "actor",
    "verdict",
    "action",
    "reasonCode",
    "reasonDetail",
    "category",
    "issuedAt",
    "receiptHash",
    "previousReceiptHash",
    "authorityTokenId",
)

_CERTIFICATE_PUBLIC_FIELDS = (
    "constitution_hash",
    "invariant_bundle_hash",
    "caller_principal",
    "authority_proof",
    "runtime_measurement",
    "epoch_id",
    "previous_receipt_hash",
    "monotonic_position",
    "machine_attestation",
    "trust_manifest_hash",
    "governance_proof",
    "resulting_state_hash",
)


def _allowlisted(source: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {key: source[key] for key in fields if key in source}


def genesis_manifest_view() -> TrustManifest:
    """Placeholder manifest until Ring 4's sealed backend supplies a real one."""
    return TrustManifest(
        manifest_hash="sha256:" + "00" * 32,
        parent_manifest_hash=None,
        constitution_hash="sha256:" + "00" * 32,
        cen_runtime_hash="sha256:unmeasured",
        classifier_hash="sha256:unmeasured",
        invariant_bundle_hash="sha256:unmeasured",
        mutation_gateway_hash="sha256:unmeasured",
        allowed_pcrs={},
        allowed_kernel_measurements=(),
        allowed_bootloader_measurements=(),
        ledger_schema_version=1,
        authority_schema_version=1,
        min_security_epoch=0,
        signatures=(),
    )


class SovereignStateReader:
    """Read-only projection of constitutional state for middleware/frontend.

    Construction takes anything that can supply receipts — typically the
    process-local bridge singleton — but retains NO reference to gating
    machinery. Callers cannot reach gate_commit through this object.
    """

    def __init__(self, *, receipts_provider, certificates_provider=None,
                 epoch_id: str | None = None,
                 manifest: TrustManifest | None = None):
        self._receipts_provider = receipts_provider
        self._certificates_provider = certificates_provider or (lambda: {})
        self._manifest = manifest or genesis_manifest_view()
        self._epoch_override = epoch_id

    # ---- internal reads -------------------------------------------------

    def _receipts(self) -> list[dict[str, Any]]:
        receipts = self._receipts_provider()
        return list(receipts) if receipts else []

    def _epoch_id(self) -> str:
        if self._epoch_override is not None:
            return self._epoch_override
        latest_cert = self._latest_certificate_raw()
        if latest_cert is not None:
            return str(latest_cert.get("epoch_id") or "genesis")
        return "genesis"

    def _latest_certificate_raw(self) -> dict[str, Any] | None:
        index = self._certificates_provider() or {}
        for receipt in reversed(self._receipts()):
            cert = index.get(receipt.get("receiptId")) or receipt.get("commitCertificate")
            if isinstance(cert, dict):
                return cert
        return None

    def _certificate_for(self, receipt: dict[str, Any]) -> dict[str, Any] | None:
        index = self._certificates_provider() or {}
        cert = index.get(receipt.get("receiptId")) or receipt.get("commitCertificate")
        return cert if isinstance(cert, dict) else None

    # ---- public read-only projections ------------------------------------

    def ledger_head(self) -> dict[str, Any]:
        """Chain tip: last receipt hash, position, continuity flags."""
        receipts = self._receipts()
        if not receipts:
            return {
                "empty": True,
                "ledger_head_hash": None,
                "receipt_count": 0,
                "monotonic_position": None,
                "chain_intact": True,
            }
        head = receipts[-1]
        chain_intact = all(
            receipts[i]["receiptHash"] == receipts[i + 1].get("previousReceiptHash")
            for i in range(len(receipts) - 1)
        )
        cert = (self._certificates_provider() or {}).get(head.get("receiptId")) \
            or head.get("commitCertificate") or {}
        return {
            "empty": False,
            "ledger_head_hash": head.get("receiptHash"),
            "receipt_count": len(receipts),
            "monotonic_position": cert.get("monotonic_position"),
            "chain_intact": bool(chain_intact),
        }

    def epoch(self) -> dict[str, Any]:
        """Current boot epoch under which recent receipts were certified."""
        return {"epoch_id": self._epoch_id(), "manifest_hash": self._manifest.manifest_hash}

    def readonly_view(self) -> ReadOnlyView:
        """The Ring-2 sanctioned object: a frozen view with no write path."""
        head = self.ledger_head()
        return ReadOnlyView(
            registry_snapshot=self._manifest,
            ledger_head_hash=head["ledger_head_hash"] or "",
            epoch_id=self._epoch_id(),
        )

    def recent_verdicts(self, limit: int = 25) -> list[dict[str, Any]]:
        """Most recent sanitized receipts, newest first."""
        limit = max(0, min(int(limit), 200))
        receipts = self._receipts()
        out = []
        for receipt in reversed(receipts[-limit:]):
            entry = _allowlisted(receipt, _RECEIPT_PUBLIC_FIELDS)
            cert = self._certificate_for(receipt)
            if cert is not None:
                entry["certificate"] = _allowlisted(cert, _CERTIFICATE_PUBLIC_FIELDS)
            out.append(entry)
        return out

    def verdict_by_receipt(self, receipt_id: str) -> dict[str, Any] | None:
        """One sanitized receipt by id, including its certificate if present."""
        for receipt in self._receipts():
            if receipt.get("receiptId") == receipt_id:
                entry = _allowlisted(receipt, _RECEIPT_PUBLIC_FIELDS)
                cert = self._certificate_for(receipt)
                if cert is not None:
                    entry["certificate"] = _allowlisted(cert, _CERTIFICATE_PUBLIC_FIELDS)
                return entry
        return None

    def summary(self) -> dict[str, Any]:
        """Single consolidated snapshot for dashboard initial load."""
        head = self.ledger_head()
        verdicts = self.recent_verdicts(limit=10)
        allowed = sum(1 for v in verdicts if v.get("verdict") == "ALLOW")
        denied = sum(1 for v in verdicts if v.get("verdict") == "DENY")
        return {
            "ledger": head,
            "epoch": self.epoch(),
            "recent": {
                "count": len(verdicts),
                "allowed": allowed,
                "denied": denied,
            },
            "view": {
                "kind": "ReadOnlyView",
                "mutation_capable": False,
            },
        }
