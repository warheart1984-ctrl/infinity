"""Small deterministic audio fixtures shared by transcription contract tests."""

from __future__ import annotations

from io import BytesIO
import wave


def pcm16_wav_bytes(*, frames: int = 160, sample_rate: int = 16_000) -> bytes:
    stream = BytesIO()
    with wave.open(stream, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frames)
    return stream.getvalue()
