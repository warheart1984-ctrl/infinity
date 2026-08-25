"""Tests for governed membrane policy adoption (MGM-2)."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("AAIS_GENOME_BOOT", "warn")

from src.jarvis_membrane_authority import authorize_membrane_slot_admission
from src.multi_organism_governance_membrane_registry import adopted_policies
from src.multi_organism_governance_membrane_runtime import (
    MultiOrganismGovernanceMembraneRuntime,
    membrane_policy_record,
)
from tests.cen_test_helpers import mint_vt_token


class GovernanceMembraneAdoptTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._repo_tmp = tempfile.TemporaryDirectory()
        os.environ["AAIS_RUNTIME_DIR"] = self._tmpdir.name
        root = Path(self._repo_tmp.name)
        gov = root / "governance"
        gov.mkdir(parents=True)
        shutil.copy(
            Path(__file__).resolve().parents[1] / "governance" / "operator_membrane_registry.v1.json",
            gov / "operator_membrane_registry.v1.json",
        )
        self.runtime = MultiOrganismGovernanceMembraneRuntime(
            runtime_dir=Path(self._tmpdir.name), repo_root=root
        )
        self.candidate = {
            "candidate_id": "pcand_test001",
            "policy_kind": "composite",
            "summary": "Composite permeability policy for federated memory and exchange",
            "charter_ref": {"charter_id": "charter_test"},
            "permitted_channels": ["memory_cues", "exchange_envelope"],
            "consent_requirements": {"dual_consent": True},
            "stability_score": 0.85,
            "mgm_class": "MGM-1",
        }

    def tearDown(self):
        os.environ.pop("AAIS_RUNTIME_DIR", None)
        self._tmpdir.cleanup()
        self._repo_tmp.cleanup()

    def test_adopt_with_dual_gate(self):
        auth = authorize_membrane_slot_admission(self.candidate)
        token = mint_vt_token("operator_membrane_policy", membrane_policy_record(self.candidate))
        result = self.runtime.adopt_membrane_policy(
            self.candidate,
            operator_approved=True,
            jarvis_authorization=auth,
            session_id="mgm-test",
            authority_token=token,
        )
        self.assertEqual(result.get("outcome"), "adopted")
        self.assertEqual(len(adopted_policies(repo_root=Path(self._repo_tmp.name))), 1)
        self.assertTrue(self.runtime._overlay_path.is_file())
        # The adopted policy carries its CEN approval envelope in the registry.
        stored = adopted_policies(repo_root=Path(self._repo_tmp.name))[0]
        self.assertEqual(stored["cen_approval"]["outcome"], "approved")

    def test_adopt_blocked_without_vt_token(self):
        """INV-021: law mutations without a VT token are denied before commit."""
        auth = authorize_membrane_slot_admission(self.candidate)
        result = self.runtime.adopt_membrane_policy(
            self.candidate,
            operator_approved=True,
            jarvis_authorization=auth,
            session_id="mgm-test",
        )
        self.assertEqual(result.get("outcome"), "blocked")
        self.assertEqual(result.get("reason"), "cen_vt_required")
        self.assertIn("VT", result["cen"]["reason_detail"])
        self.assertEqual(len(adopted_policies(repo_root=Path(self._repo_tmp.name))), 0)

    def test_imxp_wrapper_allows_without_policy(self):
        from src.imxp_governance_wrapper import check_imxp_outbound_permeability

        result = check_imxp_outbound_permeability({"consent_id": "c1"})
        self.assertTrue(result.get("allowed"))


if __name__ == "__main__":
    unittest.main()
