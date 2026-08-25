"""Beatbox downstream lane capability adapter."""

# Mythic: Beatbox Score
# Engineering: BeatboxScoreEngine
from __future__ import annotations

from typing import Any

from src.capability_module import AAISCapabilityModule

BEATBOX_LANE_COMPONENT_ID = "jarvis.capability.beatbox_score"


class BeatboxScoreCapability(AAISCapabilityModule):
    module_name = "beatbox_score"
    supported_actions = frozenset({"score", "status"})

    def __init__(self) -> None:
        super().__init__(provider_name="aais_beatbox")
        self.handlers = {"score": self._handle_score, "status": self._handle_status}

    def _handle_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        from src.beatbox_lane_organ import build_beatbox_lane_status

        return {
            "lane": build_beatbox_lane_status(),
            "standalone_lane": True,
            "execution_ready": True,
            "engine": "arrangement_pcm.v1",
        }

    def _handle_score(self, payload: dict[str, Any]) -> dict[str, Any]:
        from src.adaptive_music_runtime import compose_score

        scored = compose_score(payload)
        return {
            "cue_plan": scored.get("cue_plan") or {},
            "session_id": scored.get("session_id"),
            "scene_id": scored.get("scene_id"),
            "mood": scored.get("mood"),
            "bpm": scored.get("bpm"),
            "duration_sec": scored.get("duration_sec"),
            "music_stem_path": scored.get("music_stem_path"),
            "voice_stem_path": scored.get("voice_stem_path"),
            "stem_paths": scored.get("stem_paths") or {},
            "standalone_lane": True,
            "engine": "arrangement_pcm.v1",
        }
