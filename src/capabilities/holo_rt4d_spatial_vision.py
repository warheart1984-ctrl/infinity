"""Governed HoloRT4D spatial-vision capability adapter."""

# Mythic: HoloRT4D Spatial Vision
# Engineering: HoloRt4dSpatialVisionCapability
from __future__ import annotations

from typing import Any

from src.capability_module import AAISCapabilityModule
from src.holo_runtime_4d_spatial_vision import (
    HoloRuntime4dSpatialVisionEngine,
    build_holo_rt4d_spatial_vision_status,
)
from src.Spatial_reasoning import SpatialReasoningPlug

HOLO_RT4D_SPATIAL_VISION_COMPONENT_ID = "jarvis.capability.holo_rt4d_spatial_vision"

HOLO_RT4D_INPUT_FIELDS = (
    {
        "id": "space_id",
        "label": "Space Id",
        "type": "text",
        "required": False,
        "default": "holo_rt4d_demo",
        "placeholder": "holo_rt4d_demo",
    },
    {
        "id": "observer",
        "label": "Observer",
        "type": "text",
        "required": False,
        "default": "observer",
        "placeholder": "observer node or entity",
    },
    {
        "id": "targets",
        "label": "Targets",
        "type": "text",
        "required": False,
        "default": "",
        "placeholder": "scout, beacon, north (blank = auto)",
    },
    {
        "id": "tick",
        "label": "Tick (4D)",
        "type": "text",
        "required": False,
        "default": "0",
        "placeholder": "0",
    },
    {
        "id": "seed_demo",
        "label": "Seed Demo Space",
        "type": "boolean",
        "required": False,
        "default": True,
    },
)


class HoloRt4dSpatialVisionCapability(AAISCapabilityModule):
    module_name = "holo_rt4d_spatial_vision"
    supported_actions = frozenset({"probe", "status"})

    def __init__(self, *, spatial_plug: SpatialReasoningPlug | None = None) -> None:
        super().__init__(provider_name="aais_holo_rt4d")
        self.spatial_plug = spatial_plug
        self.handlers = {"probe": self._handle_probe, "status": self._handle_status}

    def bind_spatial_plug(self, plug: SpatialReasoningPlug | None) -> None:
        """Share Jarvis SpatialReasoningPlug so probe sees operator-built spaces."""
        self.spatial_plug = plug

    def _engine(self) -> HoloRuntime4dSpatialVisionEngine:
        return HoloRuntime4dSpatialVisionEngine(plug=self.spatial_plug)

    def _handle_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        status = build_holo_rt4d_spatial_vision_status(plug=self.spatial_plug)
        return {
            "lane": status,
            "standalone_lane": True,
            "execution_ready": True,
            "engine": status["holo_rt4d_spatial_vision_version"],
        }

    def _handle_probe(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = self._engine().probe(payload)
        return {
            **result,
            "standalone_lane": True,
        }
