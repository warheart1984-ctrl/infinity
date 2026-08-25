"""Dominance tests: ALL authoritative law-mutation paths pass through CEN.

The invariant under test is not "the runtime consults CEN" — it is that the
law-state SINK itself refuses any write without a valid CEN approval bound
to the exact record. Alternate write paths (maintenance scripts, recovery
routines, direct registry calls, forged approvals) are dominated.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("AAIS_GENOME_BOOT", "warn")

from src.cen_governance_bridge import (
    CenGovernanceBridge,
    cen_governance_bridge,
    classify_transition,
    law_state_transition_id,
)
from src.multi_organism_governance_membrane_registry import (
    adopted_policies,
    save_adopted_policy,
)
from src.multi_organism_governance_membrane_runtime import (
    MultiOrganismGovernanceMembraneRuntime,
    membrane_policy_record,
)
from tests.cen_test_helpers import mint_vt_token


def _candidate() -> dict:
    return {
        "candidate_id": "pcand_dom001",
        "policy_kind": "composite",
        "summary": "Composite permeability policy for dominance testing",
        "charter_ref": {"charter_id": "charter_test"},
        "permitted_channels": ["memory_cues", "exchange_envelope"],
        "consent_requirements": {"dual_consent": True},
        "stability_score": 0.85,
        "mgm_class": "MGM-1",
    }


class DominanceTests(unittest.TestCase):
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
        from src.jarvis_membrane_authority import authorize_membrane_slot_admission

        self.root = root
        self.runtime = MultiOrganismGovernanceMembraneRuntime(
            runtime_dir=Path(self._tmpdir.name), repo_root=root
        )
        self.candidate = _candidate()
        self.auth = authorize_membrane_slot_admission(self.candidate)

    def tearDown(self):
        os.environ.pop("AAIS_RUNTIME_DIR", None)
        self._tmpdir.cleanup()
        self._repo_tmp.cleanup()

    def _adopt(self, **kwargs):
        kwargs.setdefault("operator_approved", True)
        kwargs.setdefault("jarvis_authorization", self.auth)
        return self.runtime.adopt_membrane_policy(
            self.candidate, session_id="dominance-test", **kwargs
        )

    # ---------------------------------------------------------- happy path

    def test_valid_vt_adopts_and_persists(self):
        token = mint_vt_token("operator_membrane_policy", membrane_policy_record(self.candidate))
        result = self._adopt(authority_token=token)
        self.assertEqual(result["outcome"], "adopted")
        stored = adopted_policies(repo_root=self.root)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["cen_approval"]["outcome"], "approved")

    # ---------------------------------------------------------- VT failures

    def test_absent_vt_denied_before_commit(self):
        result = self._adopt()
        self.assertEqual(result["outcome"], "blocked")
        self.assertEqual(result["reason"], "cen_vt_required")
        self.assertIn("VT", result["cen"]["reason_detail"])
        self.assertEqual(adopted_policies(repo_root=self.root), [])

    def test_wrong_token_type_denied(self):
        token = mint_vt_token("operator_membrane_policy", membrane_policy_record(self.candidate), token_id="ft-1")
        token["tokenType"] = "FT"
        result = self._adopt(authority_token=token)
        self.assertEqual(result["outcome"], "blocked")
        self.assertIn("VT", result["cen"]["reason_detail"])

    def test_expired_vt_denied(self):
        from src.cen_governance_bridge import issue_authority_token

        record = membrane_policy_record(self.candidate)
        token = issue_authority_token(
            token_id="vt-old", token_type="VT", scope=["law:mutate"],
            transition_id=law_state_transition_id("operator_membrane_policy", record),
            expires_at="2000-01-01T00:00:00.000Z",
        )
        result = self._adopt(authority_token=token)
        self.assertEqual(result["outcome"], "blocked")
        self.assertEqual(result["cen"]["reason_code"], "TOKEN_EXPIRED")

    def test_wrong_scope_vt_denied(self):
        from src.cen_governance_bridge import issue_authority_token

        record = membrane_policy_record(self.candidate)
        token = issue_authority_token(
            token_id="vt-narrow", token_type="VT", scope=["memory:read"],
            transition_id=law_state_transition_id("operator_membrane_policy", record),
            expires_at="2999-01-01T00:00:00.000Z",
        )
        result = self._adopt(authority_token=token)
        self.assertEqual(result["outcome"], "blocked")
        self.assertEqual(result["cen"]["reason_code"], "TOKEN_SCOPE_DENIED")

    def test_invalid_signature_vt_denied(self):
        token = mint_vt_token("operator_membrane_policy", membrane_policy_record(self.candidate))
        token["signature"] = "f" * 64
        result = self._adopt(authority_token=token)
        self.assertEqual(result["outcome"], "blocked")
        self.assertEqual(result["cen"]["reason_code"], "TOKEN_INVALID_SIGNATURE")

    def test_vt_bound_to_other_record_denied(self):
        other = dict(membrane_policy_record(self.candidate), summary="a different policy entirely")
        token = mint_vt_token("operator_membrane_policy", other)
        result = self._adopt(authority_token=token)
        self.assertEqual(result["outcome"], "blocked")

    # -------------------------------------------------- sink-level dominance

    def test_direct_sink_write_without_approval_refused(self):
        """Alternate path: a script calls save_adopted_policy directly."""
        policy = dict(membrane_policy_record(self.candidate), policy_id="policy_rogue1")
        with self.assertRaisesRegex(PermissionError, "CEN-dominated law state write refused"):
            save_adopted_policy(policy, repo_root=self.root)
        self.assertEqual(adopted_policies(repo_root=self.root), [])

    def test_forged_approval_refused_at_sink(self):
        policy = dict(
            membrane_policy_record(self.candidate),
            policy_id="policy_rogue2",
            cen_approval={"outcome": "approved", "cen_receipt_hash": "sha3-256:x"},
        )
        with self.assertRaisesRegex(PermissionError, "does not bind"):
            save_adopted_policy(policy, repo_root=self.root)
        self.assertEqual(adopted_policies(repo_root=self.root), [])

    def test_approval_for_tampered_record_refused(self):
        token = mint_vt_token("operator_membrane_policy", membrane_policy_record(self.candidate))
        approval = cen_governance_bridge.gate_law_state_write(
            sink="operator_membrane_policy", record=membrane_policy_record(self.candidate),
            authority_token=token,
        )
        self.assertEqual(approval["outcome"], "approved")
        tampered = dict(membrane_policy_record(self.candidate), stability_score=0.99)
        policy = dict(tampered, policy_id="policy_rogue3", cen_approval=approval)
        with self.assertRaisesRegex(PermissionError, "does not bind"):
            save_adopted_policy(policy, repo_root=self.root)

    # ------------------------------------------------------ non-law actions

    def test_runtime_actions_do_not_require_vt(self):
        bridge = CenGovernanceBridge()
        approval = bridge.gate_commit(
            transition_id="transition:ordinary",
            transition_type="runtime_action",
            payload={"continuity": 74},
            requested_capabilities=["state:commit"],
            granted_capabilities=["workflow:execute", "state:commit"],
            authority_token=None,
        )
        self.assertEqual(approval["outcome"], "approved")

    # ------------------------------------------------------------ fail closed

    def test_cen_failure_fails_closed(self):
        broken_bridge = CenGovernanceBridge()
        def boom(_transition):
            raise RuntimeError("invariant engine exploded")
        broken_bridge._node._invariants = [type("B", (), {"invariant_id": "x", "evaluate": staticmethod(boom)})()]
        approval = broken_bridge.gate_commit(
            transition_id="transition:boom",
            transition_type="runtime_action",
            payload={"continuity": 74},
            requested_capabilities=["state:commit"],
            granted_capabilities=["workflow:execute", "state:commit"],
        )
        self.assertEqual(approval["outcome"], "denied")
        self.assertEqual(approval["reason"], "cen_failed_closed")
        self.assertFalse(approval["committed"])

    # ---------------------------------------------------------------- TOCTOU

    def test_commit_binds_exact_approved_object(self):
        bridge = CenGovernanceBridge()
        payload = {"continuity": 80}
        approval = bridge.gate_commit(
            transition_id="transition:toctou",
            transition_type="runtime_action",
            payload=payload,
            requested_capabilities=["state:commit"],
            granted_capabilities=["workflow:execute", "state:commit"],
        )
        committed = []
        # Mutate the caller's object AFTER approval — must not affect commit.
        payload["continuity"] = 1
        result = bridge.commit_approved(approval, lambda frozen: committed.append(frozen))
        self.assertTrue(result["committed"])
        self.assertEqual(committed[0]["continuity"], 80)  # frozen copy, not mutated ref

    def test_post_approval_hash_mismatch_refused(self):
        bridge = CenGovernanceBridge()
        approval = bridge.gate_commit(
            transition_id="transition:mute",
            transition_type="runtime_action",
            payload={"continuity": 80},
            requested_capabilities=["state:commit"],
            granted_capabilities=["workflow:execute", "state:commit"],
        )
        approval["frozen_payload"] = {"continuity": 1}  # swap after approval
        result = bridge.commit_approved(approval, lambda _frozen: None)
        self.assertEqual(result["reason"], "toctou_hash_mismatch")

    # ------------------------------------------------------- classification

    def test_classification_precedence(self):
        self.assertEqual(classify_transition(bundle={"constitutional_class": "law_mutation"}), "law_mutation")
        self.assertEqual(classify_transition(args={"transition_type": "runtime_action"}), "runtime_action")
        self.assertEqual(classify_transition(), "runtime_action")


if __name__ == "__main__":
    unittest.main()
