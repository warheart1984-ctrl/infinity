"""Contract tests for the retained Flask transcription compatibility adapter."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from src import transcription_service
from src.transcription_policy import reset_transcription_rate_limiter
from tests.transcription_fixtures import pcm16_wav_bytes


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _reset_route_limiter() -> None:
    reset_transcription_rate_limiter()


def _upload(audio_bytes: bytes | None = None, *, content_type: str = "audio/wav"):
    payload = pcm16_wav_bytes() if audio_bytes is None else audio_bytes
    return SimpleNamespace(
        filename="input.wav",
        content_type=content_type,
        mimetype=content_type,
        read=lambda size: payload,
    )


def _request(*, files: dict, form: dict | None = None, remote_addr: str = "127.0.0.1"):
    return SimpleNamespace(
        files=files,
        form=form or {},
        headers={},
        remote_addr=remote_addr,
    )


def _load_route(request: object):
    tree = ast.parse((ROOT / "src" / "api.py").read_text(encoding="utf-8"))
    route = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "transcribe_audio"
    )
    route.decorator_list = []
    isolated = ast.fix_missing_locations(ast.Module(body=[route], type_ignores=[]))
    scope = {
        "request": request,
        "jsonify": lambda value: value,
        "logger": SimpleNamespace(
            error=lambda message: None,
            warning=lambda *args, **kwargs: None,
        ),
    }
    exec(compile(isolated, str(ROOT / "src" / "api.py"), "exec"), scope)
    return scope["transcribe_audio"]


def test_flask_adapter_preserves_success_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def transcribe(audio: bytes, **kwargs: object) -> dict[str, object]:
        captured.update({"audio": audio, **kwargs})
        return {"text": "primary transcript", "language": "en", "segments": []}

    monkeypatch.setattr(transcription_service, "transcribe_audio_with_shadow", transcribe)
    request = _request(
        files={"audio": _upload()},
        form={"language": "en"},
    )

    response = _load_route(request)()

    assert response == {"text": "primary transcript", "language": "en", "segments": []}
    assert captured == {
        "audio": pcm16_wav_bytes(),
        "filename": "input.wav",
        "language": "en",
        "content_type": "audio/wav",
    }


def test_flask_adapter_preserves_missing_audio_contract() -> None:
    response = _load_route(_request(files={}))()

    assert response == ({"error": "Audio file is required"}, 400)


def test_flask_adapter_preserves_primary_failure_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        transcription_service,
        "transcribe_audio_with_shadow",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("primary unavailable")),
    )
    request = _request(
        files={"audio": _upload()},
    )

    response = _load_route(request)()

    assert response == ({"error": "primary unavailable"}, 500)


def test_flask_adapter_blocks_non_loopback_without_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APP_BEARER_TOKEN", raising=False)
    response = _load_route(_request(files={}, remote_addr="192.0.2.10"))()

    assert response == (
        {"error": "APP_BEARER_TOKEN is required for non-loopback transcription"},
        403,
    )


def test_flask_adapter_rejects_oversize_upload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JARVIS_TRANSCRIPTION_MAX_AUDIO_BYTES", "1024")
    request = _request(
        files={
            "audio": SimpleNamespace(
                filename="input.wav",
                content_type="audio/wav",
                mimetype="audio/wav",
                read=lambda size: b"0" * size,
            )
        }
    )

    response = _load_route(request)()

    assert response[1] == 413
    assert response[0]["max_audio_bytes"] == 1024


def test_flask_adapter_rejects_malformed_audio_with_receipt() -> None:
    response = _load_route(_request(files={"audio": _upload(b"broken")}))()

    assert response[1] == 422
    assert response[0]["receipt"]["error"]["code"] == "malformed_pcm16_wav"


def test_flask_adapter_rejects_non_wav_content_type_with_receipt() -> None:
    response = _load_route(
        _request(files={"audio": _upload(content_type="audio/mpeg")})
    )()

    assert response[1] == 415
    assert response[0]["receipt"]["error"]["code"] == "unsupported_audio_content_type"
