"""Anthropic-style analysis / writing / structure subcontract lane.

# Mythic: Claude skills lane
# Engineering: AnthropicStyleAnalysisLane
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from src.constitutional_task_bus.lanes.base import TaskBusLaneAdapter


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_skill_pack(*, repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or _repo_root()
    path = root / "configs" / "skills" / "anthropic_style_skill_pack.v1.json"
    if not path.is_file():
        return {"skills": [], "pack_id": "missing"}
    return json.loads(path.read_text(encoding="utf-8"))


class AnthropicStyleAnalysisLane(TaskBusLaneAdapter):
    lane_id = "anthropic_style_analysis"
    provider_label = "anthropic_analysis_subcontract"
    actions = ("analyze", "write", "structure", "run_skill")

    def describe(self) -> dict[str, Any]:
        key = str(os.getenv("ANTHROPIC_API_KEY") or "").strip()
        pack = load_skill_pack()
        return {
            "lane_id": self.lane_id,
            "label": "Anthropic-style Analysis Lane",
            "engineering": "AnthropicStyleAnalysisLane",
            "provider_label": self.provider_label,
            "actions": list(self.actions),
            "auth_status": "ready" if key else "needs_auth",
            "activation_hint": None if key else "Set ANTHROPIC_API_KEY for live Claude analysis.",
            "skill_count": len(list(pack.get("skills") or [])),
            "not_claimed": "Not Computer Use / full Claude skill store — analysis + make_picture route only.",
        }

    def execute(
        self,
        *,
        action: str,
        payload: dict[str, Any],
        mode: str,
        trace_id: str,
    ) -> dict[str, Any]:
        action = (action or "analyze").strip() or "analyze"
        text = str(payload.get("text") or payload.get("prompt") or "").strip()
        pack = load_skill_pack()
        skills = list(pack.get("skills") or [])

        skill_id = str(payload.get("skill_id") or "").strip()
        if action == "run_skill" and skill_id == "make_picture":
            # Claude does not ship pixels — explicit handoff to picture lane path
            return {
                "ok": True,
                "lane_id": self.lane_id,
                "action": action,
                "mode": mode if mode == "demo" else "demo",
                "status": "handoff",
                "reason_code": "TASK_BUS_PICTURE_HANDOFF",
                "message": (
                    "make_picture skill routes to AAIS PictureGenerationLane /api/image/generate — "
                    "not a silent Anthropic image API."
                ),
                "handoff_lane": "picture_generation",
                "image_path": "/api/image/generate",
                "trace_id": trace_id,
                "decision_event": {
                    "event": "explicit_lane_handoff",
                    "from": self.lane_id,
                    "to": "picture_generation",
                    "reason_code": "TASK_BUS_PICTURE_HANDOFF",
                },
            }

        if mode == "live" and not str(os.getenv("ANTHROPIC_API_KEY") or "").strip():
            return self._needs_auth_result(
                action=action,
                activation_hint="Set ANTHROPIC_API_KEY for live Claude analysis.",
                trace_id=trace_id,
            )

        if mode == "live":
            return {
                "ok": False,
                "lane_id": self.lane_id,
                "action": action,
                "mode": "live",
                "status": "deferred",
                "reason_code": "TASK_BUS_LIVE_ANTHROPIC_DEFERRED",
                "message": (
                    "ANTHROPIC_API_KEY present but live Messages API call is deferred. "
                    "No silent OpenAI substitute."
                ),
                "trace_id": trace_id,
            }

        outline = [
            "Restate operator ask under AAIS law",
            "Separate facts vs recommendations",
            "Propose next governed action with reason codes",
        ]
        return self._demo_result(
            action=action,
            payload=payload,
            trace_id=trace_id,
            summary=f"Demo {action}: structured writing/analysis scaffold.",
            extra={
                "structure": outline,
                "draft": (
                    f"[AAIS analysis draft — demo]\nAsk: {text[:400]}\n\n"
                    "1) Intent held under one trace.\n"
                    "2) Lanes are subcontracts, not free agents.\n"
                    "3) Next: confirm or dispatch picture/tools lanes explicitly."
                ),
                "skills_available": [s.get("skill_id") for s in skills],
            },
        )
