"""AMUL Logical layer: policy checks, evidence records, replay, constitutional hooks."""

from __future__ import annotations

import re
from typing import Any

from src.jarvis_memoryboard_client import JarvisMemoryboardClient

from .contracts import ReasoningRecord, ReplayRecord

_DISALLOWED = (
    re.compile(r"\b(step[- ]by[- ]step )?(build|make|synthesize)\b.*\b(explosive|malware|weapon)\b", re.I),
)

_INSUFFICIENT_EVIDENCE_ANSWER = "Insufficient evidence to answer reliably."


def policy_check(answer: str) -> list[str]:
    """Return policy flags for a candidate answer (empty list = clean)."""
    flags: list[str] = []
    if not answer.strip():
        flags.append("empty_output")
    for pattern in _DISALLOWED:
        if pattern.search(answer):
            flags.append("disallowed_content")
            break
    return flags


def fallback_answer(flags: list[str]) -> str:
    if "empty_output" in flags:
        return _INSUFFICIENT_EVIDENCE_ANSWER
    return _INSUFFICIENT_EVIDENCE_ANSWER


def build_replay_record(
    query: str,
    final_answer: str,
    tokens_used: int,
    policy_flags: list[str],
    reasoning: ReasoningRecord,
) -> ReplayRecord:
    return ReplayRecord(
        query=query,
        final_answer=final_answer,
        tokens_used=tokens_used,
        policy_flags=list(policy_flags),
        reasoning=reasoning.to_dict(),
    )


def anchor_to_ledger(record: ReplayRecord, *, client: JarvisMemoryboardClient) -> dict[str, Any]:
    """Write one replay record into the Continuity Ledger (single write path).

    Constitutional logic: no decision without evidence — the reasoning record
    travels inside the payload so the ledger entry is self-evidencing.
    """
    confidence = float(record.reasoning.get("confidence", 0.5))
    body = {
        "content": json_compact(record.to_dict())[:2000],
        "source_agent": "amul-llm",
        "session_id": "amul-replay",
        "type": "decision",
        "status": "verified" if not record.policy_flags else "draft",
        "confidence": confidence,
        "subject": "amul-llm-replay",
        "tags": ["amul", "replay", f"mode:{record.reasoning.get('mode', 'unknown')}"],
    }
    return client.create_memory(body)


def json_compact(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, separators=(",", ":"), sort_keys=True)
