"""Sovereign gate tests: THE sanctioned TS↔Python write crossing.

Proves:
- approved path returns the full CommitCertificate + receipt ids
- law_mutation without a VT denies 200 with a re-mintable challenge shape,
  and re-minting via mint_vt_token_from_denial then succeeds
- malformed bodies produce MALFORMED_TRANSITION refusal receipts (chained,
  hash-valid) and never reach policy evaluation
- exactly ONE write method exists anywhere under /sovereign/*, and it is
  POST /sovereign/gate; every other route is read-only
"""

from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.sovereign_gate_router import router as gate_router
from app.sovereign_router import router as state_router
from src.cen_governance_bridge import (
    CenGovernanceBridge,
    mint_vt_token_from_denial,
)


def _app(bridge: CenGovernanceBridge) -> FastAPI:
    """Mount both sovereign routers against an isolated bridge instance."""
    import app.sovereign_router as sr
    import app.sovereign_gate_router as sgr
    from src.sovereign_state import SovereignStateReader

    sr._reader = SovereignStateReader(
        receipts_provider=lambda: bridge.receipts,
        certificates_provider=lambda: bridge.certificates,
    )
    sgr._bridge = bridge

    app = FastAPI()
    app.include_router(state_router)
    app.include_router(gate_router)
    return app


