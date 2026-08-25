"""Tests for the IMXP Mandala adapter (packet admission + grant->policy mapping)."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("AAIS_GENOME_BOOT", "warn")

from src.imxp_mandala_adapter import (
    ImxpMandalaAdapter,
    compute_payload_hash,
    normalize_packet,
    validate_mandala_packet,
)
from src.jarvis_membrane_authority import authorize_membrane_slot_admission


def _make_packet(**overrides):
    payload = {"content": "hello", "language": "en"}
    packet = {
        "protocol": "mandala-link/1",
        "version": 1,
        "packet_id": "pkt-0001",
        "sender": "peer-a",
        "recipient": "peer-b",
        "type": "text",
        "hop_limit": 3,
        "path": ["peer-a"],
        "timestamp": 1787355960,
        "payload_hash": compute_payload_hash(payload),
        "payload": payload,
        "signature": "ed25519:test",
    }
    packet.update(overrides)
    return packet


def _make_grant():
    return {
        "grantId": "grant-001",
        "peerId": "peer-a",
        "capabilityType": "text",
        "direction": "both",
        "contextProfile": "home",
        "grantedBy": "human",
        "pairingMethod": "qr",
        "expiresAt": None,
        "revoked": False,
    }


class ImxpMandalaAdapterTests(unittest.TestCase):
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
        from src.multi_organism_governance_membrane_runtime import MultiOrganismGovernanceMembraneRuntime

        self.runtime = MultiOrganismGovernanceMembraneRuntime(
            runtime_dir=Path(self._tmpdir.name), repo_root=root
        )
        self.adapter = ImxpMandalaAdapter(runtime=self.runtime)

    def tearDown(self):
        os.environ.pop("AAIS_RUNTIME_DIR", None)
        self._tmpdir.cleanup()
        self._repo_tmp.cleanup()

    def test_validate_accepts_wire_spec_packet(self):
        ok, errors = validate_mandala_packet(_make_packet())
        self.assertTrue(ok, errors)

    def test_validate_accepts_camel_case_packet(self):
        camel = {
            "protocol": "mandala-link/1",
            "version": 1,
            "packetId": "pkt-0002",
            "sender": "peer-a",
            "type": "image",
            "hopLimit": 3,
            "path": ["peer-a"],
            "timestamp": 1787355960,
            "payloadHash": compute_payload_hash({"mime": "image/jpeg"}),
            "payload": {"mime": "image/jpeg"},
            "signature": "ed25519:test",
        }
        normalized = normalize_packet(camel)
        self.assertEqual(normalized["packet_id"], "pkt-0002")
        ok, errors = validate_mandala_packet(normalized)
        self.assertTrue(ok, errors)

    def test_validate_rejects_hash_mismatch(self):
        bad = _make_packet(payload={"tampered": True})
        ok, errors = validate_mandala_packet(bad)
        self.assertFalse(ok)
        self.assertTrue(any("payload_hash" in e for e in errors))

    def test_admit_blocked_for_invalid_packet(self):
        result = self.adapter.admit_packet(_make_packet(protocol="other/1"))
        self.assertEqual(result.get("outcome"), "blocked")
        self.assertEqual(result.get("reason"), "invalid_packet")

    def test_admit_admits_valid_packet_without_policy(self):
        result = self.adapter.admit_packet(_make_packet(), session_id="mgm-mandala")
        self.assertEqual(result.get("outcome"), "admitted")
        self.assertEqual(result.get("mgm_class"), "MGM-3")
        self.assertEqual(result.get("channel"), "exchange_envelope")
        self.assertEqual(result["drift_event"].get("source"), "mandala_link")

    def test_admit_respects_adopted_dual_consent_policy(self):
        candidate = {
            "candidate_id": "pcand_test002",
            "policy_kind": "composite",
            "summary": "Composite permeability policy for federated memory and exchange",
            "charter_ref": {"charter_id": "charter_test"},
            "permitted_channels": ["memory_cues", "exchange_envelope"],
            "consent_requirements": {"dual_consent": True},
            "stability_score": 0.85,
            "mgm_class": "MGM-1",
        }
        auth = authorize_membrane_slot_admission(candidate)
        from src.multi_organism_governance_membrane_runtime import membrane_policy_record
        from tests.cen_test_helpers import mint_vt_token

        token = mint_vt_token("operator_membrane_policy", membrane_policy_record(candidate))
        adopted = self.runtime.adopt_membrane_policy(
            candidate, operator_approved=True, jarvis_authorization=auth, session_id="mgm-test", authority_token=token
        )
        self.assertEqual(adopted.get("outcome"), "adopted")
        blocked = self.adapter.admit_packet(_make_packet())
        self.assertEqual(blocked.get("outcome"), "blocked")
        self.assertEqual(blocked.get("permeability", {}).get("reason"), "dual_consent_required")
        ticketed = self.adapter.admit_packet(_make_packet(capability_ticket="consent-1"))
        self.assertEqual(ticketed.get("outcome"), "admitted")

    def test_grant_maps_to_candidate(self):
        candidate = self.adapter.grant_to_policy_candidate(_make_grant())
        self.assertNotEqual(candidate.get("outcome"), "blocked")
        self.assertEqual(candidate.get("policy_kind"), "exchange_permeability")
        self.assertIn("exchange_envelope", candidate.get("permitted_channels"))
        self.assertEqual(candidate.get("mgm_class"), "MGM-1")
        self.assertEqual(candidate["mandala_grant"]["grant_id"], "grant-001")
        self.assertGreaterEqual(candidate.get("stability_score"), 0.8)

    def test_revoked_grant_blocked(self):
        grant = dict(_make_grant(), revoked=True)
        result = self.adapter.grant_to_policy_candidate(grant)
        self.assertEqual(result.get("outcome"), "blocked")

    def test_multi_channel_grant_is_composite(self):
        grant = dict(_make_grant(), capabilities=[{"type": "text"}, {"type": "sensor"}])
        candidate = self.adapter.grant_to_policy_candidate(grant)
        self.assertEqual(candidate.get("policy_kind"), "composite")
        self.assertIn("memory_cues", candidate.get("permitted_channels"))

    def test_full_dual_gate_proposal(self):
        result = self.adapter.propose_policy_from_grant(_make_grant(), operator_approved=False)
        self.assertEqual(result.get("outcome"), "proposed")
        candidate = self.adapter.grant_to_policy_candidate(_make_grant())
        persist = getattr(self.runtime, "_persist_candidate")
        persist(candidate)
        auth = authorize_membrane_slot_admission(candidate)
        from src.multi_organism_governance_membrane_runtime import membrane_policy_record
        from tests.cen_test_helpers import mint_vt_token

        token = mint_vt_token("operator_membrane_policy", membrane_policy_record(candidate), token_id="vt-grant")
        adopted = self.adapter.propose_policy_from_grant(
            _make_grant(),
            operator_approved=True,
            jarvis_authorization=auth,
            session_id="mgm-mandala",
            authority_token=token,
        )
        self.assertEqual(adopted.get("outcome"), "adopted")


if __name__ == "__main__":
    unittest.main()
