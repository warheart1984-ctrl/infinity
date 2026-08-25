"""Governed Mandala visual sync capability adapter (plan-only)."""

# Mythic: Mandala Music Synesthesia
# Engineering: MandalaVisualSyncCapability
from __future__ import annotations

from typing import Any

from src.capability_module import AAISCapabilityModule

MANDALA_VISUAL_SYNC_COMPONENT_ID = "jarvis.capability.mandala_visual_sync"

MANDALA_VISUAL_SYNC_INPUT_FIELDS = (
    {
        "id": "mood",
        "label": "Mood",
        "type": "text",
        "required": False,
        "default": "focused",
        "placeholder": "calm | focused | intense | happy",
    },
    {
        "id": "bpm",
        "label": "BPM",
        "type": "text",
        "required": False,
        "default": "120",
        "placeholder": "70-175",
    },
    {
        "id": "energy",
        "label": "Energy",
        "type": "text",
        "required": False,
        "default": "62",
    },
    {
        "id": "tension",
        "label": "Tension",
        "type": "text",
        "required": False,
        "default": "40",
    },
    {
        "id": "mix_sha256",
        "label": "Mix SHA256",
        "type": "text",
        "required": False,
        "placeholder": "optional mix receipt hash",
    },
)


class MandalaVisualSyncCapability(AAISCapabilityModule):
    """Derive MandalaVisualAdaptationPlan from score/scene axes (no pixels)."""

    module_name = "mandala_visual_sync"
    supported_actions = frozenset({"sync", "status"})

    def __init__(self) -> None:
        super().__init__(provider_name="aais_mandala")
        self.handlers = {"sync": self._handle_sync, "status": self._handle_status}

    def _handle_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "standalone_lane": True,
            "execution_ready": True,
            "engine": "mandala_visual_adaptation.v1",
            "owns_pixels": False,
            "console_path": "/adaptive-music",
        }

    def _handle_sync(self, payload: dict[str, Any]) -> dict[str, Any]:
        from src.mandala_music_synesthesia import derive_visual_adaptation

        plan = derive_visual_adaptation(dict(payload or {}))
        return {
            **plan,
            "standalone_lane": True,
            "console_path": "/adaptive-music",
        }
