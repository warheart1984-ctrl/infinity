"""Tests for the dependency-free local Whisper HTTP primary backend."""

from __future__ import annotations

import json

import pytest

from src.speech import SpeechToText


class _Response:
    def __init__(self, payload: dict, *, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.content = json.dumps(payload).encode("utf-8")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self._payload


def test_http_backend_transcribes_bytes_without_python_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def post(url: str, **kwargs: object) -> _Response:
        captured.update({"url": url, **kwargs})
        return _Response({"text": "governed local transcript", "language": "en"})

    monkeypatch.setattr("src.speech.requests.post", post)
    transcriber = SpeechToText(
        backend="http",
        http_endpoint="http://127.0.0.1:13312/inference",
    )

    result = transcriber.transcribe_bytes(b"RIFF-audio", suffix=".wav", language="en")

    assert result["text"] == "governed local transcript"
    assert captured["url"] == "http://127.0.0.1:13312/inference"
    assert captured["files"]["file"][1] == b"RIFF-audio"
    assert transcriber._model is None


def test_remote_http_endpoint_is_refused_without_explicit_https_consent() -> None:
    transcriber = SpeechToText(
        backend="http",
        http_endpoint="http://example.com/inference",
    )

    with pytest.raises(ValueError, match="must be loopback"):
        transcriber.transcribe_bytes(b"RIFF-audio")


def test_auto_backend_falls_back_when_http_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.speech.requests.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("offline")),
    )
    transcriber = SpeechToText(backend="auto")
    monkeypatch.setattr(
        transcriber,
        "_transcribe_model_file",
        lambda path, language: {"text": "python fallback", "segments": [], "language": language},
    )

    result = transcriber.transcribe_bytes(b"RIFF-audio", language="en")

    assert result["text"] == "python fallback"
