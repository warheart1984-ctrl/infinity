"""AMUL LLM runtime: Adaptive -> Modular -> Universal -> Logical end-to-end flow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .adaptive import AdaptiveDecision, decide
from .contracts import (
    MemoryContract,
    PromptContract,
    ReasoningRecord,
    ToolContract,
    UniversalMetadata,
)
from .logical import anchor_to_ledger, build_replay_record, fallback_answer, policy_check
from .modules import CoreModelModule, RegistryToolModule, ToolModule


@dataclass(slots=True)
class AmulResponse:
    """Universal response envelope returned by every generation."""

    answer: str
    decision: dict[str, Any]
    metadata: dict[str, Any]
    replay: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "decision": self.decision,
            "metadata": self.metadata,
            "replay": self.replay,
        }


class AmulLLM:
    """Facade implementing the AMUL flow for a normal LLM task.

    1. Adaptive layer classifies intent + selects mode.
    2. Modular layer runs the core model (tools when mode demands it).
    3. Universal layer wraps output in the standard schema.
    4. Logical layer validates, logs, and produces the final answer.
    """

    def __init__(
        self,
        core: CoreModelModule,
        *,
        tools: ToolModule | None = None,
        ledger_client: Any = None,
        model_version: str = "amul-0.1",
    ):
        self.core = core
        self.tools = tools
        self.ledger_client = ledger_client
        self.model_version = model_version
        self._reasoning_depth_by_mode = {
            "chat_mode": 1,
            "tool_mode": 2,
            "creative_mode": 2,
            "reasoning_mode": 3,
        }

    # -- universal APIs --------------------------------------------------

    def classify(self, text: str) -> dict[str, Any]:
        decision = decide(text, tools_available=bool(self.tools))
        return decision.to_dict()

    def generate(
        self,
        prompt: PromptContract | str,
        *,
        context: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        record: bool = True,
    ) -> AmulResponse:
        if isinstance(prompt, str):
            prompt = PromptContract(user=prompt, context=context)
        query = prompt.user

        decision: AdaptiveDecision = decide(
            f"{query} {context}".strip(),
            tools_available=bool(self.tools),
            temperature=temperature,
            max_tokens=max_tokens,
        )
        steps = [
            f"parsed intent={decision.intent}",
            f"selected mode={decision.mode}",
        ]

        messages = prompt.to_messages()
        if decision.mode == "tool_mode" and self.tools is not None:
            answer, steps = self._run_tool_lane(query, messages, decision, steps)
        else:
            raw = self.core.generate(messages, decision.generation_config)
            steps.append("generated candidate answer")
            answer = raw

        flags = policy_check(answer)
        if flags:
            steps.append(f"policy flags={flags}")
            answer = fallback_answer(flags)
        steps.append("policy check passed" if not flags else "fallback issued")

        confidence = self._confidence(decision, flags)
        reasoning = ReasoningRecord(
            input=query, mode=decision.mode, steps=steps, confidence=confidence
        )
        tokens_used = max(1, (len(query) + len(answer)) // 4)
        replay = build_replay_record(query, answer, tokens_used, flags, reasoning)

        if record and self.ledger_client is not None:
            anchor_to_ledger(replay, client=self.ledger_client)
            steps.append("replay anchored to continuity ledger")

        metadata = UniversalMetadata(
            model_version=self.model_version,
            confidence=confidence,
            reasoning_depth=self._reasoning_depth_by_mode.get(decision.mode, 1),
        ).to_dict()

        return AmulResponse(
            answer=answer,
            decision=decision.to_dict(),
            metadata=metadata,
            replay=replay.to_dict(),
        )

    def remember(self, key: str, value: str) -> dict[str, Any] | None:
        """Write through the universal memory contract to the Continuity Ledger."""
        if self.ledger_client is None:
            return None
        body = MemoryContract(key=key, value=value).to_ledger_body()
        return self.ledger_client.create_memory(body)

    def tools_call(self, name: str, args: dict[str, Any]) -> Any:
        if self.tools is None:
            raise RuntimeError("no tool module installed")
        errors = self.tools.validate(name, args) if hasattr(self.tools, "validate") else []
        if errors:
            raise ValueError(f"invalid tool args: {errors}")
        return self.tools.call(name, args)

    # -- internals ---------------------------------------------------------

    def _run_tool_lane(
        self,
        query: str,
        messages: list[dict[str, str]],
        decision: AdaptiveDecision,
        steps: list[str],
    ) -> tuple[str, list[str]]:
        assert self.tools is not None
        catalog = self.tools.available()
        tool_hint = "\n".join(
            f"- {name}: {spec['schema']}" for name, spec in catalog.items()
        )
        tool_messages = messages[:-1] + [
            {
                "role": "system",
                "content": (
                    "Available tools:\n"
                    f"{tool_hint}\n"
                    "If a tool is needed, reply with JSON only: "
                    '{"tool": "<name>", "args": {...}}'
                ),
            },
            messages[-1],
        ]
        raw = self.core.generate(tool_messages, decision.generation_config)
        parsed = _parse_tool_call(raw)
        if parsed is None:
            steps.append("no tool selected; answered directly")
            return raw, steps
        name, args = parsed
        errors = self.tools.validate(name, args) if hasattr(self.tools, "validate") else []
        if errors:
            steps.append(f"tool args rejected={errors}")
            return fallback_answer(["invalid_tool_args"]), steps
        result = self.tools.call(name, args)
        steps.append(f"executed tool={name}")
        final_messages = tool_messages + [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": f"Tool result:\n{result}\nAnswer the user now."},
        ]
        return self.core.generate(final_messages, decision.generation_config), steps

    def _confidence(self, decision: AdaptiveDecision, flags: list[str]) -> float:
        base = {
            "chat_mode": 0.75,
            "tool_mode": 0.8,
            "creative_mode": 0.7,
            "reasoning_mode": 0.85,
        }.get(decision.mode, 0.7)
        penalty = 0.3 * len(flags)
        if decision.intent == "safety_sensitive":
            base -= 0.15
        return max(0.05, min(0.99, base - penalty))


def _parse_tool_call(raw: str) -> tuple[str, dict[str, Any]] | None:
    stripped = raw.strip()
    if not stripped.startswith("{"):
        return None
    import json

    try:
        data = json.loads(stripped)
    except ValueError:
        return None
    if not isinstance(data, dict) or "tool" not in data:
        return None
    return str(data["tool"]), data.get("args", {}) or {}
