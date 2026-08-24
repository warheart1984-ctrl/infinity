"""Security and resource-bound tests for transcription transports."""

from __future__ import annotations

from io import BytesIO
import wave

import pytest

from src.transcription_policy import (
    AudioValidationError,
    AudioUploadTooLarge,
    TranscriptionAccessDenied,
    TranscriptionRateLimited,
    build_transcription_error_receipt,
    enforce_transcription_rate_limit,
    read_audio_bounded,
    reset_transcription_rate_limiter,
    require_transcription_access,
    validate_pcm16_wav,
)
from tests.transcription_fixtures import pcm16_wav_bytes


@pytest.fixture(autouse=True)
def _reset_route_limiter() -> None:
    reset_transcription_rate_limiter()


def test_loopback_is_allowed_when_token_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APP_BEARER_TOKEN", raising=False)

    require_transcription_access(
        authorization=None,
        client_host="127.0.0.1",
    )


def test_forwarded_non_loopback_is_not_treated_as_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APP_BEARER_TOKEN", raising=False)

    with pytest.raises(TranscriptionAccessDenied) as denied:
        require_transcription_access(
            authorization=None,
            client_host="127.0.0.1",
            forwarded_for="192.0.2.20",
        )

    assert denied.value.status_code == 403


def test_remote_client_cannot_spoof_loopback_forwarding_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APP_BEARER_TOKEN", raising=False)

    with pytest.raises(TranscriptionAccessDenied) as denied:
        require_transcription_access(
            authorization=None,
            client_host="192.0.2.20",
            forwarded_for="127.0.0.1",
        )

    assert denied.value.status_code == 403


def test_configured_token_is_required_even_on_loopback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_BEARER_TOKEN", "secret")

    with pytest.raises(TranscriptionAccessDenied) as denied:
        require_transcription_access(
            authorization="Bearer wrong",
            client_host="127.0.0.1",
        )

    assert denied.value.status_code == 401


def test_synchronous_reader_stops_at_limit() -> None:
    with pytest.raises(AudioUploadTooLarge):
        read_audio_bounded(BytesIO(b"0" * 1025), limit=1024)


def test_rate_limit_is_keyed_per_caller(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JARVIS_TRANSCRIPTION_RATE_LIMIT_REQUESTS", "1")
    monkeypatch.setenv("JARVIS_TRANSCRIPTION_RATE_LIMIT_WINDOW_SECONDS", "60")
    enforce_transcription_rate_limit(authorization=None, client_host="127.0.0.1")
    with pytest.raises(TranscriptionRateLimited):
        enforce_transcription_rate_limit(authorization=None, client_host="127.0.0.1")
    enforce_transcription_rate_limit(authorization=None, client_host="127.0.0.2")


def test_pcm16_wav_validation_reports_metadata() -> None:
    metadata = validate_pcm16_wav(
        pcm16_wav_bytes(),
        content_type="audio/wav; codecs=1",
        filename="input.wav",
    )
    assert metadata["sample_width_bytes"] == 2
    assert metadata["compression"] == "NONE"


def test_validation_receipt_excludes_audio_content() -> None:
    audio_bytes = b"not-wave"
    with pytest.raises(AudioValidationError) as denied:
        validate_pcm16_wav(
            audio_bytes,
            content_type="audio/wav",
            filename="input.wav",
        )
    receipt = build_transcription_error_receipt(
        denied.value,
        filename="input.wav",
        content_type="audio/wav",
        audio_bytes=audio_bytes,
    )
    assert receipt["source"]["byteLength"] == len(audio_bytes)
    assert "audio" not in receipt["source"]


def test_non_pcm16_wav_is_rejected_as_unsupported_media() -> None:
    stream = BytesIO()
    with wave.open(stream, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(1)
        wav_file.setframerate(16_000)
        wav_file.writeframes(b"\x80" * 160)

    with pytest.raises(AudioValidationError) as denied:
        validate_pcm16_wav(
            stream.getvalue(),
            content_type="audio/wav",
            filename="input.wav",
        )

    assert denied.value.status_code == 415
    assert denied.value.code == "unsupported_audio_format"
