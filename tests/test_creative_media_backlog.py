"""Focused tests for creative media backlog: compose, mandala, spatial couple, voice→mix."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.capabilities.adaptive_music_compose import AdaptiveMusicComposeCapability
from src.capabilities.human_voice_speakers_pipeline import HumanVoiceSpeakersPipelineCapability
from src.capabilities.mandala_visual_sync import MandalaVisualSyncCapability
from src.holo_runtime_4d_spatial_vision import HoloRuntime4dSpatialVisionEngine
from src.spatial_score_couple import apply_spatial_score_couple, visibility_axes_from_probe
from src.Spatial_reasoning import SpatialReasoningPlug


class TestSpatialScoreCouple(unittest.TestCase):
    def test_visibility_raises_tension_when_mostly_occluded(self) -> None:
        axes = visibility_axes_from_probe(
            {"visible_count": 1, "occluded_count": 3, "space_id": "arena", "tick": 1}
        )
        self.assertTrue(axes["ok"])
        self.assertEqual(axes["mood"], "intense")
        self.assertGreaterEqual(axes["tension"], 70)

    def test_apply_fill_missing_preserves_operator_mood(self) -> None:
        coupled = apply_spatial_score_couple(
            {
                "mood": "happy",
                "holo_probe": {"visible_count": 0, "occluded_count": 4},
            }
        )
        self.assertEqual(coupled["mood"], "happy")
        self.assertIn("spatial_score_couple_receipt", coupled)

    def test_apply_override_forces_coupled_mood(self) -> None:
        coupled = apply_spatial_score_couple(
            {
                "mood": "happy",
                "couple_mode": "override",
                "holo_probe": {"visible_count": 0, "occluded_count": 4},
            }
        )
        self.assertEqual(coupled["mood"], "intense")


class TestSpatialPlugLiveSpaceBinding(unittest.TestCase):
    def test_prefers_live_space_over_demo_seed(self) -> None:
        plug = SpatialReasoningPlug()
        plug.build_space(
            "live_ops",
            nodes=[
                {"id": "observer", "x": 0, "y": 0, "z": 0},
                {"id": "target", "x": 2, "y": 0, "z": 0},
            ],
            edges=[{"from": "observer", "to": "target", "weight": 2}],
        )
        engine = HoloRuntime4dSpatialVisionEngine(plug=plug)
        frame = engine.probe({"seed_demo": True, "observer": "observer", "targets": "target"})
        self.assertEqual(frame["space_id"], "live_ops")
        self.assertIn(frame["space_binding"], {"live_spatial_plug", "live_spatial_plug_redirect"})
        self.assertNotEqual(frame["space_id"], "holo_rt4d_demo")


class TestAdaptiveMusicComposeCapability(unittest.TestCase):
    def test_status(self) -> None:
        result = AdaptiveMusicComposeCapability().execute("status", {})
        self.assertTrue(result.get("ok"))
        self.assertTrue((result.get("data") or {}).get("execution_ready"))

    def test_compose_includes_mandala_plan(self) -> None:
        result = AdaptiveMusicComposeCapability().execute(
            "compose",
            {
                "mood": "focused",
                "energy": 55,
                "tension": 35,
                "duration_sec": 3,
                "include_audio": False,
                "include_mandala_sync": True,
                "description": "bridge compose test",
            },
        )
        self.assertTrue(result.get("ok"), result)
        data = result.get("data") or {}
        self.assertEqual(data.get("mood"), "focused")
        self.assertIn("mandala_visual_plan", data)
        self.assertTrue((data.get("mandala_visual_plan") or {}).get("ok"))


class TestMandalaVisualSyncCapability(unittest.TestCase):
    def test_sync_plan_only(self) -> None:
        result = MandalaVisualSyncCapability().execute(
            "sync",
            {"mood": "intense", "bpm": 140, "energy": 80, "tension": 70},
        )
        self.assertTrue(result.get("ok"))
        data = result.get("data") or {}
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("plan_version"), "mandala_visual_adaptation.v1")
        self.assertFalse((data.get("consumer_seam") or {}).get("owns_pixels"))


class TestHumanVoiceSpeakersPipeline(unittest.TestCase):
    def test_guided_pipeline_speakers_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = HumanVoiceSpeakersPipelineCapability().execute(
                "run",
                {
                    "fixture": "notes-demo-redacted",
                    "auto_signoff": True,
                    "extraction_root": str(root / "extract"),
                    "speakers_root": str(root / "speakers"),
                    "runtime_context": "test_harness",
                },
            )
            self.assertTrue(result.get("ok"), result)
            data = result.get("data") or {}
            self.assertEqual(data.get("status"), "speakers_ready")
            self.assertTrue(data.get("profile_id"))
            self.assertTrue(data.get("constraints_path"))
            self.assertTrue(Path(data["constraints_path"]).is_file())


class TestCreativeBridgeWiring(unittest.TestCase):
    def test_bridge_exposes_compose_mandala_voice_story(self) -> None:
        from src.jarvis_operator import JarvisOperator

        operator = JarvisOperator()
        snapshot = operator.capability_bridge_snapshot()
        caps = {item.get("id"): item for item in (snapshot.get("available_capabilities") or [])}
        for expected in (
            "adaptive_music",
            "mandala",
            "human_voice_speakers",
            "story_forge",
            "beatbox",
            "speakers",
            "holo_rt4d",
        ):
            self.assertIn(expected, caps, f"missing capability {expected}")

        mandala = caps["mandala"]
        actions = mandala.get("actions") or []
        self.assertTrue(actions)
        self.assertEqual(actions[0].get("tool"), "mandala_visual_sync")

        executed = operator.capability_bridge.execute_selection(
            "mandala",
            "sync",
            args={"mood": "calm", "bpm": 90, "energy": 40, "tension": 20},
            runtime_context="operator_runtime",
        )
        tool_result = executed.get("tool_result") or {}
        self.assertEqual(tool_result.get("type"), "mandala_visual_sync")
        self.assertEqual(tool_result.get("status"), "completed")

    def test_media_workflow_templates_present(self) -> None:
        from app.workflow_templates import WORKFLOW_TEMPLATES, get_workflow_template

        ids = {item["id"] for item in WORKFLOW_TEMPLATES}
        for expected in (
            "sovereign-sound-loop",
            "spatial-score-couple",
            "voice-to-mix",
            "imagine-audio-pack",
        ):
            self.assertIn(expected, ids)
            template = get_workflow_template(expected)
            self.assertEqual(template.get("category"), "media")


class TestSovereignSoundLoop(unittest.TestCase):
    def test_loop_without_holo(self) -> None:
        from src.sovereign_sound_loop import run_sovereign_sound_loop

        result = run_sovereign_sound_loop(
            {
                "mood": "calm",
                "energy": 40,
                "tension": 25,
                "duration_sec": 3,
                "include_audio": False,
                "run_holo_probe": False,
                "description": "sovereign loop test",
            }
        )
        self.assertTrue(result.get("ok"))
        self.assertIn("compose", result)
        self.assertIn("mandala_visual_plan", result)
        self.assertIsNone(result.get("holo_probe"))


if __name__ == "__main__":
    unittest.main()
