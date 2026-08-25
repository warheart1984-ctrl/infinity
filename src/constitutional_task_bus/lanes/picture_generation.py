"""Picture generation lane — AAIS image / mandala / storyboard hooks.

# Mythic: Pictures lane
# Engineering: PictureGenerationLane
"""

from __future__ import annotations

import os
from typing import Any

from src.constitutional_task_bus.lanes.base import TaskBusLaneAdapter

AAIS_IMAGE_GENERATE_PATH = "/api/image/generate"


class PictureGenerationLane(TaskBusLaneAdapter):
    lane_id = "picture_generation"
    provider_label = "aais_image_path"
    actions = ("make_picture", "plan_storyboard", "mandala_hook")

    def describe(self) -> dict[str, Any]:
        disabled = os.getenv("AAIS_DISABLE_IMAGE_GENERATION", "false").lower() == "true"
        return {
            "lane_id": self.lane_id,
            "label": "Picture Generation Lane",
            "engineering": "PictureGenerationLane",
            "provider_label": self.provider_label,
            "actions": list(self.actions),
            "auth_status": "demo" if disabled else "ready",
            "activation_hint": (
                "Unset AAIS_DISABLE_IMAGE_GENERATION for live diffusion."
                if disabled
                else None
            ),
            "image_api": AAIS_IMAGE_GENERATE_PATH,
            "hooks": ["/image-generator", "/adaptive-music", "/workflows/templates"],
            "not_claimed": "Claude/OpenAI do not own pixels here — AAIS image path only.",
        }

    def execute(
        self,
        *,
        action: str,
        payload: dict[str, Any],
        mode: str,
        trace_id: str,
    ) -> dict[str, Any]:
        action = (action or "make_picture").strip() or "make_picture"
        prompt = str(
            payload.get("prompt") or payload.get("text") or "operator picture request"
        ).strip()
        disabled = os.getenv("AAIS_DISABLE_IMAGE_GENERATION", "false").lower() == "true"

        if action == "mandala_hook":
            return self._demo_result(
                action=action,
                payload=payload,
                trace_id=trace_id,
                summary="Mandala visual sync hook planned (no silent vendor image API).",
                extra={
                    "image_path": AAIS_IMAGE_GENERATE_PATH,
                    "deep_links": {
                        "mandala": "/adaptive-music?panel=sovereign-sound",
                        "image_generator": "/image-generator",
                    },
                },
            )

        if action == "plan_storyboard":
            frames = [
                {"frame": 1, "beat": "establish", "prompt": prompt[:120]},
                {"frame": 2, "beat": "conflict", "prompt": f"{prompt[:80]} — tension"},
                {"frame": 3, "beat": "resolve", "prompt": f"{prompt[:80]} — clarity"},
            ]
            return self._demo_result(
                action=action,
                payload=payload,
                trace_id=trace_id,
                summary="Storyboard plan via AAIS picture lane.",
                extra={"frames": frames, "image_path": AAIS_IMAGE_GENERATE_PATH},
            )

        # make_picture — always records AAIS image path; live may invoke local generator
        base = {
            "image_path": AAIS_IMAGE_GENERATE_PATH,
            "prompt": prompt,
            "deep_links": {
                "image_generator": f"/image-generator",
                "adaptive_music": "/adaptive-music",
            },
        }

        if mode == "live" and not disabled:
            try:
                # Prefer mock/local AI without requiring HTTP self-call
                from src.mock_ai import MockAI

                mock = MockAI()
                image = mock.generate_image(prompt, num_inference_steps=1)
                # Prove path was the AAIS lane, not a vendor image API
                return {
                    "ok": True,
                    "lane_id": self.lane_id,
                    "action": action,
                    "mode": "live",
                    "status": "completed",
                    "reason_code": "TASK_BUS_AAIS_IMAGE_PATH",
                    "summary": "Generated via AAIS image path (local/mock generator).",
                    "trace_id": trace_id,
                    "image_format": "png",
                    "image_bytes_hint": getattr(image, "size", None),
                    **base,
                }
            except Exception as exc:
                return {
                    "ok": False,
                    "lane_id": self.lane_id,
                    "action": action,
                    "mode": "live",
                    "status": "error",
                    "reason_code": "TASK_BUS_IMAGE_PATH_ERROR",
                    "message": str(exc),
                    "trace_id": trace_id,
                    **base,
                }

        return self._demo_result(
            action=action,
            payload=payload,
            trace_id=trace_id,
            summary=(
                "Demo make_picture: planned AAIS /api/image/generate call "
                "(no vendor image API; diffusion may be disabled)."
            ),
            extra={
                **base,
                "reason_code": "TASK_BUS_AAIS_IMAGE_PATH",
                "diffusion_disabled": disabled,
            },
        )
