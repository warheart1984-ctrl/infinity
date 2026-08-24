"""Acceptance tests for timestamped AMUL epistemic reconciliation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.amul_epistemic_ledger import (
    AMULEpistemicLedgerStore,
    EpistemicLedgerIntegrityError,
)


class AMULEpistemicLedgerTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.runtime_dir = Path(self._tmpdir.name)
        self.store = AMULEpistemicLedgerStore(runtime_dir=self.runtime_dir)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _reported(self, **overrides):
        claim = {
            "claim_id": "reported-old",
            "subject": "infinity.backend",
            "proposition": "Infinity backend is reachable.",
            "kind": "reported",
            "source": {"kind": "operator_report", "ref": "session-127"},
            "scope": "local-host",
            "observed_at": "2026-08-24T10:00:00Z",
            "valid_until": "2026-08-24T10:05:00Z",
            "confidence": 0.9,
        }
        claim.update(overrides)
        return claim

    def _observed(self, **overrides):
        claim = {
            "claim_id": "observed-new",
            "subject": "infinity.backend",
            "proposition": "Infinity backend is not reachable from the current process scope.",
            "kind": "observed",
            "source": {"kind": "runtime_probe", "ref": "curl-localhost-13305"},
            "scope": "local-host",
            "observed_at": "2026-08-24T10:10:00Z",
            "valid_until": "2026-08-24T10:20:00Z",
            "confidence": 0.7,
            "verification_method": "TCP/HTTP probe from the active runtime",
            "evidence_refs": ["probe://localhost/13305/2026-08-24T10:10:00Z"],
            "contradicts": ["reported-old"],
        }
        claim.update(overrides)
        return claim

    def test_stale_report_and_fresh_observation_preserve_historical_conflict(self):
        old = self.store.append_claim(self._reported())
        new = self.store.append_claim(self._observed())

        result = self.store.reconcile(
            subject="infinity.backend",
            scope="local-host",
            as_of="2026-08-24T10:12:00Z",
        )

        states = {row["claim_id"]: row["temporal_state"] for row in result["claims"]}
        self.assertEqual(states[old["claim_id"]], "stale")
        self.assertEqual(states[new["claim_id"]], "bounded_current")
        self.assertEqual(result["overall_state"], "bounded_current")
        self.assertEqual(result["open_conflicts"], [])
        self.assertEqual(len(result["historical_conflicts"]), 1)
        self.assertEqual(len(self.store.list_claims()), 2)
        self.assertFalse(result["truth_adjudicated"])

    def test_two_fresh_contradictory_claims_are_contested_without_confidence_winner(self):
        first = self.store.append_claim(
            self._reported(valid_until="2026-08-24T10:30:00Z", confidence=0.99)
        )
        second = self.store.append_claim(self._observed(confidence=0.1))

        result = self.store.reconcile(
            subject="infinity.backend",
            scope="local-host",
            as_of="2026-08-24T10:12:00Z",
        )

        self.assertEqual(result["overall_state"], "contested")
        self.assertEqual(len(result["open_conflicts"]), 1)
        self.assertEqual(
            {row["claim_id"] for row in result["current_claims"]},
            {first["claim_id"], second["claim_id"]},
        )
        self.assertTrue(
            all(row["temporal_state"] == "contested" for row in result["current_claims"])
        )
        self.assertIn("do not choose by confidence", result["recommended_action"])

    def test_explicit_supersession_marks_old_record_without_erasing_it(self):
        old = self.store.append_claim(self._reported(valid_until=None))
        replacement = self.store.append_claim(
            self._observed(
                proposition="Infinity backend is reachable after restart.",
                contradicts=[],
                supersedes=[old["claim_id"]],
            )
        )

        result = self.store.reconcile(
            subject="infinity.backend",
            scope="local-host",
            as_of="2026-08-24T10:12:00Z",
        )

        states = {row["claim_id"]: row["temporal_state"] for row in result["claims"]}
        self.assertEqual(states[old["claim_id"]], "superseded")
        self.assertEqual(states[replacement["claim_id"]], "bounded_current")
        self.assertEqual(len(result["claims"]), 2)

    def test_observation_requires_method_and_evidence(self):
        with self.assertRaisesRegex(ValueError, "observed claims require"):
            self.store.append_claim(
                self._observed(verification_method=None, evidence_refs=[])
            )

    def test_validity_window_must_follow_observation(self):
        with self.assertRaisesRegex(ValueError, "valid_until must be later"):
            self.store.append_claim(
                self._reported(valid_until="2026-08-24T09:59:59Z")
            )

    def test_relation_targets_must_share_subject_and_scope(self):
        old = self.store.append_claim(self._reported())
        with self.assertRaisesRegex(ValueError, "must share subject and scope"):
            self.store.append_claim(
                self._observed(scope="container-only", contradicts=[old["claim_id"]])
            )

    def test_store_reloads_and_verifies_hash_chain(self):
        self.store.append_claim(self._reported())
        reloaded = AMULEpistemicLedgerStore(runtime_dir=self.runtime_dir)

        verification = reloaded.verify_chain()

        self.assertTrue(verification["valid"])
        self.assertEqual(verification["entry_count"], 1)
        self.assertEqual(len(reloaded.list_claims()), 1)

    def test_tampered_history_fails_closed(self):
        self.store.append_claim(self._reported())
        row = json.loads(self.store.path.read_text(encoding="utf-8"))
        row["proposition"] = "Tampered proposition"
        self.store.path.write_text(json.dumps(row) + "\n", encoding="utf-8")

        self.assertFalse(self.store.verify_chain()["valid"])
        with self.assertRaises(EpistemicLedgerIntegrityError):
            self.store.list_claims()
        with self.assertRaises(EpistemicLedgerIntegrityError):
            self.store.append_claim(self._observed())


if __name__ == "__main__":
    unittest.main()
