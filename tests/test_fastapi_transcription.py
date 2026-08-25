"""Contract tests for the native FastAPI transcription adapter."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app import transcription
from src.transcription_policy import reset_transcription_rate_limiter
from tests.transcription_fixtures import pcm16_wav_bytes


TOKEN = "transcription-test-token"
AUTH_HEADERS = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture(autouse=True)
def _reset_route_limiter() -> None:
    reset_transcription_rate_limiter()


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(transcription.router)
    return TestClient(app)


def test_native_route_preserves_success_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BEARER_TOKEN", TOKEN)
    captured: dict[str, object] = {}

    def transcribe(audio: bytes, **kwargs: object) -> dict[str, object]:
        captured.update({"audio": audio, **kwargs})
        return {"text": "primary transcript", "language": "en", "segments": []}

    monkeypatch.setattr(transcription, "transcribe_audio_with_shadow", transcribe)

    audio_bytes = pcm16_wav_bytes()
    with _client() as client:
        response = client.post(
            "/api/audio/transcribe",
            files={"audio": ("input.wav", audio_bytes, "audio/wav")},
            data={"language": "en"},
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 200
    assert response.json() == {
        "text": "primary transcript",
        "language": "en",
        "segments": [],
    }
    assert captured == {
        "audio": audio_bytes,
        "filename": "input.wav",
        "language": "en",
        "content_type": "audio/wav",
    }


def test_native_route_preserves_missing_audio_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BEARER_TOKEN", TOKEN)
    with _client() as client:
        response = client.post("/api/audio/transcribe", headers=AUTH_HEADERS)

    assert response.status_code == 400
    assert response.json() == {"error": "Audio file is required"}


def test_native_route_preserves_primary_failure_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_BEARER_TOKEN", TOKEN)
    def fail(audio: bytes, **kwargs: object) -> dict[str, object]:
        raise RuntimeError("primary unavailable")

    monkeypatch.setattr(transcription, "transcribe_audio_with_shadow", fail)

    with _client() as client:
        response = client.post(
            "/api/audio/transcribe",
            files={"audio": ("input.wav", pcm16_wav_bytes(), "audio/wav")},
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 500
    assert response.json() == {"error": "primary unavailable"}


def test_native_route_requires_configured_bearer_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_BEARER_TOKEN", TOKEN)
    with _client() as client:
        response = client.post(
            "/api/audio/transcribe",
            files={"audio": ("input.wav", pcm16_wav_bytes(), "audio/wav")},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_native_route_rejects_oversize_upload_before_primary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_BEARER_TOKEN", TOKEN)
    monkeypatch.setenv("JARVIS_TRANSCRIPTION_MAX_AUDIO_BYTES", "1024")
    monkeypatch.setattr(
        transcription,
        "transcribe_audio_with_shadow",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not run")),
    )

    with _client() as client:
        response = client.post(
            "/api/audio/transcribe",
            files={"audio": ("input.wav", b"0" * 1025, "audio/wav")},
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 413
    assert response.json()["max_audio_bytes"] == 1024


def test_native_route_rejects_non_wav_content_type_with_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_BEARER_TOKEN", TOKEN)
    with _client() as client:
        response = client.post(
            "/api/audio/transcribe",
            files={"audio": ("input.wav", pcm16_wav_bytes(), "audio/mpeg")},
            headers=AUTH_HEADERS,
        )

    payload = response.json()
    assert response.status_code == 415
    assert payload["receipt"]["error"]["code"] == "unsupported_audio_content_type"
    assert payload["receipt"]["authority"]["smeInvoked"] is False


def test_native_route_rejects_malformed_wav_with_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_BEARER_TOKEN", TOKEN)
    with _client() as client:
        response = client.post(
            "/api/audio/transcribe",
            files={"audio": ("input.wav", b"not-a-wave", "audio/wav")},
            headers=AUTH_HEADERS,
        )

    payload = response.json()
    assert response.status_code == 422
    assert payload["receipt"]["error"]["code"] == "malformed_pcm16_wav"
    assert payload["receipt"]["source"]["retained"] is False


def test_native_route_rate_limit_is_scoped_to_transcription(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_BEARER_TOKEN", TOKEN)
    monkeypatch.setenv("JARVIS_TRANSCRIPTION_RATE_LIMIT_REQUESTS", "1")
    monkeypatch.setenv("JARVIS_TRANSCRIPTION_RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setattr(
        transcription,
        "transcribe_audio_with_shadow",
        lambda *args, **kwargs: {"text": "ok"},
    )
    upload = {"audio": ("input.wav", pcm16_wav_bytes(), "audio/wav")}
    with _client() as client:
        first = client.post("/api/audio/transcribe", files=upload, headers=AUTH_HEADERS)
        second = client.post("/api/audio/transcribe", files=upload, headers=AUTH_HEADERS)

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["retry-after"] == "60"
