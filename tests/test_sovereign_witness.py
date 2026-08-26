"""Ring 6 — WitnessProvider contract tests (written before implementation).

Witness sovereignty: independent observers notarize the head of the
constitutional ledger so the machine owner cannot silently rewind history.

    Ring 1 Law -> 2 Execution -> 3 Continuity -> 4 Machine
        -> 5 Governance -> 6 Witnesses (external reality)

The witness record is deliberately minimal — it proves THAT history
existed at a point, never WHAT it contained:

    WitnessCheckpoint {
        node_id,
        security_epoch,      (ledger epoch_id)
        ledger_position,
        ledger_head_hash,
        constitution_hash,
        manifest_hash,
    }

Provider-neutral interface:
    publish(checkpoint) -> inclusion_proof
    verify(checkpoint, proof) -> bool

v1 ships a local file-backed provider; Rekor/remote witnesses implement
the same two methods later.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


def _checkpoint(**overrides) -> dict:
    fields = dict(
        node_id="node-alpha",
        security_epoch="sha3-256:" + "e" * 64,
        ledger_position=42,
        ledger_head_hash="sha3-256:" + "h" * 64,
        constitution_hash="sha256:" + "c" * 64,
        manifest_hash="sha256:" + "f" * 64,
    )
    fields.update(overrides)
    return fields


class WitnessProviderContractTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _provider(self):
        from src.sovereign_witness import LocalFileWitnessProvider

        return LocalFileWitnessProvider(witness_dir=self.dir)

    # ---- publish / verify round trip ----

    def test_publish_returns_inclusion_proof_that_verifies(self):
        provider = self._provider()
        cp = _checkpoint()
        proof = provider.publish(cp)
        self.assertTrue(provider.verify(cp, proof))

    def test_sequential_publishes_chain_positions(self):
        provider = self._provider()
        p1 = provider.publish(_checkpoint(ledger_position=1))
        p2 = provider.publish(_checkpoint(ledger_position=2))
        p3 = provider.publish(_checkpoint(ledger_position=3))
        self.assertEqual(p1["position"], 0)
        self.assertEqual(p2["position"], 1)
        self.assertEqual(p3["position"], 2)
        # Each proof links to the previous witness entry.
        self.assertEqual(proof_prev_hash(p2), entry_hash_of(p1))

    # ---- tamper / substitution ----

    def test_verify_refuses_checkpoint_substituted_after_signing(self):
        provider = self._provider()
        proof = provider.publish(_checkpoint())
        forged = _checkpoint(ledger_head_hash="sha3-256:" + "f" * 64)
        self.assertFalse(provider.verify(forged, proof))

    def test_verify_refuses_garbage_proof(self):
        provider = self._provider()
        cp = _checkpoint()
        self.assertFalse(provider.verify(cp, {}))
        self.assertFalse(provider.verify(cp, {"position": 99, "entry_hash": "nope"}))

    # ---- persistence across processes ----

    def test_new_provider_instance_sees_prior_publications(self):
        cp = _checkpoint()
        p1 = self._provider().publish(cp)
        fresh = self._provider()
        self.assertTrue(fresh.verify(cp, p1))

    def test_witness_log_is_readable_and_ordered(self):
        provider = self._provider()
        for i in range(3):
            provider.publish(_checkpoint(ledger_position=i))
        entries = provider.entries()
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0]["checkpoint"]["ledger_position"], 0)

    # ---- anti-rollback query surface ----

    def test_latest_checkpoint_query(self):
        provider = self._provider()
        self.assertIsNone(provider.latest())
        published = provider.publish(_checkpoint(ledger_position=7))
        latest = provider.latest()
        self.assertEqual(latest["checkpoint_hash"], published["checkpoint_hash"])
        self.assertEqual(latest["checkpoint"]["ledger_position"], 7)

    def test_rollback_detected_when_local_head_behind_witness(self):
        """The core Ring-6 promise: a rewound node is detectable."""
        provider = self._provider()
        provider.publish(_checkpoint(ledger_position=50))
        # Node claims an older head than the witness remembers.
        rolled_back = _checkpoint(ledger_position=10)
        verdict = provider.check_rollback(
            local_ledger_head="sha3-256:" + "old" * 21 + "o",
            local_ledger_position=10,
        )
        self.assertTrue(verdict["rollback_suspected"])
        self.assertGreater(verdict["witnessed_position"], 10)


def proof_prev_hash(proof: dict) -> str:
    return proof.get("prev_entry_hash", "")


def entry_hash_of(proof: dict) -> str:
    return proof.get("entry_hash", "")


if __name__ == "__main__":
    unittest.main()
