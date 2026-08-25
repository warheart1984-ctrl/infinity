"""Sovereignty stack module tests: TrustManifest, CommitCertificate,
ReadOnlyView capability separation.

The core property under test: every accepted state transition carries
enough evidence to prove all lower sovereignty rings were valid at the
moment of commit — and the certificate validation refuses any break in
the ring inheritance chain.
"""

import unittest

from src.commit_certificate import CommitCertificate
from src.cen_governance_bridge import CenGovernanceBridge
from src.mutation_capabilities import CapabilityRegistry, MutationProvenance, ReadOnlyView
from src.trust_manifest import TrustManifest


def _manifest(**overrides) -> TrustManifest:
    base = dict(
        manifest_hash="sha256:" + "11" * 32,
        parent_manifest_hash=None,
        constitution_hash="sha256:" + "22" * 32,
        cen_runtime_hash="sha256:" + "33" * 32,
        classifier_hash="sha256:" + "44" * 32,
        invariant_bundle_hash="sha256:" + "55" * 32,
        mutation_gateway_hash="sha256:" + "66" * 32,
        allowed_pcrs={0: "aa", 7: "bb"},
        allowed_kernel_measurements=("kernel-good",),
        allowed_bootloader_measurements=("bootloader-good",),
        ledger_schema_version=2,
        authority_schema_version=1,
        min_security_epoch=14,
        signatures=("steward1sig0000", "steward2sig0000"),
    )
    base.update(overrides)
    return TrustManifest(**base)


def _cert(**overrides) -> CommitCertificate:
    base = dict(
        constitution_hash="sha256:" + "22" * 32,
        invariant_bundle_hash="sha256:" + "55" * 32,
        caller_principal="operator:1234",
        authority_proof="sha3-256:" + "a" * 64,
        runtime_measurement="sha256:runtime",
        epoch_id="epoch-1",
        previous_receipt_hash="sha3-256:" + "p" * 64,
        monotonic_position=7,
        machine_attestation="tpm-quote-abc",
        trust_manifest_hash="sha256:" + "11" * 32,
        governance_proof="quorum-2of3",
        resulting_state_hash="sha256:" + "s" * 64,
    )
    base.update(overrides)
    return CommitCertificate(**base)


class TestTrustManifest(unittest.TestCase):
    def test_json_roundtrip_is_lossless(self):
        m = _manifest()
        restored = TrustManifest.from_json(m.to_json())
        self.assertEqual(restored, m)

    def test_frozen_manifest_rejects_mutation(self):
        m = _manifest()
        with self.assertRaises(Exception):
            m.constitution_hash = "tampered"

    def test_signature_threshold_requires_quorum(self):
        m = _manifest(signatures=())
        self.assertFalse(m.verify_signatures({"sk1": "pub1"}))
        m2 = _manifest(signatures=("steward1sig0000", "steward2sig0000"))
        self.assertTrue(m2.verify_signatures({"sk1": "pub1", "sk2": "pub2", "sk3": "pub3"}))


class TestCommitCertificateChain(unittest.TestCase):
    def setUp(self):
        self.manifest = _manifest()
        self.measurements = {"epoch_id": "epoch-1"}

    def test_valid_certificate_passes(self):
        ok, reason = _cert().validate(
            last_certificate=None, trust_manifest=self.manifest,
            current_measurements=self.measurements,
        )
        self.assertTrue(ok, reason)

    def test_chain_break_refused(self):
        prev = _cert(monotonic_position=6)
        bad_prev_hash = "sha3-256:" + "f" * 64
        cert = _cert(previous_receipt_hash=bad_prev_hash)
        ok, reason = cert.validate(
            last_certificate=prev, trust_manifest=self.manifest,
            current_measurements=self.measurements,
        )
        # prev's resulting_state_hash differs from what cert claims followed
        self.assertFalse(ok)
        self.assertIn("chain break", reason)

    def test_monotonic_regression_refused(self):
        prev = _cert(monotonic_position=9, resulting_state_hash=_cert().previous_receipt_hash)
        cert = _cert(monotonic_position=8)
        ok, reason = cert.validate(
            last_certificate=prev, trust_manifest=self.manifest,
            current_measurements=self.measurements,
        )
        self.assertFalse(ok)
        self.assertIn("monotonic position regression", reason)

    def test_epoch_mismatch_refused(self):
        cert = _cert(epoch_id="epoch-0")
        ok, reason = cert.validate(
            last_certificate=None, trust_manifest=self.manifest,
            current_measurements=self.measurements,
        )
        self.assertFalse(ok)
        self.assertIn("epoch mismatch", reason)

    def test_constitution_mismatch_with_manifest_refused(self):
        cert = _cert(constitution_hash="sha256:" + "ee" * 32)
        ok, reason = cert.validate(
            last_certificate=None, trust_manifest=self.manifest,
            current_measurements=self.measurements,
        )
        self.assertFalse(ok)
        self.assertIn("constitution hash mismatch", reason)

    def test_empty_authority_proof_refused(self):
        cert = _cert(authority_proof="")
        ok, reason = cert.validate(
            last_certificate=None, trust_manifest=self.manifest,
            current_measurements=self.measurements,
        )
        self.assertFalse(ok)
        self.assertIn("authority_proof", reason)


