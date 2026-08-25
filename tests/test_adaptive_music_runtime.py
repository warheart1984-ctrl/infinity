"""Tests for ConstitutionalAdaptiveAudioRuntime."""

from __future__ import annotations

import tempfile
import unittest
import wave
from pathlib import Path

from src.adaptive_music_runtime import (
    ConstitutionalAdaptiveAudioRuntime,
    compose_and_mix,
)
from src.capabilities.beatbox_score import BeatboxScoreCapability
from src.capabilities.speakers_mix import SpeakersMixCapability


def _wav_duration(path: str) -> float:
    with wave.open(path, "rb") as handle:
        frames = handle.getnframes()
        rate = handle.getframerate() or 1
    return frames / float(rate)


class TestAdaptiveMusicRuntime(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp(prefix="aais_adaptive_music_"))
        self.runtime = ConstitutionalAdaptiveAudioRuntime(output_root=self.temp)

    def test_invalid_mood_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            self.runtime.compose_score({"mood": "jazz-fusion", "duration_sec": 2})

    def test_different_moods_produce_different_audio(self) -> None:
        calm = self.runtime.compose_and_mix(
            {"mood": "calm", "duration_sec": 2, "session_id": "calm-a", "bpm": 80},
            include_audio=False,
        )
        intense = self.runtime.compose_and_mix(
            {"mood": "intense", "duration_sec": 2, "session_id": "intense-a", "bpm": 140},
            include_audio=False,
        )
        self.assertGreater(_wav_duration(calm.mix_path), 0)
        self.assertGreater(_wav_duration(intense.mix_path), 0)
        self.assertNotEqual(calm.mix_sha256, intense.mix_sha256)
        self.assertTrue(Path(calm.stem_paths["kick"]).is_file())
        self.assertTrue(Path(calm.stem_paths["voice"]).is_file())
        self.assertEqual(calm.cue_plan.get("status"), "rendered")
        self.assertNotEqual(calm.cue_plan.get("status"), "governed_posture")

    def test_beatbox_capability_executes_score(self) -> None:
        result = BeatboxScoreCapability().execute(
            "score",
            {"mood": "focused", "duration_sec": 2, "session_id": "cap-score", "bpm": 100},
        )
        self.assertTrue(result.get("ok"))
        data = result.get("data") or {}
        self.assertNotEqual((data.get("cue_plan") or {}).get("status"), "governed_posture")
        self.assertTrue(Path(str(data.get("music_stem_path") or "")).is_file())

    def test_speakers_capability_mixes_stems(self) -> None:
        scored = self.runtime.compose_score(
            {"mood": "happy", "duration_sec": 2, "session_id": "cap-mix", "bpm": 120}
        )
        result = SpeakersMixCapability().execute("mix", scored)
        self.assertTrue(result.get("ok"))
        data = result.get("data") or {}
        self.assertNotEqual((data.get("mix_plan") or {}).get("status"), "governed_posture")
        self.assertTrue(Path(str(data.get("mix_path") or "")).is_file())
        self.assertGreater(_wav_duration(str(data["mix_path"])), 0)

    def test_module_compose_and_mix_helper(self) -> None:
        payload = compose_and_mix(
            {"mood": "calm", "duration_sec": 2, "session_id": "helper-a", "bpm": 90},
            include_audio=False,
        )
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["score_owned_by"], "beatbox")
        self.assertEqual(payload["mix_owned_by"], "speakers")
        self.assertGreater(payload["duration_sec"], 0)


if __name__ == "__main__":
    unittest.main()
