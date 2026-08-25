"""Ring 3 tests — persistent epoch ledger invariants."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.epoch_ledger import (
    GENESIS_PREV_HASH,
    EpochLedger,
    EpochLedgerError,
    LedgerReceipt,
    derive_epoch_id,
)

BOOT = {
    "constitution_hash": "sha3-256:" + "a" * 64,
    "runtime_measurement": "sha3-256:" + "b" * 64,
    "machine_measurement": "sha3-256:" + "c" * 64,
}


class EpochLedgerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    # ---- genesis + chain integrity ----

    def test_genesis_boot_opens_epoch_and_chain_verifies(self):
        ledger = EpochLedger(self.dir)
        boot = ledger.boot(**BOOT)
        self.assertTrue(boot["epoch_id"])
        self.assertEqual(boot["prev_epoch_id"], "")
        self.assertFalse(boot["continuity_broken"])

        ok, reason = ledger.load_and_verify()
        self.assertTrue(ok, reason)
        types = [e.receipt_type for e in ledger.entries()]
        self.assertEqual(types, ["EPOCH_OPEN"])
        first = ledger.entries()[0]
        self.assertEqual(first.prev_hash, GENESIS_PREV_HASH)
        self.assertEqual(ledger.current_epoch_id, boot["epoch_id"])

    def test_commits_chain_and_verify(self):
        ledger = EpochLedger(self.dir)
        ledger.boot(**BOOT)
        for i in range(5):
            doc = ledger.append_commit(
                payload_digest=f"sha3-256:{i:064x}",
                resulting_state_hash=f"sha3-256:{(i + 1):064x}",
                authority_ref="vt-test",
            )
            self.assertEqual(doc["receipt_type"], "COMMIT")
        ok, reason = ledger.load_and_verify()
        self.assertTrue(ok, reason)
        self.assertEqual(ledger.position, 6)
        entries = ledger.entries()
        for prev, cur in zip(entries, entries[1:]):
            self.assertEqual(cur.prev_hash, prev.compute_hash())
        self.assertEqual(entries[-1].epoch_id, ledger.current_epoch_id)

    def test_commit_without_boot_refused(self):
        ledger = EpochLedger(self.dir)
        with self.assertRaises(EpochLedgerError):
            ledger.append_commit(
                payload_digest="sha3-256:" + "0" * 64,
                resulting_state_hash="sha3-256:" + "1" * 64,
            )

    # ---- tamper / splice resistance ----

    def test_tampered_line_detected_on_load(self):
        ledger = EpochLedger(self.dir)
        ledger.boot(**BOOT)
        ledger.append_commit(
            payload_digest="sha3-256:" + "1" * 64,
            resulting_state_hash="sha3-256:" + "2" * 64,
        )
        path = self.dir / "sovereign_epoch_ledger.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines()
        doc = json.loads(lines[0])
        doc["payload_digest"] = "sha3-256:" + "f" * 64
        lines[0] = json.dumps(doc, sort_keys=True, separators=(",", ":"))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        fresh = EpochLedger(self.dir)
        ok, reason = fresh.load_and_verify()
        self.assertFalse(ok)
        self.assertIn("hash mismatch", reason)

    def test_spliced_history_detected_via_chain_break(self):
        ledger_a = EpochLedger(self.dir)
        ledger_a.boot(**BOOT)
        ledger_a.append_commit(
            payload_digest="sha3-256:" + "1" * 64,
            resulting_state_hash="sha3-256:" + "2" * 64,
        )
        path = self.dir / "sovereign_epoch_ledger.jsonl"
        original_lines = path.read_text(encoding="utf-8").splitlines()

        # Simulate an attacker splicing a foreign valid receipt onto the tail
        foreign_receipt = LedgerReceipt(
            position=99,
            prev_hash=GENESIS_PREV_HASH,
            epoch_id="sha3-256:" + "9" * 64,
            receipt_type="COMMIT",
            nonce="forged-nonce",
            timestamp_utc="2026-01-01T00:00:00+00:00",
            payload_digest="sha3-256:" + "8" * 64,
            authority_ref="",
            resulting_state_hash="sha3-256:" + "7" * 64,
        ).to_json()
        path.write_text(
            "\n".join(original_lines) + "\n" + json.dumps(foreign_receipt, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        fresh = EpochLedger(self.dir)
        ok, reason = fresh.load_and_verify()
        self.assertFalse(ok)
        self.assertIn("chain break", reason)

    def test_nonce_replay_in_file_refused_at_load(self):
        ledger = EpochLedger(self.dir)
        ledger.boot(**BOOT)
        ledger.append_commit(
            payload_digest="sha3-256:" + "1" * 64,
            resulting_state_hash="sha3-256:" + "2" * 64,
        )
        path = self.dir / "sovereign_epoch_ledger.jsonl"
        lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        last = json.loads(lines[-1])
        genesis_nonce = json.loads(lines[0])["nonce"]

        # Forge a well-linked tail receipt that replays the genesis nonce:
        # the chain link is valid, so the nonce-replay check is what refuses.
        forged = LedgerReceipt(
            position=int(last["position"]) + 1,
            prev_hash=str(last["hash"]),
            epoch_id=last["epoch_id"],
            receipt_type="COMMIT",
            nonce=genesis_nonce,
            timestamp_utc="2026-01-01T00:00:00+00:00",
            payload_digest="sha3-256:" + "8" * 64,
            authority_ref="",
            resulting_state_hash="sha3-256:" + "7" * 64,
        ).to_json()
        path.write_text(
            "\n".join(lines) + "\n" + json.dumps(forged, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

        fresh = EpochLedger(self.dir)
        ok, reason = fresh.load_and_verify()
        self.assertFalse(ok)
        self.assertIn("replay", reason)

    # ---- continuity semantics ----

    def test_clean_shutdown_then_boot_is_orderly(self):
        ledger = EpochLedger(self.dir)
        first_boot = ledger.boot(**BOOT)
        ledger.shutdown()
        second_boot = EpochLedger(self.dir).boot(**{**BOOT, "boot_nonce": "n2"})
        self.assertNotEqual(first_boot["epoch_id"], second_boot["epoch_id"])
        self.assertFalse(second_boot["unexpected_reboot"])
        types = [e.receipt_type for e in EpochLedger(self.dir).entries()]
        self.assertEqual(types, ["EPOCH_OPEN", "SHUTDOWN", "EPOCH_OPEN"])

    def test_crash_produces_unexpected_reboot_event(self):
        ledger = EpochLedger(self.dir)
        ledger.boot(**BOOT)
        ledger.append_commit(
            payload_digest="sha3-256:" + "1" * 64,
            resulting_state_hash="sha3-256:" + "2" * 64,
        )
        # no shutdown — simulate kill -9 by booting a fresh instance
        rebooted = EpochLedger(self.dir).boot(**{**BOOT, "boot_nonce": "after-crash"})
        self.assertTrue(rebooted["unexpected_reboot"])
        types = [e.receipt_type for e in EpochLedger(self.dir).entries()]
        self.assertEqual(types, ["EPOCH_OPEN", "COMMIT", "UNEXPECTED_REBOOT", "EPOCH_OPEN"])

    def test_epoch_binding_prevents_cross_epoch_append_confusion(self):
        ledger = EpochLedger(self.dir)
        b1 = ledger.boot(**BOOT)
        ledger.shutdown()
        b2 = ledger.boot(**{**BOOT, "boot_nonce": "second"})
        self.assertNotEqual(b1["epoch_id"], b2["epoch_id"])
        doc = ledger.append_commit(
            payload_digest="sha3-256:" + "3" * 64,
            resulting_state_hash="sha3-256:" + "4" * 64,
        )
        self.assertEqual(doc["epoch_id"], b2["epoch_id"])

    def test_derive_epoch_id_changes_with_any_input(self):
        base = derive_epoch_id(
            prev_epoch_id="", constitution_hash="c", runtime_measurement="r",
            machine_measurement="m", boot_nonce="n",
        )
        variants = [
            derive_epoch_id(prev_epoch_id="x", constitution_hash="c", runtime_measurement="r", machine_measurement="m", boot_nonce="n"),
            derive_epoch_id(prev_epoch_id="", constitution_hash="c2", runtime_measurement="r", machine_measurement="m", boot_nonce="n"),
            derive_epoch_id(prev_epoch_id="", constitution_hash="c", runtime_measurement="r2", machine_measurement="m", boot_nonce="n"),
            derive_epoch_id(prev_epoch_id="", constitution_hash="c", runtime_measurement="r", machine_measurement="m2", boot_nonce="n"),
            derive_epoch_id(prev_epoch_id="", constitution_hash="c", runtime_measurement="r", machine_measurement="m", boot_nonce="n2"),
        ]
        for variant in variants:
            self.assertNotEqual(base, variant)

    # ---- discontinuity / recovery ----

    def test_discontinuity_irrevocable_and_recovery_required(self):
        ledger = EpochLedger(self.dir)
        ledger.boot(**BOOT)
        self.assertFalse(ledger.continuity_broken)
        ledger.declare_trust_discontinuity(reason="TPM NV counter rollback detected")
        self.assertTrue(ledger.continuity_broken)

        # A brand-new process loading the same file still sees broken continuity
        fresh = EpochLedger(self.dir)
        fresh.load_and_verify()
        self.assertTrue(fresh.continuity_broken)

        # Plain boot after discontinuity must NOT silently claim continuity.
        # The only lawful way forward is an explicit recovery epoch.
        recovered = fresh.open_recovery_epoch(
            constitution_hash=BOOT["constitution_hash"],
            runtime_measurement=BOOT["runtime_measurement"],
            machine_measurement=BOOT["machine_measurement"],
            recovery_reason="quorum-authorized rebuild",
        )
        self.assertTrue(recovered["continuity_broken"])
        self.assertTrue(recovered["recovered"])
        types = [e.receipt_type for e in fresh.entries()]
        self.assertIn("TRUST_DISCONTINUITY", types)
        self.assertIn("RECOVERY", types)
        # continuity flag stays broken forever after
        again = EpochLedger(self.dir)
        again.load_and_verify()
        self.assertTrue(again.continuity_broken)

    def test_recovery_requires_prior_discontinuity(self):
        ledger = EpochLedger(self.dir)
        ledger.boot(**BOOT)
        with self.assertRaises(EpochLedgerError):
            ledger.open_recovery_epoch(
                constitution_hash=BOOT["constitution_hash"],
                runtime_measurement=BOOT["runtime_measurement"],
                machine_measurement=BOOT["machine_measurement"],
                recovery_reason="no discontinuity occurred",
            )

    def test_discontinuity_on_empty_ledger_refused(self):
        ledger = EpochLedger(self.dir)
        with self.assertRaises(EpochLedgerError):
            ledger.declare_trust_discontinuity(reason="premature")

    # ---- corruption refuses boot ----

    def test_boot_refused_on_corrupt_ledger(self):
        ledger = EpochLedger(self.dir)
        ledger.boot(**BOOT)
        path = self.dir / "sovereign_epoch_ledger.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join(lines) + "\n{not json}\n", encoding="utf-8")
        fresh = EpochLedger(self.dir)
        with self.assertRaises(EpochLedgerError):
            fresh.boot(**{**BOOT, "boot_nonce": "post-corruption"})


if __name__ == "__main__":
    unittest.main()
