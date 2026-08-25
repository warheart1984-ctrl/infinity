"""Integration: trust root -> UCR attestation -> CEN-gated commit.

The pairing under test: a commit that requires an attested execution
instance is refused until the organism boots, seals its trust root, and
registers an attested UCR instance. Attestation feeds the admission
boundary; no attestation, no commit.
"""

from __future__ import annotations

import unittest

from src.cen_governance_bridge import CenGovernanceBridge
from src.trust_root import (
    get_trust_root,
    is_trust_root_sealed,
    reset_trust_root_for_tests,
    run_early_boot,
)
from src.ucr_attestation import (
    get_registered_ucr_handle,
    issue_attestation_from_sealed_trust,
    reset_ucr_registration_for_tests,
    ucr_register,
)

KERNEL = "sha3-256:" + "a" * 64
LAW = "sha3-256:" + "b" * 64
CORRIDORS = "sha3-256:" + "c" * 64
MANIFEST = "sha3-256:" + "d" * 64


def _gate(bridge: CenGovernanceBridge, **kwargs) -> dict:
    return bridge.gate_commit(
        transition_id="transition:attested-commit",
        transition_type="runtime_action",
        payload={"continuity": 80},
        requested_capabilities=["state:commit"],
        granted_capabilities=["workflow:execute", "state:commit"],
        **kwargs,
    )


class CenTrustAttestationIntegrationTests(unittest.TestCase):
    def setUp(self):
        reset_trust_root_for_tests()
        reset_ucr_registration_for_tests()
        self.bridge = CenGovernanceBridge()

    def test_unsealed_organism_cannot_commit_attested_transition(self):
        result = _gate(self.bridge, require_ucr_attested=True)
        self.assertEqual(result["outcome"], "denied")
        self.assertEqual(result["reason"], "ucr_not_attested")
        self.assertFalse(result["committed"])
        # Refusal receipt chained even for attestation refusals.
        self.assertIn("cen_receipt_hash", result)
        self.assertIn("evidence_receipt_id", result)

    def test_sealed_but_unregistered_still_refused(self):
        run_early_boot(h_kernel_image=KERNEL, h_law_spine=LAW, h_corridors=CORRIDORS, h_boot_manifest=MANIFEST)
        self.assertTrue(is_trust_root_sealed())
        result = _gate(self.bridge, require_ucr_attested=True)
        self.assertEqual(result["reason"], "ucr_not_attested")

    def test_attested_instance_commits(self):
        run_early_boot(h_kernel_image=KERNEL, h_law_spine=LAW, h_corridors=CORRIDORS, h_boot_manifest=MANIFEST)
        token = issue_attestation_from_sealed_trust(
            ucr_instance_id="ucr-live", build_fingerprint="build-live",
            expires_at="2999-01-01T00:00:00.000Z",
        )
        registered = ucr_register(token)
        self.assertEqual(registered["outcome"], "OK")
        handle = get_registered_ucr_handle()
        self.assertTrue(handle)

        committed = []
        result = self.bridge.gate_commit(
            transition_id="transition:attested-commit",
            transition_type="runtime_action",
            payload={"continuity": 80},
            requested_capabilities=["state:commit"],
            granted_capabilities=["workflow:execute", "state:commit"],
            require_ucr_attested=True,
            authority_token=None,
        )
        approval = self.bridge.commit_approved(result, lambda frozen: committed.append(frozen))
        self.assertEqual(result["outcome"], "approved")
        self.assertTrue(approval["committed"])
        self.assertEqual(committed[0]["continuity"], 80)

    def test_attestation_gate_is_opt_in(self):
        """Ordinary commits (require_ucr_attested=False) are unaffected."""
        result = _gate(self.bridge)
        self.assertEqual(result["outcome"], "approved")


if __name__ == "__main__":
    unittest.main()
