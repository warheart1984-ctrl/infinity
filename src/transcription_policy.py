"""Shared security and resource bounds for transcription transports."""

from __future__ import annotations

import hmac
import hashlib
import ipaddress
from io import BytesIO
import math
import os
from pathlib import Path
import threading
import time
from datetime import UTC, datetime
from uuid import uuid4
import wave


DEFAULT_MAX_AUDIO_BYTES = 10 * 1024 * 1024
READ_CHUNK_BYTES = 1024 * 1024
DEFAULT_RATE_LIMIT_REQUESTS = 12
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60.0
PCM16_WAV_CONTENT_TYPES = frozenset(
    {"audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave"}
)

_RATE_LIMIT_LOCK = threading.Lock()
_RATE_LIMIT_BUCKETS: dict[str, list[float]] = {}


class AudioUploadTooLarge(ValueError):
    def __init__(self, max_audio_bytes: int) -> None:
        self.max_audio_bytes = max_audio_bytes
        super().__init__(f"Audio file exceeds the {max_audio_bytes}-byte limit")


class TranscriptionAccessDenied(PermissionError):
    def __init__(self, message: str, *, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(message)


class TranscriptionRateLimited(PermissionError):
    def __init__(self, retry_after_seconds: int) -> None:
        self.status_code = 429
        self.retry_after_seconds = max(1, retry_after_seconds)
        super().__init__("Transcription request rate limit exceeded")


class AudioValidationError(ValueError):
    def __init__(self, message: str, *, code: str, status_code: int) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class UnsupportedAudioMedia(AudioValidationError):
    def __init__(self, message: str, *, code: str = "unsupported_audio_format") -> None:
        super().__init__(message, code=code, status_code=415)


class MalformedAudio(AudioValidationError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="malformed_pcm16_wav", status_code=422)


def max_audio_bytes() -> int:
    raw = os.getenv("JARVIS_TRANSCRIPTION_MAX_AUDIO_BYTES", "").strip()
    if not raw:
        return DEFAULT_MAX_AUDIO_BYTES
    try:
        configured = int(raw)
    except ValueError as exc:
        raise ValueError("JARVIS_TRANSCRIPTION_MAX_AUDIO_BYTES must be an integer") from exc
    if configured < 1024:
        raise ValueError("JARVIS_TRANSCRIPTION_MAX_AUDIO_BYTES must be at least 1024")
    return configured


def ensure_audio_size(audio_bytes: bytes, *, limit: int | None = None) -> None:
    selected_limit = max_audio_bytes() if limit is None else limit
    if len(audio_bytes) > selected_limit:
        raise AudioUploadTooLarge(selected_limit)


def read_audio_bounded(stream, *, limit: int | None = None) -> bytes:
    """Read a synchronous upload without allowing unbounded primary memory use."""
    selected_limit = max_audio_bytes() if limit is None else limit
    audio_bytes = stream.read(selected_limit + 1)
    ensure_audio_size(audio_bytes, limit=selected_limit)
    return audio_bytes


def _positive_number_from_env(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def reset_transcription_rate_limiter() -> None:
    """Clear process-local route buckets. Intended for tests and safe reloads."""
    with _RATE_LIMIT_LOCK:
        _RATE_LIMIT_BUCKETS.clear()


def enforce_transcription_rate_limit(
    *,
    authorization: str | None,
    client_host: str | None,
    forwarded_for: str | None = None,
) -> None:
    """Apply a bounded, process-local limit to the transcription route only."""
    configured_request_limit = _positive_number_from_env(
        "JARVIS_TRANSCRIPTION_RATE_LIMIT_REQUESTS",
        DEFAULT_RATE_LIMIT_REQUESTS,
    )
    if not configured_request_limit.is_integer():
        raise ValueError("JARVIS_TRANSCRIPTION_RATE_LIMIT_REQUESTS must be an integer")
    request_limit = int(configured_request_limit)
    window_seconds = _positive_number_from_env(
        "JARVIS_TRANSCRIPTION_RATE_LIMIT_WINDOW_SECONDS",
        DEFAULT_RATE_LIMIT_WINDOW_SECONDS,
    )
    supplied = str(authorization or "")
    if supplied:
        identity = "bearer:" + hashlib.sha256(supplied.encode()).hexdigest()
    else:
        identity = "host:" + _client_host(client_host, forwarded_for)

    now = time.monotonic()
    cutoff = now - window_seconds
    with _RATE_LIMIT_LOCK:
        timestamps = _RATE_LIMIT_BUCKETS.setdefault(identity, [])
        timestamps[:] = [timestamp for timestamp in timestamps if timestamp > cutoff]
        if len(timestamps) >= request_limit:
            retry_after = math.ceil(max(1.0, window_seconds - (now - timestamps[0])))
            raise TranscriptionRateLimited(retry_after)
        timestamps.append(now)


def validate_wav_content_type(content_type: str | None, filename: str) -> str:
    normalized_type = str(content_type or "").split(";", 1)[0].strip().lower()
    if normalized_type not in PCM16_WAV_CONTENT_TYPES:
        raise UnsupportedAudioMedia(
            "Only PCM16 WAV uploads are accepted",
            code="unsupported_audio_content_type",
        )
    if Path(filename or "").suffix.lower() != ".wav":
        raise UnsupportedAudioMedia(
            "Only .wav filenames are accepted",
            code="unsupported_audio_filename",
        )
    return normalized_type


def validate_pcm16_wav(
    audio_bytes: bytes,
    *,
    content_type: str | None,
    filename: str,
) -> dict[str, int | str]:
    """Validate an uncompressed, non-empty, 16-bit PCM WAV container."""
    normalized_type = validate_wav_content_type(content_type, filename)
    try:
        with wave.open(BytesIO(audio_bytes), "rb") as wav_file:
            metadata: dict[str, int | str] = {
                "content_type": normalized_type,
                "channels": wav_file.getnchannels(),
                "sample_width_bytes": wav_file.getsampwidth(),
                "sample_rate_hz": wav_file.getframerate(),
                "frame_count": wav_file.getnframes(),
                "compression": wav_file.getcomptype(),
            }
    except (EOFError, ValueError, wave.Error) as exc:
        raise MalformedAudio("Upload is not a well-formed WAV container") from exc

    if metadata["compression"] != "NONE" or metadata["sample_width_bytes"] != 2:
        raise UnsupportedAudioMedia("WAV audio must be uncompressed 16-bit PCM")
    if (
        int(metadata["channels"]) <= 0
        or int(metadata["sample_rate_hz"]) <= 0
        or int(metadata["frame_count"]) <= 0
    ):
        raise MalformedAudio("PCM16 WAV must contain at least one valid audio frame")
    return metadata


def build_transcription_error_receipt(
    error: AudioValidationError,
    *,
    filename: str,
    content_type: str | None,
    audio_bytes: bytes | None = None,
) -> dict[str, object]:
    """Create a content-free refusal receipt suitable for audit storage."""
    source: dict[str, object] = {
        "filename": Path(filename or "audio.wav").name,
        "contentType": str(content_type or ""),
        "retained": False,
    }
    if audio_bytes is not None:
        source.update(
            {
                "byteLength": len(audio_bytes),
                "sha256": hashlib.sha256(audio_bytes).hexdigest(),
            }
        )
    return {
        "schema": "jarvis-transcription-error-receipt/1.0",
        "receiptId": "transcription-refusal-" + uuid4().hex,
        "createdAt": datetime.now(UTC).isoformat(),
        "status": "refused",
        "error": {
            "code": error.code,
            "message": str(error),
            "httpStatus": error.status_code,
        },
        "source": source,
        "authority": {
            "executive": "Jarvis",
            "smeInvoked": False,
        },
    }


def _client_host(client_host: str | None, forwarded_for: str | None) -> str:
    direct_host = str(client_host or "").strip()
    # Only a loopback reverse proxy is trusted to supply forwarding metadata.
    # A remote caller must not be able to spoof X-Forwarded-For: 127.0.0.1.
    if forwarded_for and _is_loopback(direct_host):
        return forwarded_for.split(",", 1)[0].strip()
    return direct_host


def _is_loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host.lower() == "localhost"


def require_transcription_access(
    *,
    authorization: str | None,
    client_host: str | None,
    forwarded_for: str | None = None,
) -> None:
    """Allow bearer-authenticated callers or direct loopback-only operation."""
    configured_token = os.getenv("APP_BEARER_TOKEN", "").strip()
    supplied = str(authorization or "")
    if configured_token:
        expected = f"Bearer {configured_token}"
        if not hmac.compare_digest(supplied, expected):
            raise TranscriptionAccessDenied("Unauthorized", status_code=401)
        return

    host = _client_host(client_host, forwarded_for)
    if _is_loopback(host):
        return
    raise TranscriptionAccessDenied(
        "APP_BEARER_TOKEN is required for non-loopback transcription",
        status_code=403,
    )
