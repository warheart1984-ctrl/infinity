"""AMUL LLM runtime package: Adaptive, Modular, Universal, Logical layers."""

from .adaptive import AdaptiveDecision, classify_intent, decide, select_mode
from .contracts import (
    MemoryContract,
    PromptContract,
    ReasoningRecord,
    ReplayRecord,
    ToolContract,
    UniversalMetadata,
)
from .logical import anchor_to_ledger, build_replay_record, fallback_answer, policy_check
from .modules import LemonadeCoreModule, RegistryToolModule
from .runtime import AmulLLM, AmulResponse

__all__ = [
    "AdaptiveDecision",
    "AmulLLM",
    "AmulResponse",
    "LemonadeCoreModule",
    "MemoryContract",
    "PromptContract",
    "ReasoningRecord",
    "ReplayRecord",
    "RegistryToolModule",
    "ToolContract",
    "UniversalMetadata",
    "anchor_to_ledger",
    "build_replay_record",
    "classify_intent",
    "decide",
    "fallback_answer",
    "policy_check",
    "select_mode",
]
