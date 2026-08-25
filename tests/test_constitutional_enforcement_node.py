"""Tests for constitutional_enforcement_node — ported from enforcementNode.test.ts
plus a cross-runtime golden receipt (fixed-clock CEN demo, TS algorithm)."""

from __future__ import annotations

import unittest

from src.constitutional_enforcement_node import (
    ConstitutionalEnforcementNode,
    compile_invariant_dsl,
    create_resource_floor_invariant,
    issue_authority_token,
    verify_enforcement_receipt,
)

BASELINE_CONTEXT = {
    "actor": "operator",
    "mriSnapshot": {
        "continuity": 72,
        "governance": 68,
        "memory": 75,
        "coordination": 63,
        "confidence": 81,
    },
    "runtimeContext": {
        "corridorId": "law-evolution",
        "capabilities": ["law:propose", "state:commit"],
    },
}


def _transition(**overrides) -> dict:
    transition = {
        "transitionId": "transition:safe",
        "transitionType": "state_update",
        "payload": {"continuity": 74},
        "requestedCapabilities": ["state:commit"],
        "context": BASELINE_CONTEXT,
    }
    transition.update(overrides)
    return transition


class TestEnforcementNode(unittest.TestCase):
    def test_allows_safe_transitions_and_commits_state(self):
        node = ConstitutionalEnforcementNode(invariants=[create_resource_floor_invariant("continuity", 50)])
        result = node.execute(
            _transition(payload={"continuity": 74}, requestedCapabilities=["state:commit"])
        )
        self.assertEqual(result["decision"]["verdict"], "ALLOW")
        self.assertTrue(result["committed"])
        self.assertEqual(node.get_state("transition:safe"), {"continuity": 74})
        self.assertTrue(result["receipt"]["receiptId"].startswith("cen:"))
        self.assertIsNone(result["receipt"]["previousReceiptHash"])

    def test_denies_violations_and_hash_chains_receipts(self):
        node = ConstitutionalEnforcementNode(invariants=[create_resource_floor_invariant("coordination", 60)])
        allowed = node.execute(_transition(transitionId="transition:prime", payload={"coordination": 64}))
        denied = node.execute(
            _transition(transitionId="transition:floor-breach", payload={"coordination": 42})
        )
        self.assertEqual(allowed["decision"]["verdict"], "ALLOW")
        self.assertEqual(denied["decision"]["verdict"], "DENY")
        self.assertEqual(denied["decision"]["reasonCode"], "INVARIANT_VIOLATION")
        self.assertFalse(denied["committed"])
        self.assertEqual(denied["receipt"]["previousReceiptHash"], allowed["receipt"]["receiptHash"])
        self.assertIsNone(node.get_state("transition:floor-breach"))

    def test_compiles_minimum_dsl_bridge(self):
        invariant = compile_invariant_dsl("require governance >= 70")
        node = ConstitutionalEnforcementNode(invariants=[invariant])
        result = node.execute(
            _transition(
                transitionId="transition:dsl-deny",
                transitionType="law_mutation",
                payload={"law": "soft invariant proposed"},
                requestedCapabilities=["law:propose"],
            )
        )
        self.assertEqual(result["decision"]["verdict"], "DENY")
        self.assertEqual(result["receipt"]["evaluations"][0]["invariantId"], "idsl:governance:min:70")

    def test_denies_capability_bypass_before_invariants(self):
        node = ConstitutionalEnforcementNode(invariants=[create_resource_floor_invariant("continuity", 50)])
        result = node.execute(
            _transition(
                transitionId="transition:bypass",
                transitionType="law_mutation",
                payload={"law": "mutate outside authority"},
                requestedCapabilities=["root:bypass"],
            )
        )
        self.assertEqual(result["decision"]["verdict"], "DENY")
        self.assertEqual(result["decision"]["reasonCode"], "CAPABILITY_DENIED")
        self.assertEqual(len(result["receipt"]["evaluations"]), 0)

    def test_ep1_lifecycle_and_categories(self):
        node = ConstitutionalEnforcementNode(
            invariants=[create_resource_floor_invariant("continuity", 50)],
            issued_at=lambda: "2026-06-18T22:45:00.000Z",
        )
        transition = _transition()

        intercepted = node.intercept(transition)
        evaluated = node.evaluate(intercepted)
        allowed = node.allow(evaluated)
        replayed = node.execute(transition)
        malformed = node.execute(dict(transition, transitionId="", payload=None))

        self.assertEqual(allowed["receipt"]["category"], "allow")
        self.assertEqual(allowed["receipt"]["stage"], "receipt")
        self.assertTrue(verify_enforcement_receipt(allowed["receipt"]))
        self.assertEqual(replayed["decision"]["reasonCode"], "REPLAY_DETECTED")
        self.assertEqual(replayed["receipt"]["category"], "replay")
        self.assertEqual(malformed["decision"]["reasonCode"], "MALFORMED_TRANSITION")
        self.assertEqual(malformed["receipt"]["category"], "anomaly")

    def test_authority_tokens_and_trigger_actions(self):
        node = ConstitutionalEnforcementNode(
            invariants=[
                type(
                    "Trigger",
                    (),
                    {
                        "invariant_id": "trigger:freeze-low-confidence",
                        "evaluate": lambda self, t: {
                            "invariantId": "trigger:freeze-low-confidence",
                            "passed": False,
                            "message": "confidence below freeze floor",
                            "action": "FREEZE",
                        },
                    },
                )()
            ],
            issued_at=lambda: "2026-06-18T22:45:00.000Z",
        )
        token = issue_authority_token(
            token_id="vt-1",
            token_type="VT",
            scope=["law:propose"],
            transition_id="transition:freeze",
            expires_at="2999-01-01T00:00:00.000Z",
        )

        frozen = node.execute(
            _transition(
                transitionId="transition:freeze",
                transitionType="law_mutation",
                payload={"law": "unsafe mutation"},
                requestedCapabilities=["law:propose"],
                authorityToken=token,
            )
        )
        replayed_token = node.execute(
            _transition(
                transitionId="transition:new-token-replay",
                transitionType="law_mutation",
                payload={"law": "reuse token"},
                requestedCapabilities=["law:propose"],
                authorityToken=token,
            )
        )

        self.assertEqual(frozen["decision"]["verdict"], "DENY")
        self.assertEqual(frozen["decision"]["action"], "FREEZE")
        self.assertEqual(frozen["receipt"]["category"], "deny")
        self.assertEqual(replayed_token["decision"]["reasonCode"], "TOKEN_REPLAYED")
        self.assertEqual(replayed_token["receipt"]["category"], "token_refusal")


