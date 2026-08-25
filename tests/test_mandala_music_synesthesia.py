"""Tests for MandalaVisualAdaptationLayer (score → visual sync)."""

from __future__ import annotations

import unittest

from src.mandala_music_synesthesia import (
    ADAPTER_VERSION,
    PLAN_VERSION,
    MandalaVisualAdaptationLayer,
    derive_visual_adaptation,
)


class TestMandalaMusicSynesthesia(unittest.TestCase):
    def setUp(self) -> None:
        self.layer = MandalaVisualAdaptationLayer()

    def test_same_cues_yield_same_plan(self) -> None:
        payload = {
            "mood": "focused",
            "bpm": 100,
            "energy": 62,
            "tension": 40,
            "focus": 60,
            "valence": 0.5,
            "duration_sec": 6,
            "cue_plan": {"status": "rendered", "cue_count": 4, "cues": [{}, {}, {}, {}]},
            "mix_sha256": "abc",
            "session_id": "sync-a",
        }
        a = self.layer.derive_visual_adaptation(payload).to_dict()
        b = derive_visual_adaptation(payload)
        self.assertTrue(a["ok"])
        self.assertEqual(a["plan_version"], PLAN_VERSION)
        self.assertEqual(a["adapter_version"], ADAPTER_VERSION)
        self.assertEqual(a["plan_id"], b["plan_id"])
        self.assertEqual(a["lighting"], b["lighting"])
        self.assertEqual(a["camera"], b["camera"])
        self.assertEqual(a["glyph_particle"], b["glyph_particle"])
        self.assertEqual(a["renderer_hooks"], b["renderer_hooks"])
        self.assertFalse(a["consumer_seam"]["owns_pixels"])
        self.assertEqual(a["consumer_seam"]["status"], "plan_only")

    def test_mood_and_bpm_alter_plan_fields(self) -> None:
        calm = self.layer.derive_visual_adaptation(
            {
                "mood": "calm",
                "bpm": 80,
                "energy": 30,
                "tension": 20,
                "focus": 70,
                "valence": 0.6,
            }
        ).to_dict()
        intense = self.layer.derive_visual_adaptation(
            {
                "mood": "intense",
                "bpm": 150,
                "energy": 90,
                "tension": 85,
                "focus": 40,
                "valence": 0.2,
            }
        ).to_dict()
        self.assertNotEqual(calm["plan_id"], intense["plan_id"])
        self.assertNotEqual(calm["lighting"]["hue_deg"], intense["lighting"]["hue_deg"])
        self.assertLess(calm["lighting"]["intensity"], intense["lighting"]["intensity"])
        self.assertLess(calm["camera"]["pulse_hz"], intense["camera"]["pulse_hz"])
        self.assertEqual(calm["camera"]["beat_period_ms"], 750)
        self.assertEqual(intense["camera"]["beat_period_ms"], 400)
        self.assertLess(calm["glyph_particle"]["energy"], intense["glyph_particle"]["energy"])
        self.assertEqual(calm["lighting"]["temperature"], "cool")
        self.assertEqual(intense["lighting"]["temperature"], "warm")

    def test_invalid_mood_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            self.layer.derive_visual_adaptation({"mood": "jazz-fusion", "bpm": 100})

    def test_nested_cue_plan_and_scene_state(self) -> None:
        plan = self.layer.plan_from_cue_plan(
            {"status": "rendered", "cue_count": 2, "session_id": "s1", "scene_id": "op"},
            scene={"mood": "happy", "bpm": 120, "energy": 70, "tension": 35, "valence": 0.8},
        ).to_dict()
        self.assertEqual(plan["mood"], "happy")
        self.assertEqual(plan["bpm"], 120)
        self.assertEqual(plan["source"]["cue_count"], 2)
        self.assertIn("lighting_intensity", plan["renderer_hooks"])
        self.assertIn("particle_energy", plan["renderer_hooks"])
        self.assertIn("camera_pulse_hz", plan["renderer_hooks"])


if __name__ == "__main__":
    unittest.main()
