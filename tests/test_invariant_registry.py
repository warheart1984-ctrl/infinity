"""Tests for invariant_registry — ported from invariantRegistry.test.ts."""

from __future__ import annotations

import unittest

from src.invariant_registry import (
    CANONICAL_INVARIANTS,
    compile_invariant_dsl,
    create_invariant_registry,
    get_invariant,
    register_invariant,
)


def _transition(*, governance: float, confidence: float, payload: dict | None = None) -> dict:
    return {
        "transition_id": "idsl:freeze",
        "transition_type": "law_mutation",
        "payload": payload or {},
        "requested_capabilities": ["law:propose"],
        "context": {
            "actor": "operator",
            "mri_snapshot": {
                "continuity": 72,
                "governance": governance,
                "memory": 75,
                "coordination": 63,
                "confidence": confidence,
            },
            "runtime_context": {"corridor_id": "law-evolution", "capabilities": ["law:propose"]},
        },
    }


class TestInvariantRegistry(unittest.TestCase):
    def test_registers_and_retrieves_canonical_invariants(self):
        registry = create_invariant_registry(CANONICAL_INVARIANTS)
        invariant = get_invariant(registry, "INV-007")
        self.assertEqual(invariant["name"], "Resource Floor")
        self.assertIn("continuity", invariant["measured_dimensions"])
        self.assertEqual(
            invariant["receipt_metadata"]["subsystem"], "constitutional-enforcement-node"
        )

    def test_canonical_severity_and_authority_tokens(self):
        by_id = {item["id"]: item for item in CANONICAL_INVARIANTS}
        self.assertEqual(by_id["INV-021"]["receipt_metadata"]["severity"], "critical")
        self.assertEqual(by_id["INV-021"]["required_authority_token"], "VT")
        self.assertIsNone(by_id["INV-007"]["required_authority_token"])

    def test_missing_invariant_raises(self):
        registry = create_invariant_registry()
        with self.assertRaisesRegex(KeyError, "invariant not found: INV-999"):
            get_invariant(registry, "INV-999")

    def test_parses_boolean_idsl_without_eval(self):
        invariant = compile_invariant_dsl(
            "WHEN governance < 70 AND confidence >= 80 THEN FREEZE IF VIOLATED THEN DENY"
        )
        failed = invariant.evaluate(_transition(governance=68, confidence=81))
        self.assertFalse(failed["passed"])
        self.assertEqual(failed["action"], "FREEZE")

        passed = invariant.evaluate(_transition(governance=75, confidence=81))
        self.assertTrue(passed["passed"])
        self.assertEqual(passed["action"], "ALLOW")
        self.assertEqual(passed["message"], "IDSL condition satisfied")

    def test_or_groups_and_negation(self):
        invariant = compile_invariant_dsl(
            "WHEN NOT continuity >= 50 OR memory < 10 THEN DENY IF VIOLATED THEN DENY"
        )
        # continuity=72 satisfies >=50 (NOT -> False); memory=75 not < 10 (False) => satisfied
        satisfied = invariant.evaluate(_transition(governance=70, confidence=80))
        self.assertTrue(satisfied["passed"])
        self.assertEqual(satisfied["action"], "ALLOW")
        # payload overrides continuity to 30: NOT(30>=50) = True => violated
        violated = invariant.evaluate(
            _transition(governance=70, confidence=80, payload={"continuity": 30})
        )
        self.assertFalse(violated["passed"])
        self.assertEqual(violated["action"], "DENY")

    def test_payload_overrides_mri_snapshot(self):
        invariant = compile_invariant_dsl("require governance >= 70")
        result = invariant.evaluate(_transition(governance=40, confidence=80, payload={"governance": 90}))
        self.assertTrue(result["passed"])
        result = invariant.evaluate(_transition(governance=40, confidence=80))
        self.assertFalse(result["passed"])
        self.assertEqual(result["action"], "DENY")

    def test_require_syntax_backward_compatibility(self):
        invariant = compile_invariant_dsl("require governance >= 70")
        self.assertEqual(invariant.invariant_id, "idsl:governance:min:70")

    def test_unsupported_syntax_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported IDSL"):
            compile_invariant_dsl("eval process.exit()")
        with self.assertRaisesRegex(ValueError, "unsupported invariant DSL"):
            compile_invariant_dsl("require governance > 70")

    def test_custom_registration(self):
        registry = create_invariant_registry()
        register_invariant(
            registry,
            {
                "id": "INV-CUSTOM",
                "name": "Custom Confidence Floor",
                "measured_dimensions": ["confidence"],
                "threshold": 70,
                "expression": "require confidence >= 70",
                "receipt_metadata": {"subsystem": "test", "severity": "medium"},
            },
        )
        self.assertEqual(get_invariant(registry, "INV-CUSTOM")["threshold"], 70)


if __name__ == "__main__":
    unittest.main()
