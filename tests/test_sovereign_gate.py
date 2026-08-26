"""Sovereign gate tests: the demo's five acts through the REAL CEN stack.

1. safe read -> allow
2. authority grab -> deny (chained refusal evidence)
3. unapproved write -> await_human_approval
4. approve -> VT minted bound to transition -> allow
5. replay on fresh judge -> identical receipt hash; tamper -> mismatch
"""

from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.sovereign_gate_router import router, _transition_id, GateProposal


def _app() -> FastAPI:
    application = FastAPI()
    application.include_router(router)
    return application


def _read() -> dict:
    return dict(action="get_status", target="workflow:demo", effect="read", risk="low")


def _write() -> dict:
    return dict(action="write_file", target="workflow:demo", effect="write", risk="medium")


class TestSovereignGate(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(_app())

    def test_safe_read_allows_with_certificate(self):
        r = self.client.post("/sovereign/gate", json=_read())
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["verdict"], "allow")
        self.assertIn("sha3-256:", body["receipt_hash"])
        self.assertIsNotNone(body["certificate"])

    def test_authority_grab_is_denied_as_evidence(self):
        r = self.client.post("/sovereign/gate", json=dict(
            _read(), action="swap_policy", effect="authority_change", risk="critical"))
        body = r.json()
        self.assertEqual(body["verdict"], "deny")
        self.assertEqual(body["reason_codes"], ["CONSTITUTIONALLY_FORBIDDEN"])
        self.assertTrue(body["receipt_hash"], "denial must chain a refusal receipt")

    def test_unapproved_write_awaits_human(self):
        r = self.client.post("/sovereign/gate", json=_write())
        body = r.json()
        self.assertEqual(body["verdict"], "await_human_approval")
        self.assertEqual(body["reason_codes"], ["APPROVAL_REQUIRED"])
        self.assertTrue(body["transition_id"])
        # deterministic transition id for the same proposal
        again = self.client.post("/sovereign/gate", json=_write()).json()
        self.assertEqual(again["transition_id"], body["transition_id"])

    def test_approve_then_allow_roundtrip(self):
        awaited = self.client.post("/sovereign/gate", json=_write()).json()
        approval = self.client.post(
            "/sovereign/gate/approve", json={"transition_id": awaited["transition_id"]})
        self.assertEqual(approval.status_code, 200)
        token = approval.json()["approval_token"]
        self.assertEqual(token["tokenType"], "VT")
        self.assertEqual(token["transitionId"], awaited["transition_id"])

        final = self.client.post("/sovereign/gate/approved", json={
            "proposal": awaited["proposal"], "approval_token": token})
        body = final.json()
        self.assertEqual(body["verdict"], "allow")
        self.assertIsNotNone(body["receipt_hash"])
        self.assertTrue(body["fingerprint"]["payload_hash"])

    def test_forged_or_foreign_token_cannot_unlock(self):
        awaited = self.client.post("/sovereign/gate", json=_write()).json()
        approval = self.client.post(
            "/sovereign/gate/approve",
            json={"transition_id": "transition:gate:somebody-elses"},
        ).json()["approval_token"]
        final = self.client.post("/sovereign/gate/approved", json={
            "proposal": awaited["proposal"], "approval_token": approval})
        self.assertNotEqual(final.json()["verdict"], "allow")

    def test_replay_identity_and_mismatch(self):
        first = self.client.post("/sovereign/gate", json=_read()).json()
        replay = self.client.post("/sovereign/gate/replay", json={
            "proposal": first["proposal"],
            "expected_verdict": first["verdict"],
            "expected_payload_hash": first["fingerprint"]["payload_hash"],
            "expected_state_hash": first["fingerprint"]["state_hash"],
        }).json()
        self.assertTrue(replay["replay_ok"], replay.get("detail"))

        tampered = self.client.post("/sovereign/gate/replay", json={
            "proposal": dict(first["proposal"], payload={"tampered": True}),
            "expected_verdict": first["verdict"],
            "expected_payload_hash": first["fingerprint"]["payload_hash"],
            "expected_state_hash": first["fingerprint"]["state_hash"],
        }).json()
        self.assertFalse(tampered["replay_ok"])
        self.assertIn("MISMATCH", tampered["detail"])


class TestGateHistoryFeedsSovereignState(unittest.TestCase):
    def test_state_reflects_gate_judgments_and_chains(self):
        from app import sovereign_router as sr
        from fastapi import FastAPI

        # Fresh module state for isolation
        import app.sovereign_gate_router as gr
        gr.GATE_HISTORY.clear()

        application = FastAPI()
        application.include_router(router)
        application.include_router(sr.router)
        client = TestClient(application)

        self.assertEqual(client.get("/sovereign/state").json()["ledger"]["receipt_count"], 0)

        first = client.post("/sovereign/gate", json=_read()).json()
        second = client.post("/sovereign/gate", json=dict(
            _read(), action="swap_policy", effect="authority_change", risk="critical")).json()

        state = client.get("/sovereign/state").json()
        ledger = state["ledger"]
        self.assertEqual(ledger["receipt_count"], 2)
        self.assertTrue(ledger["chain_intact"], "gate history must chain across judgments")
        head = client.get("/sovereign/epoch").json()
        self.assertEqual(head["ledger_head_hash"], second["receipt_hash"])

        verdicts = client.get("/sovereign/verdicts?limit=10").json()["verdicts"]
        ids = {v["receiptId"] for v in verdicts}
        self.assertIn(first["receipt_id"], ids)
        self.assertIn(second["receipt_id"], ids)
        # certificates ride along for allowed judgments
        allowed = next(v for v in verdicts if v["receiptId"] == first["receipt_id"])
        self.assertIn("certificate", allowed)


if __name__ == "__main__":
    unittest.main()
