"""Private PCM WAV normalization for the bounded SME-AUD contract."""

from __future__ import annotations

from math import gcd
import os
from pathlib import Path
import tempfile
import wave

import numpy as np
from scipy.signal import resample_poly


TARGET_SAMPLE_RATE = 16000


def _pcm_to_float(frames: bytes, *, sample_width: int) -> np.ndarray:
    if sample_width == 1:
        return (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    if sample_width == 2:
        return np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if sample_width == 3:
        raw = np.frombuffer(frames, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        values = raw[:, 0] | (raw[:, 1] << 8) | (raw[:, 2] << 16)
        values = np.where(values & 0x800000, values - 0x1000000, values)
        return values.astype(np.float32) / 8388608.0
    if sample_width == 4:
        return np.frombuffer(frames, dtype="<i4").astype(np.float32) / 2147483648.0
    raise ValueError("SME WAV normalization supports 8, 16, 24, or 32-bit PCM")


def normalize_wav_for_sme(source: Path, *, temporary_root: Path) -> tuple[Path, dict]:
    """Return a private PCM16 mono 16 kHz WAV and its transformation record."""
    source = source.resolve()
    with wave.open(str(source), "rb") as stream:
        if stream.getcomptype() != "NONE":
            raise ValueError("SME WAV normalization requires uncompressed PCM")
        channels = stream.getnchannels()
        sample_width = stream.getsampwidth()
        sample_rate = stream.getframerate()
        frames = stream.readframes(stream.getnframes())

    original = {
        "channels": channels,
        "sampleRate": sample_rate,
        "bitsPerSample": sample_width * 8,
    }
    if channels == 1 and sample_width == 2 and sample_rate == TARGET_SAMPLE_RATE:
        return source, {"applied": False, "original": original, "target": original}

    samples = _pcm_to_float(frames, sample_width=sample_width)
    if channels < 1 or samples.size % channels:
        raise ValueError("SME WAV channel data is malformed")
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    if sample_rate != TARGET_SAMPLE_RATE:
        common = gcd(sample_rate, TARGET_SAMPLE_RATE)
        samples = resample_poly(
            samples,
            TARGET_SAMPLE_RATE // common,
            sample_rate // common,
        )
    pcm16 = np.clip(samples, -1.0, 1.0 - (1.0 / 32768.0))
    pcm16 = np.rint(pcm16 * 32768.0).astype("<i2")

    temporary_root.mkdir(parents=True, exist_ok=True)
    os.chmod(temporary_root, 0o700)
    with tempfile.NamedTemporaryFile(
        suffix=".wav",
        prefix="sme-normalized-",
        dir=temporary_root,
        delete=False,
    ) as temporary:
        normalized = Path(temporary.name)
    try:
        with wave.open(str(normalized), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(TARGET_SAMPLE_RATE)
            stream.writeframes(pcm16.tobytes())
        os.chmod(normalized, 0o600)
    except Exception:
        normalized.unlink(missing_ok=True)
        raise

    return normalized, {
        "applied": True,
        "original": original,
        "target": {
            "channels": 1,
            "sampleRate": TARGET_SAMPLE_RATE,
            "bitsPerSample": 16,
        },
    }
