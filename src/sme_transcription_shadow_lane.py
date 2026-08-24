"""Bounded asynchronous SME-AUD shadow lane for real Jarvis requests."""

# Mythic: Jarvis hears through a governed shadow sense
# Engineering: SmeTranscriptionShadowLane
from __future__ import annotations

from collections import deque
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import re
import tempfile
import threading
import time
from typing import Any, Callable
from uuid import uuid4

from src.mandala_sme_shadow import MandalaSMEShadow


OBSERVATION_SCHEMA = "jarvis-sme-live-transcription-observation/1.0"
PROMOTION_SCHEMA = "jarvis-sme-live-transcription-promotion/1.0"
DEFAULT_MAX_AUDIO_BYTES = 10 * 1024 * 1024
DEFAULT_QUEUE_SIZE = 4
DEFAULT_MIN_OBSERVATIONS = 25
DEFAULT_MAX_P95_LATENCY_MS = 2500.0


def _env_true(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _safe_token(value: str, default: str) -> str:
    token = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value or "").strip()).strip("-")
    return (token or default)[:96]


def _words(value: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", str(value or "").lower())


def _word_agreement(primary: str, shadow: str) -> dict[str, Any]:
    expected = _words(primary)
    observed = _words(shadow)
    previous = list(range(len(observed) + 1))
    for row, expected_word in enumerate(expected, start=1):
        current = [row]
        for column, observed_word in enumerate(observed, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (expected_word != observed_word),
                )
            )
        previous = current
    edits = previous[-1]
    denominator = max(len(expected), 1)
    disagreement = edits / denominator
    return {
        "status": "scored",
        "kind": "primary_shadow_agreement_not_ground_truth",
        "primaryWordCount": len(expected),
        "shadowWordCount": len(observed),
        "wordDisagreements": edits,
        "wordDisagreementRate": round(disagreement, 6),
        "wordAgreement": round(max(0.0, 1.0 - disagreement), 6),
        "exactMatch": expected == observed,
    }


