"""Tests for ucr_attestation — ported from ucrAttestation.test.ts + TS golden."""

from __future__ import annotations

import unittest

from src.trust_root import (
    is_trust_root_sealed,
    reset_trust_root_for_tests,
    run_early_boot,
)
from src.ucr_attestation import (
    ERR_BOOT_NOT_SEALED,
    ERR_SIGNATURE_INVALID,
    ERR_TOKEN_EXPIRED,
    ERR_TRUST_ROOT_MISMATCH,
    DEFAULT_LAW_KEY,
    get_registered_ucr_handle,
    issue_attestation_from_sealed_trust,
    issue_attestation_token,
    placeholder_signature,
    reset_ucr_registration_for_tests,
    ucr_register,
)

KERNEL = "sha3-256:" + "a" * 64
LAW = "sha3-256:" + "b" * 64
CORRIDORS = "sha3-256:" + "c" * 64
MANIFEST = "sha3-256:" + "d" * 64
FAR_FUTURE = "2999-01-01T00:00:00.000Z"


class UcrAttestationTests(unittest.TestCase):
    def setUp(self):
        reset_trust_root_for_tests()
        reset_ucr_registration_for_tests()

    def test_refuses_registration_before_boot_is_sealed(self):
        token = issue_attestation_token(
            ucr_instance_id="ucr-1",
            build_fingerprint="build-a",
            law_key=DEFAULT_LAW_KEY,
            trust_root=KERNEL,
            corridors_hash=CORRIDORS,
            law_spine_hash=LAW,
            expires_at=FAR_FUTURE,
        )
        result = ucr_register(token)
        self.assertEqual(result["outcome"], "REFUSED")
        self.assertEqual(result["reasonCode"], ERR_BOOT_NOT_SEALED)

    def test_issues_sealed_trust_token_and_registers_handle(self):
        # Same measurement fixtures as the TS golden script (trust-root suite).
        g_kernel, g_law = "sha3-256:" + "1" * 64, "sha3-256:" + "2" * 64
        g_corridors, g_manifest = "sha3-256:" + "3" * 64, "sha3-256:" + "4" * 64
        boot = run_early_boot(h_kernel_image=g_kernel, h_law_spine=g_law, h_corridors=g_corridors, h_boot_manifest=g_manifest)
        # Fully fixed fields so the signature matches the TS golden byte-for-byte.
        token = issue_attestation_token(
            ucr_instance_id="ucr-golden",
            build_fingerprint="build-golden",
            law_key=DEFAULT_LAW_KEY,
            trust_root=boot["trustRoot"]["hTrustRoot"],
            corridors_hash=g_corridors,
            law_spine_hash=g_law,
            expires_at=FAR_FUTURE,
            issued_at="2026-08-25T00:00:00.000Z",
            nonce="noncenonce",
            token_id="tok-fixed",
        )
        # The convenience path projects the same sealed measurements.
        convenience = issue_attestation_from_sealed_trust(
            ucr_instance_id="ucr-live", build_fingerprint="build-live", expires_at=FAR_FUTURE
        )
        self.assertEqual(convenience["trustRoot"], boot["trustRoot"]["hTrustRoot"])
        self.assertTrue(is_trust_root_sealed())
        self.assertEqual(token["trustRoot"], boot["trustRoot"]["hTrustRoot"])
        # Cross-runtime golden from the TS algorithm.
        self.assertEqual(token["signature"], "ac7879f37b6f5ad3df651cfe975e0fa49b9d475beb4e49099fd3ceb8d151918d")
        result = ucr_register(token)
        self.assertEqual(result["outcome"], "OK")
        self.assertTrue(result["ucrHandle"])
        self.assertEqual(get_registered_ucr_handle(), result["ucrHandle"])

    def test_deterministic_refusal_ordering(self):
        run_early_boot(h_kernel_image=KERNEL, h_law_spine=LAW, h_corridors=CORRIDORS, h_boot_manifest=MANIFEST)

        expired = issue_attestation_from_sealed_trust(
            ucr_instance_id="ucr-expired", build_fingerprint="build-expired",
            expires_at="2000-01-01T00:00:00.000Z",
        )
        self.assertEqual(ucr_register(expired)["reasonCode"], ERR_TOKEN_EXPIRED)

        bad_signature = issue_attestation_from_sealed_trust(
            ucr_instance_id="ucr-bad-sig", build_fingerprint="build-bad-sig", expires_at=FAR_FUTURE
        )
        bad_signature["signature"] = "00"
        result = ucr_register(bad_signature)
        self.assertEqual(result["reasonCode"], ERR_SIGNATURE_INVALID)

        mismatch = issue_attestation_token(
            ucr_instance_id="ucr-mismatch", build_fingerprint="build-mismatch",
            law_key=DEFAULT_LAW_KEY,
            trust_root=run_early_boot.__module__ and __import__("src.trust_root", fromlist=["get_trust_root"]).get_trust_root()["hLawSpine"],
            corridors_hash=__import__("src.trust_root", fromlist=["get_trust_root"]).get_trust_root()["hCorridors"],
            law_spine_hash=__import__("src.trust_root", fromlist=["get_trust_root"]).get_trust_root()["hLawSpine"],
            expires_at=FAR_FUTURE,
        )
        self.assertEqual(ucr_register(mismatch)["reasonCode"], ERR_TRUST_ROOT_MISMATCH)

    def test_invalid_law_key_refused(self):
        run_early_boot(h_kernel_image=KERNEL, h_law_spine=LAW, h_corridors=CORRIDORS, h_boot_manifest=MANIFEST)
        token = issue_attestation_token(
            ucr_instance_id="ucr-zero", build_fingerprint="b",
            law_key="0" * 32,
            trust_root=get_sealed()["hTrustRoot"],
            corridors_hash=get_sealed()["hCorridors"],
            law_spine_hash=get_sealed()["hLawSpine"],
            expires_at=FAR_FUTURE,
        )
        self.assertEqual(ucr_register(token)["reasonCode"], 1001)  # ERR_LAW_KEY_INVALID


def get_sealed():
    from src.trust_root import get_trust_root

    return get_trust_root()


if __name__ == "__main__":
    unittest.main()
