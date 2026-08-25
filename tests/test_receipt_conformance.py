"""Adversarial conformance suite for organism receipts and the invariant registry.

Pins checkpoint behavior (DEEA clone commit b9852d7) per
docs/contracts/ORGANISM_RECEIPT_CONTRACT.md: malformed receipts, single-byte
mutation, key reordering, unknown invariants, authority-token declarations,
snapshot/payload conflicts, and cross-runtime replay.
"""

from __future__ import annotations

import json
import subprocess
import unittest

from src.aaes_evidence_receipts import create_evidence_receipt, hash_json
from src.invariant_registry import (
    AUTHORITY_TOKEN_TYPES,
    CANONICAL_INVARIANTS,
    compile_invariant_dsl,
    create_invariant_registry,
    get_invariant,
)
from src.organism_receipt import (
    canonical_json,
    from_lirl,
    validate_organism_receipt,
    verify_receipt_id,
)

SOVEREIGN_X_RECEIPT_JS = "/home/jon/dev/Sovereign-X/src/lirl/organismReceipt.js"


def _stored() -> dict:
    return {
        "receiptId": "evidence:fd794caedeadbeef",
        "issuedAt": "2026-08-23T12:00:00Z",
        "verdict": "ACCEPT",
        "intentId": "intent-1",
        "actorId": "operator",
        "action": "memory.write",
        "memoryWritten": True,
        "reasons": ["actor lawful", "action in allowlist"],
        "claimLabel": "lirl:accept:memory.write",
        "subsystem": "lirl-vertical-slice",
        "subjectHash": "a" * 64,
        "evidenceRefs": ["intent-1", "run-1", "span-1"],
        "sequence": 7,
    }


class TestMalformedReceipts(unittest.TestCase):
    def test_each_missing_section_rejected(self):
        for section in ("organ", "intent", "decision", "effect", "evidence", "replay", "continuity"):
            with self.subTest(section=section):
                receipt = from_lirl(_stored())
                receipt.pop(section)
                valid, errors = validate_organism_receipt(receipt)
                self.assertFalse(valid)
                self.assertTrue(any(section in e for e in errors))

    def test_wrong_types_and_values_rejected(self):
        receipt = from_lirl(_stored())
        receipt["effect"]["performed"] = "yes"
        receipt["decision"]["outcome"] = "maybe"
        receipt["organ"]["dialect"] = "smoke-signal"
        valid, errors = validate_organism_receipt(receipt)
        self.assertFalse(valid)
        self.assertTrue(any("boolean" in e for e in errors))
        self.assertTrue(any("outcome" in e for e in errors))
        self.assertTrue(any("dialect" in e for e in errors))

    def test_non_object_input_rejected(self):
        for bad in (None, [], "receipt", 42):
            with self.subTest(bad=bad):
                valid, errors = validate_organism_receipt(bad)
                self.assertFalse(valid)


class TestMutationDetection(unittest.TestCase):
    def _receipt(self) -> dict:
        return from_lirl(_stored())

    def test_single_byte_mutation_in_every_section_detected(self):
        base = self._receipt()
        for section, field in (
            ("intent", "record_id"),
            ("decision", "outcome"),
            ("effect", "action"),
            ("evidence", "claim_label"),
            ("replay", "packet_hash"),
            ("continuity", "spine_id"),
            ("organ", "name"),
        ):
            with self.subTest(field=f"{section}.{field}"):
                mutated = json.loads(json.dumps(base))
                mutated[section][field] = str(mutated[section][field]) + "x"
                self.assertFalse(verify_receipt_id(mutated))

    def test_flipped_boolean_detected(self):
        mutated = self._receipt()
        mutated["effect"]["performed"] = not mutated["effect"]["performed"]
        self.assertFalse(verify_receipt_id(mutated))

    def test_unicode_byte_mutation_detected(self):
        stored = dict(_stored(), claimLabel="lirl:accept:mémory.write ✓")
        receipt = from_lirl(stored)
        self.assertTrue(verify_receipt_id(receipt))
        receipt["evidence"]["claim_label"] = "lirl:accept:mémory.writ ✗"
        self.assertFalse(verify_receipt_id(receipt))


class TestKeyOrderingAndIdentity(unittest.TestCase):
    def test_reordered_keys_produce_identical_canonical_form(self):
        a = {"b": 1, "a": {"d": 3, "c": [2, 1]}}
        b = {"a": {"c": [2, 1], "d": 3}, "b": 1}
        self.assertEqual(canonical_json(a), canonical_json(b))

    def test_reordered_receipt_dict_yields_same_id(self):
        receipt = from_lirl(_stored())
        shuffled = {k: receipt[k] for k in reversed(list(receipt.keys()))}
        self.assertEqual(canonical_json(shuffled), canonical_json(receipt))
        self.assertTrue(verify_receipt_id(shuffled))

    def test_key_casing_is_identity_not_alias(self):
        """Key Identity Law: camelCase vs snake_case subjects are distinct inputs."""
        camel = create_evidence_receipt(
            claim_label="cen:test", subsystem="x", evidence_refs=[],
            subject={"receiptId": "r1"}, issued_at="2026-08-24T00:00:00Z",
        )
        snake = create_evidence_receipt(
            claim_label="cen:test", subsystem="x", evidence_refs=[],
            subject={"receipt_id": "r1"}, issued_at="2026-08-24T00:00:00Z",
        )
        self.assertNotEqual(camel["subject_hash"], snake["subject_hash"])
        self.assertNotEqual(camel["receipt_id"], snake["receipt_id"])

    def test_empty_values_hash_canonical_form_never_collapsed(self):
        import hashlib

        self.assertEqual(hash_json(None), "sha3-256:" + hashlib.sha3_256(b"null").hexdigest())
        self.assertEqual(hash_json(""), "sha3-256:" + hashlib.sha3_256(b'""').hexdigest())
        self.assertEqual(hash_json([]), "sha3-256:" + hashlib.sha3_256(b"[]").hexdigest())


