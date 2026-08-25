"""AMUL LLM runtime contracts (Universal layer).

Plain-data contracts that standardize prompts, tools, memory writes, and the
metadata every AMUL generation must carry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PromptContract:
    """Universal prompt contract."""

    system: str = ""
    user: str = ""
    context: str = ""
    mode: str = "chat"

    def to_messages(self) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if self.system:
            messages.append({"role": "system", "content": self.system})
        if self.context:
            messages.append({"role": "system", "content": f"Context:\n{self.context}"})
        messages.append({"role": "user", "content": self.user})
        return messages


@dataclass(slots=True)
class ToolContract:
    """Universal tool contract: name plus JSON schema."""

    name: str
    schema: dict[str, Any]
    description: str = ""

    def validate_args(self, args: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        for required in self.schema.get("required", []):
            if required not in args:
                errors.append(f"missing required arg: {required}")
        properties = self.schema.get("properties", {})
        for key, value in args.items():
            if key not in properties:
                errors.append(f"unknown arg: {key}")
                continue
            expected = properties[key].get("type", "string")
            type_map = {"string": str, "number": (int, float), "integer": int, "boolean": bool}
            python_type = type_map.get(expected)
            if python_type is not None and not isinstance(value, python_type):
                errors.append(f"arg {key} must be {expected}")
        return errors


@dataclass(slots=True)
class MemoryContract:
    """Universal memory write, routed through the Continuity Ledger."""

    key: str
    value: str

    def to_ledger_body(
        self,
        *,
        actor: str = "amul-llm",
        session_id: str = "amul-default",
        memory_type: str = "preference",
    ) -> dict[str, Any]:
        return {
            "content": self.value[:2000],
            "source_agent": actor[:128] or "amul-llm",
            "session_id": session_id[:128] or "amul-default",
            "type": memory_type,
            "subject": self.key[:256],
            "tags": ["amul", "memory-contract"],
        }


@dataclass(slots=True)
class UniversalMetadata:
    """Metadata attached to every AMUL response envelope."""

    model_version: str = ""
    safety_level: str = "standard"
    confidence: float = 0.0
    reasoning_depth: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_version": self.model_version,
            "safety_level": self.safety_level,
            "confidence": round(self.confidence, 4),
            "reasoning_depth": self.reasoning_depth,
        }


@dataclass(slots=True)
class ReasoningRecord:
    """Logical-layer evidence & reasoning record."""

    input: str
    mode: str
    steps: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "input": self.input,
            "mode": self.mode,
            "steps": list(self.steps),
            "confidence": round(self.confidence, 4),
        }


@dataclass(slots=True)
class ReplayRecord:
    """Logical-layer replayable audit record."""

    query: str
    final_answer: str
    tokens_used: int
    policy_flags: list[str] = field(default_factory=list)
    reasoning: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "final_answer": self.final_answer,
            "tokens_used": self.tokens_used,
            "policy_flags": list(self.policy_flags),
            "reasoning": dict(self.reasoning),
        }
