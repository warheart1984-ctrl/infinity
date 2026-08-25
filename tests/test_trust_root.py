"""Tests for trust_root — ported from trustRoot.test.ts + TS golden."""

from __future__ import annotations

import unittest

from src.trust_root import (
    as_measurement,
    build_trust_root,
    compute_h_trust_root,
    compute_measurement,
    get_trust_root,
    is_measurement,
    is_trust_root_sealed,
    reset_trust_root_for_tests,
    run_early_boot,
    seal_trust_root,
    to_ucr_context,
)

KERNEL = "sha3-256:" + "1" * 64
LAW = "sha3-256:" + "2" * 64
CORRIDORS = "sha3-256:" + "3" * 64
MANIFEST = "sha3-256:" + "4" * 64
GOLDEN_H_TRUST_ROOT = "sha3-256:19ffaf3f821f8af123ef4354c7bb0068a534abcd53be62f98d3f647704bcd432"


class TrustRootMeasurementTests(unittest.TestCase):
    def setUp(self):
        reset_trust_root_for_tests()

    def test_validates_canonical_sha3_256_measurements(self):
        self.assertTrue(is_measurement(KERNEL))
        self.assertFalse(is_measurement("sha3-256:ABC"))
        with self.assertRaisesRegex(ValueError, "invalid measurement"):
            compute_h_trust_root(
                h_kernel_image="bad", h_law_spine=LAW, h_corridors=CORRIDORS, h_boot_manifest=MANIFEST
            )

    def test_deterministic_trust_root_from_fixed_order(self):
        first = compute_h_trust_root(
            h_kernel_image=KERNEL, h_law_spine=LAW, h_corridors=CORRIDORS, h_boot_manifest=MANIFEST
        )
        second = compute_h_trust_root(
            h_kernel_image=KERNEL, h_law_spine=LAW, h_corridors=CORRIDORS, h_boot_manifest=MANIFEST
        )
        self.assertEqual(first, second)
        self.assertTrue(is_measurement(first))
        # Order matters: swapping fields changes the root.
        swapped = compute_h_trust_root(
            h_kernel_image=LAW, h_law_spine=KERNEL, h_corridors=CORRIDORS, h_boot_manifest=MANIFEST
        )
        self.assertNotEqual(first, swapped)

    def test_matches_node_golden(self):
        self.assertEqual(
            compute_h_trust_root(
                h_kernel_image=KERNEL, h_law_spine=LAW, h_corridors=CORRIDORS, h_boot_manifest=MANIFEST
            ),
            GOLDEN_H_TRUST_ROOT,
        )

    def test_compute_measurement_helper(self):
        self.assertEqual(compute_measurement("abc"), as_measurement(compute_measurement("abc")))

    def test_seals_exactly_once_and_projects_ucr_context(self):
        boot = run_early_boot(h_kernel_image=KERNEL, h_law_spine=LAW, h_corridors=CORRIDORS, h_boot_manifest=MANIFEST)
        trust_root = boot["trustRoot"]
        self.assertEqual(boot["bootResult"], "OK")
        self.assertTrue(is_trust_root_sealed())
        self.assertEqual(get_trust_root(), trust_root)
        self.assertEqual(
            to_ucr_context(trust_root),
            {"hashAlg": "sha3-256", "hLawSpine": LAW, "hCorridors": CORRIDORS, "hTrustRoot": trust_root["hTrustRoot"]},
        )
        with self.assertRaisesRegex(RuntimeError, "already sealed"):
            seal_trust_root(trust_root)
        reset_trust_root_for_tests()
        self.assertFalse(is_trust_root_sealed())
        with self.assertRaisesRegex(RuntimeError, "not sealed"):
            get_trust_root()

    def test_build_trust_root_embeds_computed_field(self):
        trust_root = build_trust_root(h_kernel_image=KERNEL, h_law_spine=LAW, h_corridors=CORRIDORS, h_boot_manifest=MANIFEST)
        self.assertEqual(trust_root["hTrustRoot"], GOLDEN_H_TRUST_ROOT)


if __name__ == "__main__":
    unittest.main()
