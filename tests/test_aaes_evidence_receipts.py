"""Tests for aaes_evidence_receipts — ported from evidenceReceipts.test.ts plus
Node golden ids generated from packages/evidence-receipts/src/index.ts."""

from __future__ import annotations

import unittest

from src.aaes_evidence_receipts import (
    create_cen_evidence_receipt,
    create_evidence_receipt,
    create_mri_evidence_receipt,
    verify_receipt_hash,
)

TRUST_GOLDEN_ID = "evidence:70df716782241b7b201feeab1f5b3354dadb85c249058010c57095e7995da7f4"
CEN_GOLDEN_ID = "evidence:84c8ae8e1c50463f721079cc67e52485871e726c882f6ecbeb7ba6d0977243f9"
MRI_GOLDEN_ID = "evidence:9107db7c30ce378d8304a521c813df15677ecda6ac3ee74f9ce6a3ac1bbe95e4"


def _trust_input() -> dict:
    return {
        "claim_label": "trust-root-sealed",
        "subsystem": "trust-root",
        "evidence_refs": ["boot:ok", "measurement:h_trust_root"],
        "subject": {"hTrustRoot": "sha3-256:" + "a" * 64},
        "issued_at": "2026-08-24T12:00:00Z",
    }


class TestEvidenceReceipts(unittest.TestCase):
    def test_creates_deterministic_ids_from_claim_and_refs(self):
        first = create_evidence_receipt(**_trust_input())
        second = create_evidence_receipt(**_trust_input())
        self.assertEqual(first["receipt_id"], second["receipt_id"])
        self.assertEqual(first["claim_label"], "trust-root-sealed")
        self.assertEqual(first["evidence_refs"], ["boot:ok", "measurement:h_trust_root"])

    def test_matches_node_golden_id(self):
        receipt = create_evidence_receipt(**_trust_input())
        self.assertEqual(receipt["receipt_id"], TRUST_GOLDEN_ID)
        self.assertEqual(
            receipt["subject_hash"],
            "sha3-256:e16f5177ec380393e39c0c8353b707d9eb692dd609909168d3a1f1932e1403bc",
        )

    def test_maps_runtime_and_mri_kinds(self):
        runtime = create_evidence_receipt(
            claim_label="runtime-initialized",
            subsystem="runtime-law-spine",
            evidence_refs=["registration:ok"],
            subject={"allowed": True},
        )
        mri = create_evidence_receipt(
            claim_label="mri-continuity-report",
            subsystem="mri-instrument",
            evidence_refs=["mri:comparison"],
            subject={"continuity": 72},
        )
        generic = create_evidence_receipt(
            claim_label="unrelated-claim",
            subsystem="somewhere-else",
            evidence_refs=[],
            subject=None,
        )
        self.assertEqual(runtime["kind"], "runtime")
        self.assertEqual(mri["kind"], "mri")
        self.assertEqual(generic["kind"], "generic")

    def test_explicit_kind_overrides_inference(self):
        receipt = create_evidence_receipt(
            claim_label="anything",
            subsystem="anything",
            evidence_refs=[],
            subject={},
            kind="fault",
        )
        self.assertEqual(receipt["kind"], "fault")

    def test_cen_receipt_seals_enforcement_decision(self):
        # Keys mirror the TS CenReceiptSubject shape — the golden id was
        # generated from that exact subject object.
        cen = create_cen_evidence_receipt(
            {
                "receiptId": "cen:abc",
                "verdict": "DENY",
                "reasonCode": "INVARIANT_VIOLATION",
                "transitionId": "transition:deny",
                "receiptHash": "sha3-256:" + "a" * 64,
            }
        )
        self.assertEqual(cen["kind"], "runtime")
        self.assertIn("cen:abc", cen["evidence_refs"])
        self.assertEqual(cen["receipt_id"], CEN_GOLDEN_ID)

    def test_cen_accepts_snake_case_keys_deterministically(self):
        cen = create_cen_evidence_receipt(
            {
                "receipt_id": "cen:abc",
                "verdict": "DENY",
                "reason_code": "INVARIANT_VIOLATION",
                "transition_id": "transition:deny",
                "receipt_hash": "sha3-256:" + "a" * 64,
            }
        )
        self.assertTrue(verify_receipt_hash(cen))
        # Different subject keys -> different hash -> different id, still stable
        again = create_cen_evidence_receipt(
            {
                "receipt_id": "cen:abc",
                "verdict": "DENY",
                "reason_code": "INVARIANT_VIOLATION",
                "transition_id": "transition:deny",
                "receipt_hash": "sha3-256:" + "a" * 64,
            }
        )
        self.assertEqual(cen["receipt_id"], again["receipt_id"])

    def test_mri_receipt_seals_provenance(self):
        mri = create_mri_evidence_receipt(
            evidence_id="evidence:mri:1",
            provenance="system_log",
            recency=0.92,
            reliability=0.88,
            cross_evidence_consistency=0.81,
            subject={"continuity": 72},
        )
        self.assertEqual(mri["kind"], "mri")
        self.assertIn("evidence:mri:1", mri["evidence_refs"])
        self.assertTrue(verify_receipt_hash(mri))
        self.assertEqual(mri["receipt_id"], MRI_GOLDEN_ID)

    def test_verify_rejects_malformed_receipts(self):
        self.assertFalse(verify_receipt_hash({"subject_hash": "sha256:x", "receipt_id": "evidence:y"}))
        self.assertFalse(verify_receipt_hash({"subject_hash": "sha3-256:x", "receipt_id": "nope"}))


if __name__ == "__main__":
    unittest.main()
