"""Speakers downstream lane capability adapter."""

# Mythic: Speakers Mix
# Engineering: SpeakersMixEngine
from __future__ import annotations

from typing import Any

from src.capability_module import AAISCapabilityModule

SPEAKERS_LANE_COMPONENT_ID = "jarvis.capability.speakers_mix"


class SpeakersMixCapability(AAISCapabilityModule):
    module_name = "speakers_mix"
    supported_actions = frozenset({"mix", "status"})

    def __init__(self) -> None:
        super().__init__(provider_name="aais_speakers")
        self.handlers = {"mix": self._handle_mix, "status": self._handle_status}

    def _handle_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        from src.speakers_lane_organ import build_speakers_lane_status

        return {
            "lane": build_speakers_lane_status(),
            "standalone_lane": True,
            "execution_ready": True,
            "engine": "speakers_mix.v1",
        }

    def _handle_mix(self, payload: dict[str, Any]) -> dict[str, Any]:
        from src.adaptive_music_runtime import mix_stems

        mixed = mix_stems(payload)
        return {
            "mix_plan": mixed.get("mix_plan") or {},
            "session_id": mixed.get("session_id"),
            "scene_id": mixed.get("scene_id"),
            "mix_path": mixed.get("mix_path"),
            "mix_sha256": mixed.get("mix_sha256"),
            "music_stem_path": mixed.get("music_stem_path"),
            "voice_stem_path": mixed.get("voice_stem_path"),
            "duration_sec": mixed.get("duration_sec"),
            "standalone_lane": True,
            "engine": "speakers_mix.v1",
        }