class TestReadOnlyViewCapabilitySeparation(unittest.TestCase):
    def test_mutation_through_view_raises(self):
        view = ReadOnlyView(
            registry_snapshot=_manifest(),
            ledger_head_hash="sha3-256:head",
            epoch_id="epoch-1",
        )
        with self.assertRaises(RuntimeError):
            view.mutate(payload={"memory": 90})

    def test_view_exposes_only_read_accessors(self):
        m = _manifest()
        view = ReadOnlyView(registry_snapshot=m, ledger_head_hash="sha3-256:head", epoch_id="epoch-1")
        self.assertEqual(view.registry(), m)
        self.assertEqual(view.last_receipt_hash(), "sha3-256:head")
        self.assertEqual(view.epoch(), "epoch-1")

    def test_capability_registry_detects_nonce_replay_within_epoch(self):
        reg = CapabilityRegistry()
        prov = MutationProvenance(
            caller_pid=100, caller_binary_hash="sha256:bin",
            authority_token={"tokenId": "vt-1"}, law_bundle_id="b1", nonce="n-1",
        )
        reg.register(prov, epoch_id="epoch-1")
        self.assertTrue(reg.check_nonce("epoch-1", "n-1"))
        self.assertFalse(reg.check_nonce("epoch-2", "n-1"))  # fresh epoch resets
        self.assertEqual(reg.provenance_for(100), prov)


class TestBridgeEmitsCommitCertificates(unittest.TestCase):
    def test_approved_commit_carries_ring_evidence(self):
        bridge = CenGovernanceBridge()
        result = bridge.gate_commit(
            transition_id="transition:cert-check",
            transition_type="runtime_action",
            payload={"continuity": 74},
            requested_capabilities=["state:commit"],
            granted_capabilities=["workflow:execute", "state:commit"],
        )
        self.assertEqual(result["outcome"], "approved")
        cert = result["commitCertificate"]
        for field in (
            "constitution_hash", "invariant_bundle_hash", "caller_principal",
            "authority_proof", "epoch_id", "previous_receipt_hash",
            "monotonic_position", "trust_manifest_hash", "resulting_state_hash",
        ):
            self.assertIn(field, cert)
        # Ring 3 binding: the certificate chains to the enforcement receipt
        self.assertEqual(cert["previous_receipt_hash"], result["cen_receipt_hash"])
        # Result state binds exactly the frozen approved payload
        from src.cen_governance_bridge import _payload_hash
        self.assertEqual(cert["resulting_state_hash"], _payload_hash(result["frozen_payload"]))

    def test_monotonic_position_increases_across_approvals(self):
        bridge = CenGovernanceBridge()
        positions = []
        for i in range(3):
            r = bridge.gate_commit(
                transition_id=f"transition:mono-{i}",
                transition_type="runtime_action",
                payload={"continuity": 74},
                requested_capabilities=["state:commit"],
                granted_capabilities=["state:commit"],
            )
            positions.append(r["commitCertificate"]["monotonic_position"])
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(len(set(positions)), 3)

    def test_denials_do_not_advance_monotonic_position(self):
        bridge = CenGovernanceBridge()
        ok = bridge.gate_commit(
            transition_id="transition:mono-a", transition_type="runtime_action",
            payload={"continuity": 74}, requested_capabilities=["state:commit"],
            granted_capabilities=["state:commit"],
        )
        first = ok["commitCertificate"]["monotonic_position"]
        denied = bridge.gate_commit(
            transition_id="transition:mono-b", transition_type="law_mutation",
            payload={"memory": 90}, requested_capabilities=["law:mutate"],
            granted_capabilities=["law:mutate"], authority_token=None,
        )
        self.assertEqual(denied["outcome"], "denied")
        again = bridge.gate_commit(
            transition_id="transition:mono-c", transition_type="runtime_action",
            payload={"continuity": 74}, requested_capabilities=["state:commit"],
            granted_capabilities=["state:commit"],
        )
        self.assertEqual(again["commitCertificate"]["monotonic_position"], first + 1)


if __name__ == "__main__":
    unittest.main()