class SmeTranscriptionShadowLane:
    """Queue real requests without delaying or replacing Jarvis responses."""

    def __init__(
        self,
        *,
        root: Path | None = None,
        runtime_root: Path | None = None,
        enabled: bool | None = None,
        provider: str | None = None,
        allow_cloud: bool | None = None,
        persist_ledger: bool | None = None,
        queue_size: int | None = None,
        max_audio_bytes: int | None = None,
        min_observations: int | None = None,
        max_p95_latency_ms: float | None = None,
        adapter_factory: Callable[[], MandalaSMEShadow] | None = None,
    ) -> None:
        self.root = (root or Path(__file__).resolve().parents[1]).resolve()
        self.runtime_root = (
            runtime_root
            or self.root / ".runtime" / "sme-shadow" / "live-transcription"
        ).resolve()
        self.enabled = (
            _env_true("JARVIS_SME_TRANSCRIPTION_SHADOW")
            if enabled is None
            else bool(enabled)
        )
        self.provider = str(
            provider or os.getenv("SME_TRANSCRIPTION_PROVIDER") or "local"
        ).strip().lower()
        self.allow_cloud = (
            _env_true("SME_TRANSCRIPTION_ALLOW_CLOUD")
            if allow_cloud is None
            else bool(allow_cloud)
        )
        self.persist_ledger = (
            _env_true("JARVIS_SME_SHADOW_PERSIST_LEDGER")
            if persist_ledger is None
            else bool(persist_ledger)
        )
        if self.provider not in {"local", "cloud", "auto"}:
            raise ValueError("SME transcription provider must be local, cloud, or auto")
        self.queue_size = max(
            1,
            int(queue_size or os.getenv("JARVIS_SME_SHADOW_QUEUE_SIZE") or DEFAULT_QUEUE_SIZE),
        )
        self.max_audio_bytes = max(
            45,
            int(
                max_audio_bytes
                or os.getenv("JARVIS_SME_SHADOW_MAX_AUDIO_BYTES")
                or DEFAULT_MAX_AUDIO_BYTES
            ),
        )
        self.min_observations = max(
            1,
            int(
                min_observations
                or os.getenv("JARVIS_SME_SHADOW_MIN_OBSERVATIONS")
                or DEFAULT_MIN_OBSERVATIONS
            ),
        )
        self.max_p95_latency_ms = float(
            max_p95_latency_ms
            or os.getenv("JARVIS_SME_SHADOW_MAX_P95_LATENCY_MS")
            or DEFAULT_MAX_P95_LATENCY_MS
        )
        self.metrics_path = self.runtime_root / "observations.jsonl"
        self.promotion_path = self.runtime_root / "promotion-status.json"
        self.inbox_root = self.runtime_root / "inbox"
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=self.queue_size)
        self._worker: threading.Thread | None = None
        self._worker_lock = threading.Lock()
        self._metrics_lock = threading.Lock()
        self.last_worker_error: str | None = None
        self._adapter_factory = adapter_factory or (
            lambda: MandalaSMEShadow(
                root=self.root,
                runtime_root=self.runtime_root,
                timeout_seconds=float(os.getenv("JARVIS_SME_SHADOW_TIMEOUT_SECONDS", "60")),
            )
        )

    def submit(
        self,
        audio_bytes: bytes,
        *,
        filename: str,
        language: str | None,
        primary_status: str,
        primary_text: str | None,
        primary_latency_ms: float | None,
        primary_error: str | None = None,
    ) -> dict[str, Any]:
        """Queue a shadow observation and return without waiting for inference."""
        if not self.enabled:
            return {"status": "disabled"}
        if not isinstance(audio_bytes, bytes) or len(audio_bytes) <= 44:
            return {"status": "rejected", "reason": "audio_too_small"}
        if len(audio_bytes) > self.max_audio_bytes:
            return {"status": "rejected", "reason": "audio_too_large"}
        suffix = Path(filename or "audio.wav").suffix.lower() or ".wav"
        if suffix != ".wav":
            return {"status": "rejected", "reason": "shadow_accepts_wav_only"}

        intent_id = "live-transcription-" + uuid4().hex
        item = {
            "intent_id": intent_id,
            "audio_bytes": audio_bytes,
            "filename": Path(filename or "audio.wav").name,
            "language": str(language or "en").strip().lower(),
            "primary_status": _safe_token(primary_status, "unknown"),
            "primary_text": str(primary_text or ""),
            "primary_latency_ms": primary_latency_ms,
            "primary_error": _safe_token(primary_error or "", "") or None,
            "queued_at": time.time(),
        }
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            return {"status": "queue_full"}
        self._ensure_worker()
        return {"status": "queued", "intent_id": intent_id}

    def _ensure_worker(self) -> None:
        with self._worker_lock:
            if self._worker is not None and self._worker.is_alive():
                return
            self._worker = threading.Thread(
                target=self._worker_loop,
                name="sme-transcription-shadow",
                daemon=True,
            )
            self._worker.start()

    def _worker_loop(self) -> None:
        while True:
            item = self._queue.get()
            try:
                try:
                    self._process(item)
                except Exception as exc:
                    self.last_worker_error = f"{type(exc).__name__}: {exc}"[:500]
            finally:
                self._queue.task_done()

    def _process(self, item: dict[str, Any]) -> None:
        processing_started = time.time()
        self.inbox_root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.inbox_root, 0o700)
        source_sha256 = hashlib.sha256(item["audio_bytes"]).hexdigest()
        temporary_path: Path | None = None
        receipt: dict[str, Any] | None = None
        runner_error: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                suffix=".wav",
                prefix="shadow-",
                dir=self.inbox_root,
                delete=False,
            ) as temporary:
                temporary.write(item["audio_bytes"])
                temporary_path = Path(temporary.name)
            os.chmod(temporary_path, 0o600)
            adapter = self._adapter_factory()
            receipt = adapter.transcribe_audio(
                temporary_path,
                intent_id=item["intent_id"],
                provider=self.provider,
                allow_cloud=self.allow_cloud,
                language=item["language"],
                persist_ledger=self.persist_ledger,
                session_id="jarvis-live-transcription-shadow",
            )
        except Exception as exc:
            runner_error = f"{type(exc).__name__}: {exc}"[:500]
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

        primary_text = item["primary_text"]
        shadow_text = str(((receipt or {}).get("transcription") or {}).get("text") or "")
        if primary_text and shadow_text and item["primary_status"] == "completed":
            agreement = _word_agreement(primary_text, shadow_text)
        else:
            agreement = {
                "status": "not_scored",
                "kind": "primary_shadow_agreement_not_ground_truth",
            }

        evidence = (receipt or {}).get("evidence_completeness") or {}
        provider = (receipt or {}).get("provider") or {
            "requestedPolicy": self.provider,
            "cloudAllowed": self.allow_cloud,
        }
        observation = {
            "schema": OBSERVATION_SCHEMA,
            "observed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "intent_id": item["intent_id"],
            "queue_delay_ms": round((processing_started - item["queued_at"]) * 1000, 3),
            "source": {
                "sha256": source_sha256,
                "byteLength": len(item["audio_bytes"]),
                "audioRetained": False,
            },
            "primary_jarvis": {
                "status": item["primary_status"],
                "latency_ms": item["primary_latency_ms"],
                "transcriptSha256": hashlib.sha256(primary_text.encode()).hexdigest()
                if primary_text
                else None,
                "transcriptWordCount": len(_words(primary_text)),
                "errorClass": item["primary_error"],
                "responseChangedByShadow": False,
            },
            "sme_shadow": {
                "status": (receipt or {}).get("status") or "runner_error",
                "latency_ms": (receipt or {}).get("latency_ms"),
                "provider": provider,
                "transcriptSha256": hashlib.sha256(shadow_text.encode()).hexdigest()
                if shadow_text
                else None,
                "transcriptWordCount": len(_words(shadow_text)),
                "evidenceCompleteness": evidence,
                "replayHandle": (receipt or {}).get("replay_handle"),
                "receiptPath": (receipt or {}).get("receipt_path"),
                "continuityLedger": (receipt or {}).get("continuity_ledger"),
                "runnerError": runner_error,
            },
            "comparison": agreement,
            "privacy": {
                "transcriptContentStoredInMetrics": False,
                "cloudAllowed": self.allow_cloud,
                "outboundData": bool(provider.get("outboundData", False)),
            },
            "authority": {
                "mode": "shadow",
                "primaryJarvisResponseChanged": False,
                "divineCoreDemoted": False,
            },
        }
        self._append_observation(observation)

    def _append_observation(self, observation: dict[str, Any]) -> None:
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        with self._metrics_lock:
            with self.metrics_path.open("a", encoding="utf-8") as stream:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
                stream.write(json.dumps(observation, sort_keys=True) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
                self._write_promotion_status()
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _write_promotion_status(self) -> None:
        observations: deque[dict[str, Any]] = deque(maxlen=1000)
        if self.metrics_path.is_file():
            for line in self.metrics_path.read_text(encoding="utf-8").splitlines():
                try:
                    observations.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        total = len(observations)
        completed = [
            item for item in observations if item["sme_shadow"]["status"] == "verified"
        ]
        refused = [
            item for item in observations if item["sme_shadow"]["status"] == "refused"
        ]
        evidence_complete = [
            item
            for item in observations
            if item["sme_shadow"].get("evidenceCompleteness", {}).get("complete") is True
        ]
        comparable = [
            item for item in observations if item["comparison"].get("status") == "scored"
        ]
        linked = [
            item
            for item in observations
            if (item["sme_shadow"].get("continuityLedger") or {}).get("status") == "linked"
        ]
        latencies = sorted(
            float(item["sme_shadow"]["latency_ms"])
            for item in completed
            if item["sme_shadow"].get("latency_ms") is not None
        )
        p95_latency = (
            latencies[max(0, math.ceil(len(latencies) * 0.95) - 1)] if latencies else None
        )
        mean_agreement = (
            round(
                sum(item["comparison"]["wordAgreement"] for item in comparable)
                / len(comparable),
                6,
            )
            if comparable
            else None
        )
        rates = {
            "completion": round(len(completed) / total, 6) if total else 0.0,
            "refusal": round(len(refused) / total, 6) if total else 0.0,
            "evidenceComplete": round(len(evidence_complete) / total, 6)
            if total
            else 0.0,
            "continuityLedgerLinked": round(len(linked) / total, 6) if total else 0.0,
        }
        criteria = {
            "minimumObservations": total >= self.min_observations,
            "minimumComparableObservations": len(comparable) >= self.min_observations,
            "completionRateAtLeast95Percent": rates["completion"] >= 0.95,
            "evidenceCompleteness100Percent": rates["evidenceComplete"] == 1.0,
            "meanAgreementAtLeast90Percent": mean_agreement is not None
            and mean_agreement >= 0.9,
            "p95LatencyWithinLimit": p95_latency is not None
            and p95_latency <= self.max_p95_latency_ms,
            "continuityLedgerLinked100Percent": rates["continuityLedgerLinked"] == 1.0,
            "groundTruthAccuracyBenchmark": False,
        }
        hold_reasons = [name for name, passed in criteria.items() if not passed]
        status = {
            "schema": PROMOTION_SCHEMA,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "mode": "shadow",
            "observations": total,
            "comparable_observations": len(comparable),
            "rates": rates,
            "mean_primary_shadow_agreement": mean_agreement,
            "p95_sme_latency_ms": p95_latency,
            "p95_latency_limit_ms": self.max_p95_latency_ms,
            "criteria": criteria,
            "promotion_eligible": False,
            "automatic_promotion": False,
            "operator_review_required": True,
            "hold_reasons": hold_reasons,
            "divine_core_demoted": False,
        }
        temporary = self.promotion_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.promotion_path)

    def flush(self, timeout_seconds: float = 10.0) -> bool:
        """Wait for queued work in tests and controlled shutdown paths."""
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if self._queue.unfinished_tasks == 0:
                return True
            time.sleep(0.01)
        return self._queue.unfinished_tasks == 0


_LANE: SmeTranscriptionShadowLane | None = None
_LANE_LOCK = threading.Lock()


def get_transcription_shadow_lane() -> SmeTranscriptionShadowLane:
    global _LANE
    with _LANE_LOCK:
        if _LANE is None:
            _LANE = SmeTranscriptionShadowLane()
        return _LANE


def submit_transcription_shadow(
    audio_bytes: bytes,
    *,
    filename: str,
    language: str | None,
    primary_status: str,
    primary_text: str | None,
    primary_latency_ms: float | None,
    primary_error: str | None = None,
) -> dict[str, Any]:
    """Public non-blocking hook used by the canonical Jarvis API route."""
    return get_transcription_shadow_lane().submit(
        audio_bytes,
        filename=filename,
        language=language,
        primary_status=primary_status,
        primary_text=primary_text,
        primary_latency_ms=primary_latency_ms,
        primary_error=primary_error,
    )
