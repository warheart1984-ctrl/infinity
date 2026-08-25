"""Governed API tests for the AMUL Epistemic Ledger."""

from __future__ import annotations

import tempfile
import unittest

import src.api as api


class AMULEpistemicApiTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._original_runtime_dir = api.amul_epistemic_ledger._runtime_dir_override
        api.amul_epistemic_ledger.configure_runtime_dir(self._tmpdir.name)
        self.client = api.app.test_client()

    def tearDown(self):
        api.amul_epistemic_ledger.configure_runtime_dir(self._original_runtime_dir)
        self._tmpdir.cleanup()

    def test_claim_status_list_and_reconciliation_routes(self):
        first_response = self.client.post(
            "/api/jarvis/epistemic/claims",
            json={
                "claim_id": "api-old",
                "subject": "service.infinity",
                "proposition": "Service is reachable.",
                "kind": "reported",
                "source": {"kind": "memory", "ref": "memory-127"},
                "scope": "desktop",
                "observed_at": "2026-08-24T09:00:00Z",
                "valid_until": "2026-08-24T09:05:00Z",
            },
        )
        self.assertEqual(first_response.status_code, 201)
        self.assertFalse(first_response.get_json()["truth_adjudicated"])

        second_response = self.client.post(
            "/api/jarvis/epistemic/claims",
            json={
                "claim_id": "api-new",
                "subject": "service.infinity",
                "proposition": "Service is not reachable from the desktop process.",
                "kind": "observed",
                "source": {"kind": "probe", "ref": "localhost-13305"},
                "scope": "desktop",
                "observed_at": "2026-08-24T09:10:00Z",
                "valid_until": "2026-08-24T09:20:00Z",
                "verification_method": "HTTP probe",
                "evidence_refs": ["probe://localhost/13305"],
                "contradicts": ["api-old"],
            },
        )
        self.assertEqual(second_response.status_code, 201)

        list_response = self.client.get(
            "/api/jarvis/epistemic/claims?subject=service.infinity&scope=desktop"
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.get_json()["count"], 2)

        reconcile_response = self.client.post(
            "/api/jarvis/epistemic/reconcile",
            json={
                "subject": "service.infinity",
                "scope": "desktop",
                "as_of": "2026-08-24T09:12:00Z",
            },
        )
        self.assertEqual(reconcile_response.status_code, 200)
        reconciliation = reconcile_response.get_json()
        self.assertEqual(reconciliation["overall_state"], "bounded_current")
        self.assertEqual(len(reconciliation["historical_conflicts"]), 1)
        self.assertFalse(reconciliation["truth_adjudicated"])

        status_response = self.client.get("/api/jarvis/epistemic/status")
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.get_json()["status"], "ready")
        self.assertEqual(status_response.get_json()["entry_count"], 2)

    def test_invalid_observation_is_rejected(self):
        response = self.client.post(
            "/api/jarvis/epistemic/claims",
            json={
                "subject": "service.infinity",
                "proposition": "Service is reachable.",
                "kind": "observed",
                "source": "manual",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("observed claims require", response.get_json()["error"])

    def test_every_jarvis_turn_gets_one_required_epistemic_law_block(self):
        session_id = api.conversation_memory.create_session(system_prompt="You are Jarvis.")
        session = api.conversation_memory.get_session(session_id)

        blocks = api._extra_prompt_blocks(session)
        law_blocks = [block for block in blocks if block["identity"] == "epistemic_law"]

        self.assertEqual(len(law_blocks), 1)
        self.assertTrue(law_blocks[0]["required"])
        self.assertIn("timestamped evidence", law_blocks[0]["content"])


if __name__ == "__main__":
    unittest.main()
