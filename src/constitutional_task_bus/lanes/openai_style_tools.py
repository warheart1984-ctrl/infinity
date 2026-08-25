"""OpenAI-style tools / skills / workflow subcontract lane.

# Mythic: ChatGPT skills/workflow lane
# Engineering: OpenAiStyleToolsLane
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
    path = root / "configs" / "skills" / "openai_style_skill_pack.v1.json"
    if not path.is_file():
        return {"skills": [], "pack_id": "missing"}
    return json.loads(path.read_text(encoding="utf-8"))


class OpenAiStyleToolsLane(TaskBusLaneAdapter):
    lane_id = "openai_style_tools"
    provider_label = "openai_tools_subcontract"
    actions = ("run_skill", "list_skills", "plan_workflow")

    def describe(self) -> dict[str, Any]:
        key = str(os.getenv("OPENAI_API_KEY") or "").strip()
        pack = load_skill_pack()
        return {
            "lane_id": self.lane_id,
            "label": "OpenAI-style Tools Lane",
            "engineering": "OpenAiStyleToolsLane",
            "provider_label": self.provider_label,
            "actions": list(self.actions),
            "auth_status": "ready" if key else "needs_auth",
            "activation_hint": None if key else "Set OPENAI_API_KEY for live tool calls.",
            "skill_count": len(list(pack.get("skills") or [])),
            "not_claimed": "Not a ChatGPT store clone — AAIS skill pack templates only.",
        }

    def execute(
        self,
        *,
        action: str,
        payload: dict[str, Any],
        mode: str,
        trace_id: str,
    ) -> dict[str, Any]:
        action = (action or "run_skill").strip() or "run_skill"
        pack = load_skill_pack()
        skills = list(pack.get("skills") or [])

        if action == "list_skills":
            return self._demo_result(
                action=action,
                payload=payload,
                trace_id=trace_id,
                summary=f"Listed {len(skills)} skill manifests.",
                extra={"skills": skills, "mode": mode},
            )

        skill_id = str(payload.get("skill_id") or "compose_capability_workflow").strip()
        skill = next((s for s in skills if str(s.get("skill_id")) == skill_id), None)
        if skill is None and skills:
            skill = skills[0]
            skill_id = str(skill.get("skill_id"))

        if mode == "live" and not str(os.getenv("OPENAI_API_KEY") or "").strip():
            return self._needs_auth_result(
                action=action,
                activation_hint="Set OPENAI_API_KEY for live OpenAI-style tool execution.",
                trace_id=trace_id,
            )

        if mode == "live":
            return {
                "ok": False,
                "lane_id": self.lane_id,
                "action": action,
                "mode": "live",
                "status": "deferred",
                "reason_code": "TASK_BUS_LIVE_OPENAI_TOOLS_DEFERRED",
                "message": (
                    "OPENAI_API_KEY present but live Chat Completions tool-loop is deferred. "
                    "No silent Claude/local substitute."
                ),
                "trace_id": trace_id,
                "skill_id": skill_id,
            }

        steps = list((skill or {}).get("compose") or ["capability_bridge", "workflows"])
        return self._demo_result(
            action=action,
            payload=payload,
            trace_id=trace_id,
            summary=f"Demo skill '{skill_id}' → compose {steps}.",
            extra={
                "skill": skill,
                "skill_id": skill_id,
                "compose_targets": steps,
                "capability_hints": ["adaptive_music_compose", "task_bus"],
                "deep_links": {
                    "workflows": "/workflows/templates",
                    "capability_bridge": "/jarvis",
                },
            },
        )
