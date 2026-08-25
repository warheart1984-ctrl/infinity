"""Intent classification for the Constitutional Task Bus.

# Mythic: Intent Parser
# Engineering: TaskBusIntentParser
"""

from __future__ import annotations

import re
from typing import Any


_TASK_PATTERNS = (
    r"\bplan\b",
    r"\btodo\b",
    r"\btasks?\b",
    r"\bcalendar\b",
    r"\bschedule\b",
    r"\bremind",
    r"\bmicrosoft\b",
    r"\boutlook\b",
    r"\bemail\b",
    r"\bgmail\b",
)
_TOOL_PATTERNS = (
    r"\bcode\b",
    r"\bskill\b",
    r"\btool\b",
    r"\bscript\b",
    r"\bimplement\b",
    r"\bchatgpt\b",
    r"\bopenai\b",
    r"\bbuild\b",
)
_ANALYSIS_PATTERNS = (
    r"\bwrite\b",
    r"\banalyze\b",
    r"\banalysis\b",
    r"\bstructure\b",
    r"\bcritique\b",
    r"\bsummar",
    r"\bclaude\b",
    r"\banthropic\b",
    r"\brewrite\b",
    r"\bdraft\b",
)
_PICTURE_PATTERNS = (
    r"\bpicture\b",
    r"\bimage\b",
    r"\bdraw\b",
    r"\billustrat",
    r"\bmandala\b",
    r"\bstoryboard\b",
    r"\brender\b",
    r"\bvisual\b",
    r"\bgive me pictures?\b",
)
_WORKFLOW_PATTERN = r"\bworkflow\b"


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pat, text, re.IGNORECASE) for pat in patterns)


class TaskBusIntentParser:
    """Classify operator text into task | skill | workflow | picture | mixed."""

    def classify(self, text: str, *, hints: dict[str, Any] | None = None) -> dict[str, Any]:
        raw = " ".join(str(text or "").split()).strip()
        hints = dict(hints or {})
        forced_lanes = [
            str(item).strip()
            for item in list(hints.get("lanes") or hints.get("force_lanes") or [])
            if str(item).strip()
        ]

        hits: dict[str, bool] = {
            "task": _matches_any(raw, _TASK_PATTERNS),
            "workflow": bool(re.search(_WORKFLOW_PATTERN, raw, re.IGNORECASE)),
            "tools": _matches_any(raw, _TOOL_PATTERNS),
            "analysis": _matches_any(raw, _ANALYSIS_PATTERNS),
            "picture": _matches_any(raw, _PICTURE_PATTERNS),
        }
        hits["skill"] = hits["tools"] and not hits["workflow"]

        if forced_lanes:
            lane_ids = list(dict.fromkeys(forced_lanes))
        else:
            lane_ids = []
            if hits["task"]:
                lane_ids.append("microsoft_style_tasks")
            if hits["tools"] or hits["workflow"]:
                lane_ids.append("openai_style_tools")
            if hits["analysis"]:
                lane_ids.append("anthropic_style_analysis")
            if hits["picture"]:
                lane_ids.append("picture_generation")
            if not lane_ids and raw:
                # Explicit safe default — recorded as unknown, not a silent vendor pick
                lane_ids = ["anthropic_style_analysis"]

        kinds: list[str] = []
        if hits["task"]:
            kinds.append("task")
        if hits["workflow"]:
            kinds.append("workflow")
        elif hits["tools"] or hits["skill"]:
            kinds.append("skill")
        if hits["analysis"] and "skill" not in kinds and "workflow" not in kinds:
            kinds.append("skill")
        elif hits["analysis"] and hits["task"] and "skill" not in kinds:
            kinds.append("skill")
        if hits["picture"]:
            kinds.append("picture")

        if not kinds and raw:
            kind = "unknown"
        elif len(kinds) > 1:
            kind = "mixed"
        elif kinds:
            kind = kinds[0]
        else:
            kind = "unknown"

        return {
            "kind": kind,
            "text": raw,
            "hits": hits,
            "requested_lanes": list(dict.fromkeys(lane_ids)),
            "parser": "TaskBusIntentParser",
            "forced": bool(forced_lanes),
        }