class TestUnknownInvariants(unittest.TestCase):
    def test_unknown_lookup_raises(self):
        registry = create_invariant_registry(CANONICAL_INVARIANTS)
        with self.assertRaisesRegex(KeyError, "invariant not found: INV-404"):
            get_invariant(registry, "INV-404")

    def test_unsupported_syntax_rejected_at_compile(self):
        # Unknown dimension words fail the compile-time allowlist.
        with self.assertRaises(ValueError):
            compile_invariant_dsl("WHEN drift > 5 THEN DENY IF VIOLATED THEN DENY")
        # Non-IDSL garbage fails immediately.
        with self.assertRaises(ValueError):
            compile_invariant_dsl("WHEN governance >= x THEN DENY IF VIOLATED THEN DENY")

    def test_unsupported_operator_fails_at_evaluate(self):
        # Faithful to the TS reference: the coarse allowlist admits "!=",
        # the clause parser rejects it when the invariant runs (late failure).
        invariant = compile_invariant_dsl("WHEN governance != 70 THEN DENY IF VIOLATED THEN DENY")
        transition = {"payload": {}, "context": {"mri_snapshot": {"governance": 70}}}
        with self.assertRaisesRegex(ValueError, "unsupported IDSL clause"):
            invariant.evaluate(transition)

    def test_no_eval_execution(self):
        with self.assertRaises(ValueError):
            compile_invariant_dsl("__import__('os').system('true')")


class TestAuthorityTokenDeclarations(unittest.TestCase):
    def test_critical_invariants_declare_tokens(self):
        for definition in CANONICAL_INVARIANTS:
            metadata = definition["receipt_metadata"]
            token = definition.get("required_authority_token")
            if metadata["severity"] == "critical":
                self.assertIn(token, AUTHORITY_TOKEN_TYPES, definition["id"])
            else:
                self.assertIsNone(token, f"{definition['id']} should not require a token")

    def test_identity_boundary_requires_vt(self):
        by_id = {item["id"]: item for item in CANONICAL_INVARIANTS}
        self.assertEqual(by_id["INV-021"]["required_authority_token"], "VT")


class TestSnapshotPayloadConflict(unittest.TestCase):
    """Precedence law: payload wins over mri_snapshot — no merging."""

    def _invariant(self):
        return compile_invariant_dsl("require governance >= 70")

    def test_payload_overrides_snapshot_when_passing(self):
        transition = {
            "payload": {"governance": 90},
            "context": {"mri_snapshot": {"governance": 10}},
        }
        self.assertTrue(self._invariant().evaluate(transition)["passed"])

    def test_payload_overrides_snapshot_when_failing(self):
        transition = {
            "payload": {"governance": 5},
            "context": {"mri_snapshot": {"governance": 99}},
        }
        result = self._invariant().evaluate(transition)
        self.assertFalse(result["passed"])
        self.assertIn("5", result["message"])  # payload value reported, not snapshot

    def test_falls_back_to_snapshot_absent_payload(self):
        transition = {"payload": {}, "context": {"mri_snapshot": {"governance": 80}}}
        self.assertTrue(self._invariant().evaluate(transition)["passed"])


class TestCrossRuntimeReplay(unittest.TestCase):
    """A Node-issued receipt must replay (verify) under Python and vice versa."""

    def _node_available(self) -> bool:
        import os

        return os.path.isfile(SOVEREIGN_X_RECEIPT_JS)

    def test_node_issued_receipt_verifies_in_python(self):
        if not self._node_available():
            self.skipTest("Sovereign-X source not mounted")
        stored = _stored()
        script = (
            f"import {{ fromLirl }} from '{SOVEREIGN_X_RECEIPT_JS}';\n"
            f"const stored = {json.dumps(stored)};\n"
            f"console.log(JSON.stringify(fromLirl(stored)));\n"
        )
        out = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            capture_output=True, text=True, timeout=60,
        )
        if out.returncode != 0:
            self.fail(f"node failed: {out.stderr[:300]}")
        node_receipt = json.loads(out.stdout.strip())
        # Python verifies a foreign-issued receipt without re-issuing it.
        self.assertTrue(verify_receipt_id(node_receipt))
        valid, errors = validate_organism_receipt(node_receipt)
        self.assertTrue(valid, errors)
        # And both runtimes agree on identity for the same input.
        self.assertEqual(node_receipt["receipt_id"], from_lirl(stored)["receipt_id"])
        # Tampered foreign receipt is rejected.
        node_receipt["effect"]["performed"] = not node_receipt["effect"]["performed"]
        self.assertFalse(verify_receipt_id(node_receipt))


if __name__ == "__main__":
    unittest.main()
