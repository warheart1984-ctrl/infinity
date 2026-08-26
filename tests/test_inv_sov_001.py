"""INV-SOV-001 — no ring attests validity without binding every lower ring.

These tests were written BEFORE src/sovereign_invariants.py exists.
Each refusal pins one inheritance edge:

    R1 Law         constitution_hash + invariant_bundle_hash
    R2 Execution   caller_principal + authority_proof + runtime_measurement
    R3 Continuity  epoch_id + previous_receipt_hash + monotonic_position
    R4 Machine     machine_attestation + trust_manifest_hash
    R5 Governance  governance_proof

Ring edges under test:
- R2->R1  law hashes must match the active manifest
- R2->R4  runtime measurement must be the manifest-certified runtime
- R3      certificate must bind the open epoch and the live ledger head
- R3      monotonic position must advance
- R3/R5   post-discontinuity commits require a RECOVERY-opened epoch
- R4->R3  manifest binding + machine attestation presence
- R5      governance proof presence
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.commit_certificate import CommitCertificate
from src.epoch_ledger import EpochLedger
from src.trust_manifest import TrustManifest

CONSTITUTION = "sha256:" + "c" * 64
RUNTIME_HASH = "sha256:" + "r" * 64
INV_BUNDLE = "sha256:" + "b" * 64


def build_manifest(**overrides) -> TrustManifest:
    fields = dict(
        manifest_hash="sha256:" + "f" * 64,
        parent_manifest_hash=None,
        constitution_hash=CONSTITUTION,
        cen_runtime_hash=RUNTIME_HASH,
        classifier_hash="sha256:" + "k" * 64,
        invariant_bundle_hash=INV_BUNDLE,
        mutation_gateway_hash="sha256:" + "g" * 64,
        allowed_pcrs={0: "sha256:" + "0" * 64},
        allowed_kernel_measurements=("sha256:" + "K" * 64,),
        allowed_bootloader_measurements=("sha256:" + "B" * 64,),
        ledger_schema_version=1,
        authority_schema_version=1,
        min_security_epoch=1,
        signatures=("sig-steward-1-aaaaaaaaaa", "sig-steward-2-bbbbbbbbbb"),
    )
    fields.update(overrides)
    return TrustManifest(**fields)


class SovereignStackFixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.manifest = build_manifest()
        self.ledger = EpochLedger(self.dir)
        self.ledger.boot(
            constitution_hash=self.manifest.constitution_hash,
            runtime_measurement=self.manifest.cen_runtime_hash,
            machine_measurement=self.manifest.allowed_pcrs[0],
        )
        self.addCleanup(self._tmp.cleanup)

    def make_cert(self, **overrides) -> CommitCertificate:
        fields = dict(
            # R1 Law
            constitution_hash=self.manifest.constitution_hash,
            invariant_bundle_hash=self.manifest.invariant_bundle_hash,
            # R2 Execution
            caller_principal="middleware:pid:4242",
            authority_proof="sha3-256:" + "a" * 64,
            runtime_measurement=self.manifest.cen_runtime_hash,
            # R3 Continuity
            epoch_id=self.ledger.current_epoch_id,
            previous_receipt_hash=self.ledger.head_hash,
            monotonic_position=self.ledger.position + 1,
            # R4 Machine
            machine_attestation="tpm-quote:" + "m" * 48,
            trust_manifest_hash=self.manifest.manifest_hash,
            # R5 Governance
            governance_proof="quorum:2-of-3",
            # Result
            resulting_state_hash="sha3-256:" + "9" * 64,
        )
        fields.update(overrides)
        return CommitCertificate(**fields)


class TestInvSov001(SovereignStackFixture):
    """Refusal pins — written before the enforcement module existed."""

    def test_module_exists_with_enforce_entrypoint(self):
        # The contract this suite pins: one function, one verdict shape.
        from src.sovereignty_invariants import enforce_inv_sov_001  # noqa: F401

    # ---- happy path ----

    def test_fully_bound_certificate_passes(self):
        from src.sovereignty_invariants import enforce_inv_sov_001

        verdict = enforce_inv_sov_001(
            self.make_cert(), trust_manifest=self.manifest, ledger=self.ledger
        )
        self.assertTrue(verdict.allowed, verdict.violations)

    # ---- R2 -> R1: execution binds law ----

    def test_r2_r1_constitution_mismatch_refused(self):
        from src.sovereignty_invariants import enforce_inv_sov_001

        cert = self.make_cert(constitution_hash="sha256:" + "d" * 64)
        verdict = enforce_inv_sov_001(cert, trust_manifest=self.manifest, ledger=self.ledger)
        self.assertFalse(verdict.allowed)
        self.assertTrue(any("R2->R1" in v and "constitution" in v for v in verdict.violations))

    def test_r2_r1_invariant_bundle_mismatch_refused(self):
        from src.sovereignty_invariants import enforce_inv_sov_001

        cert = self.make_cert(invariant_bundle_hash="sha256:" + "e" * 64)
        verdict = enforce_inv_sov_001(cert, trust_manifest=self.manifest, ledger=self.ledger)
        self.assertFalse(verdict.allowed)
        self.assertTrue(any("R2->R1" in v and "invariant" in v for v in verdict.violations))

    def test_r2_r4_runtime_measurement_not_manifest_certified_refused(self):
        from src.sovereignty_invariants import enforce_inv_sov_001

        cert = self.make_cert(runtime_measurement="sha256:" + "z" * 64)
        verdict = enforce_inv_sov_001(cert, trust_manifest=self.manifest, ledger=self.ledger)
        self.assertFalse(verdict.allowed)
        self.assertTrue(any("runtime" in v.lower() for v in verdict.violations))

    def test_r2_authority_proof_required(self):
        from src.sovereignty_invariants import enforce_inv_sov_001

        cert = self.make_cert(authority_proof="")
        verdict = enforce_inv_sov_001(cert, trust_manifest=self.manifest, ledger=self.ledger)
        self.assertFalse(verdict.allowed)
        self.assertTrue(any("authority" in v.lower() for v in verdict.violations))

    # ---- R3: continuity binds execution + law ----

    def test_r3_wrong_epoch_refused(self):
        from src.sovereignty_invariants import enforce_inv_sov_001

        cert = self.make_cert(epoch_id="sha3-256:" + "0" * 63 + "0")
        verdict = enforce_inv_sov_001(cert, trust_manifest=self.manifest, ledger=self.ledger)
        self.assertFalse(verdict.allowed)
        self.assertTrue(any("epoch" in v.lower() for v in verdict.violations))

    def test_r3_stale_head_link_refused(self):
        from src.sovereignty_invariants import enforce_inv_sov_001

        stale_head = self.ledger.head_hash
        self.ledger.append_commit(
            payload_digest="sha3-256:" + "1" * 64,
            resulting_state_hash="sha3-256:" + "2" * 64,
        )
        cert = self.make_cert(previous_receipt_hash=stale_head)
        from src.sovereignty_invariants import enforce_inv_sov_001

        verdict = enforce_inv_sov_001(cert, trust_manifest=self.manifest, ledger=self.ledger)
        self.assertFalse(verdict.allowed)
        self.assertTrue(any("previous" in v.lower() or "head" in v.lower() for v in verdict.violations))

    def test_r3_monotonic_regression_refused(self):
        from src.sovereignty_invariants import enforce_inv_sov_001

        cert = self.make_cert(monotonic_position=self.ledger.position)
        verdict = enforce_inv_sov_001(cert, trust_manifest=self.manifest, ledger=self.ledger)
        self.assertFalse(verdict.allowed)
        self.assertTrue(any("monotonic" in v.lower() for v in verdict.violations))

    # ---- R4: machine binds continuity + execution + law ----

    def test_r4_trust_manifest_hash_mismatch_refused(self):
        from src.sovereignty_invariants import enforce_inv_sov_001

        cert = self.make_cert(trust_manifest_hash="sha256:" + "7" * 64)
        verdict = enforce_inv_sov_001(cert, trust_manifest=self.manifest, ledger=self.ledger)
        self.assertFalse(verdict.allowed)
        self.assertTrue(any("manifest" in v.lower() for v in verdict.violations))

    def test_r4_machine_attestation_required(self):
        from src.sovereignty_invariants import enforce_inv_sov_001

        cert = self.make_cert(machine_attestation="")
        verdict = enforce_inv_sov_001(cert, trust_manifest=self.manifest, ledger=self.ledger)
        self.assertFalse(verdict.allowed)
        self.assertTrue(any("attestation" in v.lower() for v in verdict.violations))

    # ---- R5: governance binds everything beneath ----

    def test_r5_governance_proof_required(self):
        from src.sovereignty_invariants import enforce_inv_sov_001

        cert = self.make_cert(governance_proof="")
        verdict = enforce_inv_sov_001(cert, trust_manifest=self.manifest, ledger=self.ledger)
        self.assertFalse(verdict.allowed)
        self.assertTrue(any("governance" in v.lower() for v in verdict.violations))

    def test_post_discontinuity_requires_recovery_epoch(self):
        from src.sovereignty_invariants import enforce_inv_sov_001

        self.ledger.declare_trust_discontinuity(reason="TPM NV rollback detected")
        cert = self.make_cert()
        verdict = enforce_inv_sov_001(cert, trust_manifest=self.manifest, ledger=self.ledger)
        self.assertFalse(verdict.allowed)
        self.assertTrue(any("recover" in v.lower() for v in verdict.violations))

    def test_recovered_epoch_admits_commits_again(self):
        from src.sovereignty_invariants import enforce_inv_sov_001

        self.ledger.declare_trust_discontinuity(reason="TPM NV rollback detected")
        self.ledger.open_recovery_epoch(
            constitution_hash=self.manifest.constitution_hash,
            runtime_measurement=self.manifest.cen_runtime_hash,
            machine_measurement=self.manifest.allowed_pcrs[0],
            recovery_reason="quorum-approved rebuild",
        )
        cert = self.make_cert(governance_proof="recovery-quorum:2-of-3")
        verdict = enforce_inv_sov_001(cert, trust_manifest=self.manifest, ledger=self.ledger)
        self.assertTrue(verdict.allowed, verdict.violations)

    # ---- gate-then-land ----

    def test_certified_commit_lands_receipt_binding_the_certificate(self):
        from src.sovereignty_invariants import commit_certified

        cert = self.make_cert()
        verdict, receipt = commit_certified(
            self.ledger, cert, trust_manifest=self.manifest
        )
        self.assertTrue(verdict.allowed)
        self.assertEqual(receipt["resulting_state_hash"], cert.resulting_state_hash)
        # The persisted receipt carries the certificate's own hash as payload
        # digest: the ledger contains the evidence of admissibility.
        self.assertIn(cert.previous_hash(), str(receipt["payload_digest"]))
        head_before = self.ledger.head_hash

        # A second certificate chains onto the first.
        cert2 = self.make_cert(
            previous_receipt_hash=head_before,
            monotonic_position=self.ledger.position + 1,
            resulting_state_hash="sha3-256:" + "8" * 64,
        )
        verdict2, _ = commit_certified(self.ledger, cert2, trust_manifest=self.manifest)
        self.assertTrue(verdict2.allowed, verdict2.violations)

    def test_refused_commit_lands_nothing(self):
        from src.sovereignty_invariants import commit_certified

        before = self.ledger.position
        cert = self.make_cert(monotonic_position=-5)
        verdict, receipt = commit_certified(self.ledger, cert, trust_manifest=self.manifest)
        self.assertFalse(verdict.allowed)
        self.assertEqual(receipt, {})
        self.assertEqual(self.ledger.position, before)


if __name__ == "__main__":
    unittest.main()
