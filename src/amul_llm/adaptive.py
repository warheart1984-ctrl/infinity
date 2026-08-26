"""AMUL Adaptive layer: intent classification, mode selection, constraint shaping."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_INTENT_MARKERS: dict[str, tuple[re.Pattern[str], ...]] = {
    "coding": (
        re.compile(r"\b(code|function|bug|refactor|compile|stack trace|exception)\b", re.I),
        re.compile(r"```|def |class |import |const |let |fn |=>|;\s*$", re.M),
    ),
    "math": (
        re.compile(r"\b(calculate|solve|equation|derivative|integral|probability)\b", re.I),
        re.compile(r"\d+\s*[\+\-\*/\^=]\s*\d+"),
    ),
    "reasoning": (
        re.compile(r"\b(why|how|explain|compare|analyze|derive|prove|trade-?offs?)\b", re.I),
    ),
    "creative_writing": (
        re.compile(r"\b(story|poem|song|screenplay|imagine|once upon)\b", re.I),
    ),
    "safety_sensitive": (
        re.compile(
            r"\b(weapon|explosive|malware|self[- ]harm|suicide|poison)\b",
            re.I,
        ),
    ),
}

_MODE_FOR_INTENT = {
    "chat": "chat_mode",
    "reasoning": "reasoning_mode",
    "coding": "reasoning_mode",
    "math": "reasoning_mode",
    "creative_writing": "creative_mode",
    "safety_sensitive": "chat_mode",
}

_GENERATION_CONFIG: dict[str, dict[str, Any]] = {
    "chat_mode": {"temperature": 0.7, "max_tokens": 1024},
    "reasoning_mode": {"temperature": 0.2, "max_tokens": 2048},
    "tool_mode": {"temperature": 0.1, "max_tokens": 512},
    "creative_mode": {"temperature": 0.9, "max_tokens": 2048},
}


@dataclass(slots=True)
class AdaptiveDecision:
    """Output of the adaptive layer, in the canonical AMUL shape."""

    intent: str
    mode: str
    generation_config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "mode": self.mode,
            "generation_config": dict(self.generation_config),
        }


def classify_intent(text: str) -> str:
    for intent in ("safety_sensitive", "coding", "math", "creative_writing"):
        if any(pattern.search(text) for pattern in _INTENT_MARKERS[intent]):
            return intent
    if any(pattern.search(text) for pattern in _INTENT_MARKERS["reasoning"]):
        return "reasoning"
    return "chat"


def select_mode(intent: str, *, tools_available: bool = False) -> str:
    if tools_available and intent in ("chat", "reasoning"):
        return "tool_mode"
    return _MODE_FOR_INTENT.get(intent, "chat_mode")


def build_generation_config(mode: str, **overrides: Any) -> dict[str, Any]:
    config = dict(_GENERATION_CONFIG.get(mode, _GENERATION_CONFIG["chat_mode"]))
    if mode == "chat_mode":
        config["safety_envelope"] = True
    if overrides:
        config.update({k: v for k, v in overrides.items() if v is not None})
    return config


def decide(text: str, *, tools_available: bool = False, **overrides: Any) -> AdaptiveDecision:
    """Classify intent, select mode, and shape constraints for one input."""
    intent = classify_intent(text)
    mode = select_mode(intent, tools_available=tools_available)
    return AdaptiveDecision(
        intent=intent,
        mode=mode,
        generation_config=build_generation_config(mode, **overrides),
    )
