"""Tests for the real-request SME-AUD shadow lane."""

from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import threading
import wave

from src.sme_transcription_shadow_lane import SmeTranscriptionShadowLane


def _wav_bytes(seconds: float = 1.0) -> bytes:
    buffer = BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * int(16000 * seconds))
    return buffer.getvalue()


def _receipt(path: Path, text: str = "Jarvis keeps continuity.") -> dict[str, object]:
    return {
        "status": "verified",
        "latency_ms": 125.0,
        "transcription": {"text": text},
        "provider": {
            "kind": "local",
            "model": "test-whisper",
            "outboundData": False,
        },
        "evidence_completeness": {"required": 7, "present": 7, "complete": True},
        "replay_handle": "a" * 64,
        "receipt_path": str(path),
        "continuity_ledger": {"status": "not_requested"},
    }


def test_disabled_lane_does_not_start_adapter(tmp_path: Path) -> None:
    lane = SmeTranscriptionShadowLane(
        root=tmp_path,
        runtime_root=tmp_path / "runtime",
        enabled=False,
        adapter_factory=lambda: (_ for _ in ()).throw(AssertionError("must not run")),
    )

    result = lane.submit(
        _wav_bytes(),
        filename="input.wav",
        language="en",
        primary_status="completed",
        primary_text="hello",
        primary_latency_ms=1.0,
    )

    assert result == {"status": "disabled"}
    assert not lane.metrics_path.exists()


def test_enabled_lane_records_private_non_blocking_observation(tmp_path: Path) -> None:
    observed_paths: list[Path] = []

    class Adapter:
        def transcribe_audio(self, audio_path: Path, **_: object) -> dict[str, object]:
            source = Path(audio_path)
            assert source.is_file()
            observed_paths.append(source)
            return _receipt(tmp_path / "receipt.json")

    lane = SmeTranscriptionShadowLane(
        root=tmp_path,
        runtime_root=tmp_path / "runtime",
        enabled=True,
        min_observations=2,
        adapter_factory=Adapter,
    )
    primary_text = "Jarvis keeps continuity."
    result = lane.submit(
        _wav_bytes(),
        filename="input.wav",
        language="en",
        primary_status="completed",
        primary_text=primary_text,
        primary_latency_ms=80.0,
    )

    assert result["status"] == "queued"
    assert lane.flush()
    metric_text = lane.metrics_path.read_text(encoding="utf-8")
    observation = json.loads(metric_text)
    promotion = json.loads(lane.promotion_path.read_text(encoding="utf-8"))
    assert primary_text not in metric_text
    assert observation["comparison"]["wordAgreement"] == 1.0
    assert observation["privacy"]["transcriptContentStoredInMetrics"] is False
    assert observation["source"]["audioRetained"] is False
    assert observation["authority"]["primaryJarvisResponseChanged"] is False
    assert observation["authority"]["divineCoreDemoted"] is False
    assert observed_paths and not observed_paths[0].exists()
    assert not list(lane.inbox_root.glob("*.wav"))
    assert promotion["promotion_eligible"] is False
    assert promotion["automatic_promotion"] is False
    assert "minimumObservations" in promotion["hold_reasons"]
    assert "groundTruthAccuracyBenchmark" in promotion["hold_reasons"]


def test_lane_rejects_unbounded_or_unsupported_audio(tmp_path: Path) -> None:
    lane = SmeTranscriptionShadowLane(
        root=tmp_path,
        runtime_root=tmp_path / "runtime",
        enabled=True,
        max_audio_bytes=100,
    )

    assert lane.submit(
        b"tiny",
        filename="input.wav",
        language="en",
        primary_status="failed",
        primary_text=None,
        primary_latency_ms=None,
    )["reason"] == "audio_too_small"
    assert lane.submit(
        _wav_bytes(),
        filename="input.wav",
        language="en",
        primary_status="failed",
        primary_text=None,
        primary_latency_ms=None,
    )["reason"] == "audio_too_large"
    assert lane.submit(
        b"0" * 80,
        filename="input.mp3",
        language="en",
        primary_status="failed",
        primary_text=None,
        primary_latency_ms=None,
    )["reason"] == "shadow_accepts_wav_only"


def test_lane_queue_is_bounded(tmp_path: Path) -> None:
    started = threading.Event()
    release = threading.Event()

    class BlockingAdapter:
        def transcribe_audio(self, audio_path: Path, **_: object) -> dict[str, object]:
            started.set()
            assert release.wait(timeout=3)
            return _receipt(tmp_path / "receipt.json")

    lane = SmeTranscriptionShadowLane(
        root=tmp_path,
        runtime_root=tmp_path / "runtime",
        enabled=True,
        queue_size=1,
        adapter_factory=BlockingAdapter,
    )
    payload = dict(
        filename="input.wav",
        language="en",
        primary_status="completed",
        primary_text="Jarvis keeps continuity.",
        primary_latency_ms=80.0,
    )
    assert lane.submit(_wav_bytes(), **payload)["status"] == "queued"
    assert started.wait(timeout=2)
    assert lane.submit(_wav_bytes(), **payload)["status"] == "queued"
    assert lane.submit(_wav_bytes(), **payload)["status"] == "queue_full"
    release.set()
    assert lane.flush(timeout_seconds=5)


def test_lane_records_runner_failure_without_affecting_authority(tmp_path: Path) -> None:
    class FailingAdapter:
        def transcribe_audio(self, audio_path: Path, **_: object) -> dict[str, object]:
            raise RuntimeError("backend unavailable")

    lane = SmeTranscriptionShadowLane(
        root=tmp_path,
        runtime_root=tmp_path / "runtime",
        enabled=True,
        adapter_factory=FailingAdapter,
    )
    assert lane.submit(
        _wav_bytes(),
        filename="input.wav",
        language="en",
        primary_status="completed",
        primary_text="Jarvis keeps continuity.",
        primary_latency_ms=80.0,
    )["status"] == "queued"
    assert lane.flush()
    observation = json.loads(lane.metrics_path.read_text(encoding="utf-8"))
    assert observation["sme_shadow"]["status"] == "runner_error"
    assert "RuntimeError" in observation["sme_shadow"]["runnerError"]
    assert observation["authority"]["primaryJarvisResponseChanged"] is False
