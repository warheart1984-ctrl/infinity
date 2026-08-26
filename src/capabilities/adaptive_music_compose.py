"""Governed adaptive music compose+mix capability adapter."""

# Mythic: Adaptive Score Compose
# Engineering: AdaptiveMusicComposeCapability
from __future__ import annotations

from typing import Any

from src.capability_module import AAISCapabilityModule

ADAPTIVE_MUSIC_COMPOSE_COMPONENT_ID = "jarvis.capability.adaptive_music_compose"

ADAPTIVE_MUSIC_COMPOSE_INPUT_FIELDS = (
    {
        "id": "mood",
        "label": "Mood",
        "type": "text",
        "required": False,
        "default": "focused",
        "placeholder": "calm | focused | intense | happy",
    },
    {
        "id": "energy",
        "label": "Energy",
        "type": "text",
        "required": False,
        "default": "62",
        "placeholder": "0-100",
    },
    {
        "id": "tension",
        "label": "Tension",
        "type": "text",
        "required": False,
        "default": "40",
        "placeholder": "0-100",
    },
    {
        "id": "duration_sec",
        "label": "Duration (sec)",
        "type": "text",
        "required": False,
        "default": "6",
        "placeholder": "2-12",
    },
    {
        "id": "description",
        "label": "Scene / Intent",
        "type": "textarea",
        "required": False,
        "placeholder": "Narrative pacing or operator intent",
    },
    {
        "id": "include_mandala_sync",
        "label": "Include Mandala Plan",
        "type": "boolean",
        "required": False,
        "default": True,
    },
    {
        "id": "include_audio",
        "label": "Include Audio Stems",
        "type": "boolean",
        "required": False,
        "default": True,
    },
)


def _coerce_bool(value: Any, *, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off", ""}


class AdaptiveMusicComposeCapability(AAISCapabilityModule):
    """One bridge tool: Beatbox score + Speakers mix (+ optional Mandala plan)."""

    module_name = "adaptive_music_compose"
    supported_actions = frozenset({"compose", "status"})

    def __init__(self) -> None:
        super().__init__(provider_name="aais_adaptive_music")
        self.handlers = {"compose": self._handle_compose, "status": self._handle_status}

    def _handle_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "standalone_lane": True,
            "execution_ready": True,
            "engine": "arrangement_pcm.v1",
            "console_path": "/adaptive-music",
            "lanes": ("beatbox_score", "speakers_mix", "mandala_visual_sync"),
        }

    def _handle_compose(self, payload: dict[str, Any]) -> dict[str, Any]:
        from src.adaptive_music_runtime import compose_and_mix
        from src.mandala_music_synesthesia import derive_visual_adaptation
        from src.spatial_score_couple import apply_spatial_score_couple

        body = apply_spatial_score_couple(dict(payload or {}))
        include_audio = _coerce_bool(body.get("include_audio"), default=True)
        include_mandala = _coerce_bool(body.get("include_mandala_sync"), default=True)
        result = compose_and_mix(body, include_audio=include_audio)
        if include_mandala and isinstance(result, dict):
            sync_payload = dict(body)
            sync_payload.update(
                {
                    "mood": result.get("mood") or body.get("mood"),
                    "bpm": result.get("bpm") or body.get("bpm"),
                    "duration_sec": result.get("duration_sec") or body.get("duration_sec"),
                    "cue_plan": result.get("cue_plan") or {},
                    "mix_sha256": result.get("mix_sha256") or "",
                    "session_id": result.get("session_id") or "",
                    "scene_id": result.get("scene_id") or "",
                }
            )
            result["mandala_visual_plan"] = derive_visual_adaptation(sync_payload)
        return {
            **result,
            "stems": result.get("stems") or result.get("stems_b64") or {},
            "standalone_lane": True,
            "console_path": "/adaptive-music",
            "engine": result.get("engine") or "arrangement_pcm.v1",
        }
