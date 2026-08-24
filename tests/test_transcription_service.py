"""Tests for the framework-neutral transcription authority seam."""

from __future__ import annotations

import logging
import pytest

from src import transcription_service
from src.transcription_policy import AudioUploadTooLarge
from tests.transcription_fixtures import pcm16_wav_bytes


def test_primary_result_is_unchanged_by_shadow(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict[str, object]] = []
    audio_bytes = pcm16_wav_bytes()

    class Primary:
        def transcribe_bytes(self, audio: bytes, **kwargs: object) -> dict[str, object]:
            assert audio == audio_bytes
            assert kwargs == {"suffix": ".wav", "language": "en"}
            return {"text": "primary transcript", "language": "en", "segments": []}

    monkeypatch.setattr(transcription_service, "_load_primary_transcriber", Primary)
    monkeypatch.setattr(
        transcription_service,
        "_submit_shadow_safely",
        lambda audio, **kwargs: captured.append({"audio": audio, **kwargs}),
    )

    result = transcription_service.transcribe_audio_with_shadow(
        audio_bytes,
        filename="input.wav",
        language="en",
    )

    assert result == {
        "text": "primary transcript",
        "language": "en",
        "segments": [],
    }
    assert captured[0]["primary_status"] == "completed"
    assert captured[0]["primary_text"] == "primary transcript"
    assert "sme" not in result


def test_primary_failure_is_preserved_and_observed(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict[str, object]] = []
    audio_bytes = pcm16_wav_bytes()

    class Primary:
        def transcribe_bytes(self, audio: bytes, **kwargs: object) -> dict[str, object]:
            raise RuntimeError("primary unavailable")

    monkeypatch.setattr(transcription_service, "_load_primary_transcriber", Primary)
    monkeypatch.setattr(
        transcription_service,
        "_submit_shadow_safely",
        lambda audio, **kwargs: captured.append({"audio": audio, **kwargs}),
    )

    with pytest.raises(RuntimeError, match="primary unavailable"):
        transcription_service.transcribe_audio_with_shadow(
            audio_bytes,
            filename="input.wav",
            language=None,
        )

    assert captured[0]["primary_status"] == "failed"
    assert captured[0]["primary_text"] is None
    assert captured[0]["primary_error"] == "RuntimeError"


def test_shadow_submission_failure_cannot_change_primary_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Primary:
        def transcribe_bytes(self, audio: bytes, **kwargs: object) -> dict[str, object]:
            return {"text": "still authoritative"}

    monkeypatch.setattr(transcription_service, "_load_primary_transcriber", Primary)
    monkeypatch.setattr(
        "src.sme_transcription_shadow_lane.submit_transcription_shadow",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("shadow failed")),
    )

    result = transcription_service.transcribe_audio_with_shadow(
        pcm16_wav_bytes(),
        filename="input.wav",
        language=None,
    )

    assert result == {"text": "still authoritative"}


def test_direct_service_call_enforces_primary_audio_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JARVIS_TRANSCRIPTION_MAX_AUDIO_BYTES", "1024")
    monkeypatch.setattr(
        transcription_service,
        "_load_primary_transcriber",
        lambda: (_ for _ in ()).throw(AssertionError("must not load primary")),
    )

    with pytest.raises(AudioUploadTooLarge):
        transcription_service.transcribe_audio_with_shadow(
            b"0" * 1025,
            filename="input.wav",
            language=None,
        )


def test_shadow_submission_emits_structured_audit_record(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(
        "src.sme_transcription_shadow_lane.submit_transcription_shadow",
        lambda *args, **kwargs: {
            "status": "queued",
            "intent_id": "live-transcription-test",
        },
    )

    with caplog.at_level(logging.INFO, logger="src.transcription_service"):
        transcription_service._submit_shadow_safely(
            pcm16_wav_bytes(),
            filename="input.wav",
            language="en",
            primary_status="completed",
            primary_text="hello",
            primary_latency_ms=10.0,
        )

    assert "shadow_lane_submission" in caplog.text
    assert "live-transcription-test" in caplog.text
    assert "jarvis_primary_unchanged" in caplog.text