class TestTokenRefusals(unittest.TestCase):
    def _node(self) -> ConstitutionalEnforcementNode:
        return ConstitutionalEnforcementNode(invariants=[create_resource_floor_invariant("continuity", 50)])

    def _token(self, **overrides) -> dict:
        return issue_authority_token(
            token_id="vt-x",
            token_type="VT",
            scope=["law:propose"],
            transition_id="transition:t1",
            expires_at="2999-01-01T00:00:00.000Z",
            **overrides,
        )

    def test_expired_token_denied(self):
        token = issue_authority_token(
            token_id="vt-old", token_type="VT", scope=["law:propose"],
            transition_id="transition:t1", expires_at="2000-01-01T00:00:00.000Z",
        )
        result = self._node().execute(
            _transition(transitionId="transition:t1", transitionType="runtime_action",
                        payload={"continuity": 80}, requestedCapabilities=["law:propose"],
                        authorityToken=token)
        )
        self.assertEqual(result["decision"]["reasonCode"], "TOKEN_EXPIRED")
        self.assertEqual(result["receipt"]["category"], "token_refusal")

    def test_signature_tamper_denied(self):
        token = self._token()
        token["signature"] = "0" * 64
        result = self._node().execute(
            _transition(transitionId="transition:t1", transitionType="runtime_action",
                        payload={"continuity": 80}, requestedCapabilities=["law:propose"],
                        authorityToken=token)
        )
        self.assertEqual(result["decision"]["reasonCode"], "TOKEN_INVALID_SIGNATURE")

    def test_transition_mismatch_denied(self):
        token = self._token()
        result = self._node().execute(
            _transition(transitionId="transition:other", transitionType="runtime_action",
                        payload={"continuity": 80}, requestedCapabilities=["law:propose"],
                        authorityToken=token)
        )
        self.assertEqual(result["decision"]["reasonCode"], "TOKEN_TRANSITION_MISMATCH")

    def test_scope_denial(self):
        token = self._token()
        result = self._node().execute(
            _transition(transitionId="transition:t1", transitionType="runtime_action",
                        payload={"continuity": 80}, requestedCapabilities=["state:commit"],
                        authorityToken=token)
        )
        self.assertEqual(result["decision"]["reasonCode"], "TOKEN_SCOPE_DENIED")
        self.assertIn("state:commit", result["decision"]["reasonDetail"])