class SovereignGateApiTests(unittest.TestCase):
    def setUp(self):
        self.bridge = CenGovernanceBridge()
        self.client = TestClient(_app(self.bridge))

    # ---- approved path ----

    def test_approved_runtime_action_carries_full_certificate(self):
        r = self.client.post(
            "/sovereign/gate",
            json={
                "transition_id": "transition:gate-ok",
                "transition_type": "runtime_action",
                "payload": {"coordination": 71},
                "requested_capabilities": ["state:commit"],
                "granted_capabilities": ["state:commit"],
                "actor": "middleware",
            },
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["outcome"], "approved")
        self.assertTrue(body["cen_receipt_id"])
        self.assertTrue(body["evidence_receipt_id"])
        cert = body["commitCertificate"]
        for field in (
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
        ):
            self.assertIn(field, cert)
        self.assertEqual(cert["epoch_id"], "genesis")

    def test_certificate_is_retrievable_via_read_side(self):
        approved = self.client.post(
            "/sovereign/gate",
            json={
                "transition_id": "transition:gate-readback",
                "transition_type": "runtime_action",
                "payload": {"coordination": 71},
                "requested_capabilities": ["state:commit"],
            },
        ).json()
        self.assertEqual(approved["outcome"], "approved")
        receipt_id = approved["cen_receipt_id"]
        verdict = self.client.get(f"/sovereign/verdicts/{receipt_id}")
        self.assertEqual(verdict.status_code, 200)
        self.assertIn("certificate", verdict.json())

    # ---- denial / challenge-response ----

    def test_law_mutation_without_vt_denies_with_remintable_shape(self):
        r = self.client.post(
            "/sovereign/gate",
            json={
                "transition_id": "transition:gate-law-no-token",
                "transition_type": "law_mutation",
                "payload": {"charter": "x"},
                "requested_capabilities": ["law:mutate"],
            },
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["outcome"], "denied")
        self.assertFalse(body["committed"])
        # Bridge-level VT requirement fired before any policy evaluation.
        self.assertEqual(body["reason"], "cen_vt_required")
        # Challenge-response shape: transition binding survives for re-minting.
        self.assertEqual(body["transition_id"], "transition:gate-law-no-token")
        self.assertTrue(body["cen_receipt_id"])

        # Re-minting works directly off the denial body.
        burned_token = mint_vt_token_from_denial(body)
        self.assertEqual(burned_token["transitionId"], body["transition_id"])

        # Replay protection correctly refuses the burned transition id...
        burned = self.client.post(
            "/sovereign/gate",
            json={
                "transition_id": "transition:gate-law-no-token",
                "transition_type": "law_mutation",
                "payload": {"charter": "x"},
                "requested_capabilities": ["law:mutate"],
                "granted_capabilities": ["law:mutate"],
                "authority_token": burned_token,
            },
        )
        self.assertEqual(burned.json()["reason_code"], "REPLAY_DETECTED")

        # ...so the sanctioned flow mints against the NEXT transition and
        # submits it exactly once.
        next_id = "transition:gate-law-with-token"
        token = mint_vt_token_from_denial({"transition_id": next_id})
        retry = self.client.post(
            "/sovereign/gate",
            json={
                "transition_id": next_id,
                "transition_type": "law_mutation",
                "payload": {"charter": "x"},
                "requested_capabilities": ["law:mutate"],
                "granted_capabilities": ["law:mutate"],
                "authority_token": token,
            },
        )
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.json()["outcome"], "approved")

    # ---- malformed input ----

    def test_malformed_bodies_chain_refusal_receipts(self):
        malformed_bodies = [
            {"transition_type": "runtime_action", "payload": {}, "requested_capabilities": ["x"]},
            {
                "transition_id": "t1",
                "transition_type": "not_a_real_type",
                "payload": {},
                "requested_capabilities": ["x"],
            },
            {
                "transition_id": "t2",
                "transition_type": "runtime_action",
                "payload": "not-an-object",
                "requested_capabilities": ["x"],
            },
            {
                "transition_id": "t3",
                "transition_type": "runtime_action",
                "payload": {},
                "requested_capabilities": [],
            },
        ]
        before = len(self.bridge.receipts)
        for bad in malformed_bodies:
            r = self.client.post("/sovereign/gate", json=bad)
            self.assertEqual(r.status_code, 200)
            body = r.json()
            self.assertEqual(body["outcome"], "denied")
            self.assertEqual(body["reason_code"], "MALFORMED_TRANSITION")
            self.assertTrue(body["cen_receipt_id"])
        after = len(self.bridge.receipts)
        self.assertEqual(after - before, len(malformed_bodies))
        for receipt in self.bridge.receipts[before:]:
            self.assertEqual(receipt["verdict"], "DENY")
            self.assertEqual(receipt["reasonCode"], "MALFORMED_TRANSITION")

    def test_non_json_body_is_malformed(self):
        r = self.client.post(
            "/sovereign/gate",
            content=b"this is not json",
            headers={"Content-Type": "text/plain"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["reason_code"], "MALFORMED_TRANSITION")

    def test_malformed_never_produces_approval_or_certificate(self):
        r = self.client.post(
            "/sovereign/gate",
            json={
                "transition_id": "t-malformed-cert",
                "transition_type": "runtime_action",
                "payload": {},
                "requested_capabilities": "should-have-been-a-list",
            },
        )
        body = r.json()
        self.assertNotIn("commitCertificate", body)
        self.assertEqual(body.get("committed"), False)

    # ---- Ring 2: singular explicit write path ----

    def test_exactly_one_write_method_exists_across_sovereign_routes(self):
        from fastapi.routing import APIRoute

        all_sovereign_routes = [
            route
            for route in state_router.routes + gate_router.routes
            if isinstance(route, APIRoute)
            and str(route.path).startswith("/sovereign")
        ]
        writes = [
            (route.path, method)
            for route in all_sovereign_routes
            for method in {m.lower() for m in route.methods}
            if method in {"post", "put", "patch", "delete"}
        ]
        self.assertEqual(writes, [("/sovereign/gate", "post")])

    def test_readonly_router_contract_unchanged(self):
        from fastapi.routing import APIRoute

        for route in state_router.routes:
            if not isinstance(route, APIRoute):
                continue
            methods = {m.lower() for m in route.methods}
            self.assertFalse(
                methods & {"post", "put", "patch", "delete"},
                f"read-only router gained a write method: {route.path}",
            )


if __name__ == "__main__":
    unittest.main()
