"""Sovereign state middleware tests: read-only endpoints over the CEN stack.

Proves:
- ledger head / epoch / verdicts / certificates are exposed read-only
- receipts are sanitized to the explicit field allowlist
- the router defines NO write method at all (Ring 2: absent, not disabled)
- chain integrity flag reflects the actual receipt chain
"""

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.sovereign_router import router
from src.cen_governance_bridge import CenGovernanceBridge
from src.sovereign_state import (
    _CERTIFICATE_PUBLIC_FIELDS,
    _RECEIPT_PUBLIC_FIELDS,
    SovereignStateReader,
)


def _seeded_app(bridge: CenGovernanceBridge) -> FastAPI:
    # Rebind the router's reader to the seeded bridge via dependency-free trick:
    # build a fresh app whose reader wraps this bridge's receipts.
    from app import sovereign_router as sr

    sr._reader = SovereignStateReader(
        receipts_provider=lambda: bridge.receipts,
        certificates_provider=lambda: bridge.certificates,
    )
    app = FastAPI()
    app.include_router(router)
    return app


class TestSovereignStateMiddleware(unittest.TestCase):
    def setUp(self):
        self.bridge = CenGovernanceBridge()
        # One approval + one denial so both verdict classes appear.
        self.bridge.gate_commit(
            transition_id="transition:api-ok",
            transition_type="runtime_action",
            payload={"continuity": 74},
            requested_capabilities=["state:commit"],
            granted_capabilities=["workflow:execute", "state:commit"],
        )
        self.bridge.gate_commit(
            transition_id="transition:api-no",
            transition_type="law_mutation",
            payload={"memory": 90},
            requested_capabilities=["law:mutate"],
            granted_capabilities=["law:mutate"],
            authority_token=None,
        )
        self.client = TestClient(_seeded_app(self.bridge))

    # ---- endpoint behaviour ----

    def test_state_summary_shape(self):
        r = self.client.get("/sovereign/state")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertFalse(body["ledger"]["empty"])
        self.assertTrue(body["ledger"]["chain_intact"])
        self.assertEqual(body["ledger"]["receipt_count"], 2)
        self.assertIn("epoch_id", body["epoch"])
        self.assertEqual(body["recent"]["allowed"], 1)
        self.assertEqual(body["recent"]["denied"], 1)
        self.assertIs(body["view"]["mutation_capable"], False)

    def test_epoch_endpoint_reports_genesis_and_head(self):
        r = self.client.get("/sovereign/epoch")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["epoch_id"], "genesis")
        self.assertIsNotNone(body["ledger_head_hash"])

    def test_verdicts_newest_first_and_sanitized(self):
        r = self.client.get("/sovereign/verdicts?limit=10")
        self.assertEqual(r.status_code, 200)
        verdicts = r.json()["verdicts"]
        self.assertEqual(len(verdicts), 2)
        newest = verdicts[0]
        self.assertEqual(newest["transitionId"], "transition:api-no")
        # Sanitization: raw payloads and MRI snapshots must not leak.
        self.assertNotIn("payloadHash", newest)
        self.assertNotIn("evaluations", newest)
        self.assertNotIn("mriSnapshotHash", newest)
        self.assertTrue(set(newest) <= set(_RECEIPT_PUBLIC_FIELDS) | {"certificate"})
        if "certificate" in newest:
            self.assertTrue(set(newest["certificate"]) <= set(_CERTIFICATE_PUBLIC_FIELDS))

    def test_verdict_by_id_includes_certificate(self):
        approved = self.bridge.gate_commit(
            transition_id="transition:api-cert",
            transition_type="runtime_action",
            payload={"confidence": 85},
            requested_capabilities=["state:commit"],
            granted_capabilities=["state:commit"],
        )
        receipt_id = approved["cen_receipt_id"]
        r = self.client.get(f"/sovereign/verdicts/{receipt_id}")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["receiptId"], receipt_id)
        self.assertIn("certificate", body)
        self.assertEqual(body["certificate"]["epoch_id"], "genesis")

    def test_unknown_receipt_is_404(self):
        r = self.client.get("/sovereign/verdicts/cen:does-not-exist")
        self.assertEqual(r.status_code, 404)

    # ---- Ring 2: no write path exists ----

    def test_router_defines_no_write_methods(self):
        write_methods = {"post", "put", "patch", "delete"}
        for route in router.routes:
            methods = {m.lower() for m in getattr(route, "methods", set())}
            self.assertFalse(
                methods & write_methods,
                f"write method found on {getattr(route, 'path', route)}: {methods}",
            )

    def test_reader_exposes_no_mutation_capability(self):
        reader = SovereignStateReader(receipts_provider=lambda: [])
        for forbidden in ("gate_commit", "mutate", "commit_approved", "execute"):
            self.assertFalse(
                any(callable(getattr(reader, name, None)) and name == forbidden
                    for name in dir(reader)),
                f"reader must not expose {forbidden}",
            )
        with self.assertRaises(RuntimeError):
            reader.readonly_view().mutate(anything=True)

    # ---- chain integrity ----

    def test_chain_intact_flag_true_for_sequential_receipts(self):
        self.bridge.gate_commit(
            transition_id="transition:api-chain",
            transition_type="runtime_action",
            payload={"coordination": 70},
            requested_capabilities=["state:commit"],
            granted_capabilities=["state:commit"],
        )
        head = SovereignStateReader(receipts_provider=lambda: self.bridge.receipts).ledger_head()
        self.assertTrue(head["chain_intact"])
        self.assertEqual(head["receipt_count"], 3)


if __name__ == "__main__":
    unittest.main()