class TestCrossRuntimeGolden(unittest.TestCase):
    """Fixed-clock demo receipt must match the TS algorithm byte-for-byte."""

    GOLDEN_ABSENT_TOKEN_HASH = "sha3-256:1dcb8a0fbbac33d5a496a5c3220fd02797716ac760747735c0d36d8ade75bf12"
    GOLDEN_PRESENT_TOKEN_HASH = "sha3-256:dcfff5ee576f6342a00ec88fa5474e090b48ffb6d34ce070f520b6411b02b844"
    GOLDEN_TOKEN_SIGNATURE = "c40841f77444d367ee1241e1ac79e31789e8f2052c90b3a25fae24eb53bb15f9"

    def test_demo_receipt_matches_ts_golden(self):
        node = ConstitutionalEnforcementNode(
            invariants=[compile_invariant_dsl("require governance >= 70")],
            issued_at=lambda: "2026-06-18T22:02:00.000Z",
        )
        result = node.execute(
            _transition(
                transitionId="transition:cen-demo",
                transitionType="law_mutation",
                payload={"law": "soft invariant proposed"},
                requestedCapabilities=["law:propose"],
            )
        )
        receipt = result["receipt"]
        self.assertEqual(result["decision"]["verdict"], "DENY")
        self.assertEqual(receipt["receiptHash"], self.GOLDEN_ABSENT_TOKEN_HASH)
        self.assertEqual(receipt["receiptId"], f"cen:{self.GOLDEN_ABSENT_TOKEN_HASH[len('sha3-256:'):]}")
        self.assertTrue(verify_enforcement_receipt(receipt))
        # Receipt base keys stay TS-native camelCase per the Key Identity Law.
        self.assertIn("mriSnapshotHash", receipt)
        self.assertIn("previousReceiptHash", receipt)

    def test_regression_absent_authority_token_id_is_omitted_not_null(self):
        """Value State Law regression: TS omits undefined fields before hashing;
        Python must omit the key too — inventing null changes the hash and
        breaks cross-runtime identity."""
        node = ConstitutionalEnforcementNode(
            invariants=[compile_invariant_dsl("require governance >= 70")],
            issued_at=lambda: "2026-06-18T22:02:00.000Z",
        )
        result = node.execute(
            _transition(
                transitionId="transition:cen-demo",
                transitionType="law_mutation",
                payload={"law": "soft invariant proposed"},
                requestedCapabilities=["law:propose"],
            )
        )
        receipt = result["receipt"]
        self.assertNotIn("authorityTokenId", receipt)
        self.assertEqual(receipt["receiptHash"], self.GOLDEN_ABSENT_TOKEN_HASH)

    def test_regression_present_authority_token_id_is_hashed(self):
        token = issue_authority_token(
            token_id="vt-1",
            token_type="VT",
            scope=["law:propose"],
            transition_id="transition:tokenized",
            expires_at="2999-01-01T00:00:00.000Z",
            issued_at="2026-06-18T22:45:00.000Z",
        )
        self.assertEqual(token["signature"], self.GOLDEN_TOKEN_SIGNATURE)
        node = ConstitutionalEnforcementNode(
            invariants=[create_resource_floor_invariant("continuity", 50)],
            issued_at=lambda: "2026-06-18T22:45:00.000Z",
        )
        result = node.execute(
            _transition(
                transitionId="transition:tokenized",
                transitionType="runtime_action",
                payload={"continuity": 74},
                requestedCapabilities=["law:propose"],
                authorityToken=token,
            )
        )
        receipt = result["receipt"]
        self.assertEqual(result["decision"]["verdict"], "ALLOW")
        self.assertEqual(receipt["authorityTokenId"], "vt-1")
        self.assertEqual(receipt["receiptHash"], self.GOLDEN_PRESENT_TOKEN_HASH)
        self.assertTrue(verify_enforcement_receipt(receipt))


if __name__ == "__main__":
    unittest.main()
