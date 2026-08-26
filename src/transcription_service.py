"""Framework-neutral Jarvis transcription orchestration.

The primary transcriber remains authoritative. SME-AUD only receives a bounded,
non-blocking shadow observation and cannot alter the primary result.
"""

from __future__ import annotations

import logging
import json
from pathlib import Path
import time
from typing import Any, Protocol

from src.transcription_policy import ensure_audio_size, validate_pcm16_wav


logger = logging.getLogger(__name__)


class Transcriber(Protocol):
    def transcribe_bytes(
        self,
        audio_bytes: bytes,
        *,
        suffix: str,
        language: str | None,
    ) -> dict[str, Any]: ...


def _load_primary_transcriber() -> Transcriber:
    from src.speech import speech_to_text

    return speech_to_text


def _submit_shadow_safely(
    audio_bytes: bytes,
    *,
    filename: str,
    language: str | None,
    primary_status: str,
    primary_text: str | None,
    primary_latency_ms: float | None,
    primary_error: str | None = None,
) -> None:
    """Keep shadow failures outside the authoritative response path."""
    try:
        from src.sme_transcription_shadow_lane import submit_transcription_shadow

        receipt = submit_transcription_shadow(
            audio_bytes,
            filename=filename,
            language=language,
            primary_status=primary_status,
            primary_text=primary_text,
            primary_latency_ms=primary_latency_ms,
            primary_error=primary_error,
        )
        if receipt.get("status") != "disabled":
            logger.warning(
                "transcription_audit %s",
                json.dumps(
                    {
                        "event": "shadow_lane_submission",
                        "status": receipt.get("status", "unknown"),
                        "intentId": receipt.get("intent_id"),
                        "primaryStatus": primary_status,
                        "authority": "jarvis_primary_unchanged",
                    },
                    sort_keys=True,
                ),
            )
    except Exception as exc:
        logger.warning("SME transcription shadow submission failed: %s", type(exc).__name__)


def transcribe_audio_with_shadow(
    audio_bytes: bytes,
    *,
    filename: str,
    language: str | None,
    content_type: str = "audio/wav",
) -> dict[str, Any]:
    """Run the Jarvis primary transcriber and asynchronously observe with SME."""
    ensure_audio_size(audio_bytes)
    normalized_filename = filename or "audio.wav"
    validate_pcm16_wav(
        audio_bytes,
        content_type=content_type,
        filename=normalized_filename,
    )
    suffix = Path(normalized_filename).suffix or ".wav"
    primary_started = time.perf_counter()

    try:
        result = _load_primary_transcriber().transcribe_bytes(
            audio_bytes,
            suffix=suffix,
            language=language,
        )
    except Exception as exc:
        primary_latency_ms = round((time.perf_counter() - primary_started) * 1000, 3)
        _submit_shadow_safely(
            audio_bytes,
            filename=normalized_filename,
            language=language,
            primary_status="failed",
            primary_text=None,
            primary_latency_ms=primary_latency_ms,
            primary_error=type(exc).__name__,
        )
        raise

    primary_latency_ms = round((time.perf_counter() - primary_started) * 1000, 3)
    _submit_shadow_safely(
        audio_bytes,
        filename=normalized_filename,
        language=language,
        primary_status="completed",
        primary_text=str(result.get("text") or ""),
        primary_latency_ms=primary_latency_ms,
    )
    return result
