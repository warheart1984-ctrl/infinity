"""Shadow-only Project Infinity adapter for the packaged Mandala SME runtime."""

# Mythic: SME governed nervous-system shadow
# Engineering: MandalaSMEShadow
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request


SHADOW_SCHEMA = "jarvis-sme-shadow-receipt/1.0"
DEFAULT_TIMEOUT_SECONDS = 20.0
EVIDENCE_SEGMENTS = (
    "auditEvidence",
    "authorityEvidence",
    "decisionEvidence",
    "outputEvidence",
    "replayEvidence",
    "validationEvidence",
    "verificationEvidence",
)


class SmeShadowError(RuntimeError):
    """Raised when the bounded SME shadow protocol fails closed."""


class ContinuityLedgerLinkError(SmeShadowError):
    """Raised when explicitly requested Continuity Ledger persistence fails."""


def _safe_token(value: str, default: str) -> str:
    token = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value or "").strip()).strip("-")
    return (token or default)[:96]


class MandalaSMEShadow:
    """Run SME beside Jarvis without changing the primary cognition path."""

    def __init__(
        self,
        *,
        root: Path | None = None,
        runtime_root: Path | None = None,
        node_binary: str | None = None,
        ledger_url: str | None = None,
        local_transcription_url: str | None = None,
        cloud_transcription_url: str | None = None,
        cloud_transcription_token: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.root = (root or Path(__file__).resolve().parents[1]).resolve()
        self.runtime_root = (
            runtime_root or self.root / ".runtime" / "sme-shadow"
        ).resolve()
        self.node_binary = node_binary or os.getenv("SME_NODE_BINARY", "node")
        self.ledger_url = (
            ledger_url
            or os.getenv("JARVIS_MEMORYBOARD_URL")
            or "http://127.0.0.1:8001"
        ).rstrip("/")
        self.timeout_seconds = float(timeout_seconds)
        self.local_transcription_url = (
            local_transcription_url
            or os.getenv("SME_TRANSCRIPTION_LOCAL_URL")
            or "http://127.0.0.1:13312/inference"
        )
        self.cloud_transcription_url = (
            cloud_transcription_url
            or os.getenv("SME_TRANSCRIPTION_CLOUD_URL")
            or ""
        )
        self.cloud_transcription_token = (
            cloud_transcription_token
            or os.getenv("SME_TRANSCRIPTION_CLOUD_TOKEN")
            or ""
        )
        self.package_root = self.root / "external" / "mandala_sme" / "package"
        self.runner_path = (
            self.root
            / "external"
            / "mandala_sme"
            / "shadow"
            / "image_preflight.js"
        )
        self.transcription_runner_path = (
            self.root
            / "external"
            / "mandala_sme"
            / "shadow"
            / "transcription.js"
        )

    def inspect_image(
        self,
        image_path: Path | str,
        *,
        intent_id: str,
        actor_id: str = "jarvis-shadow",
        persist_ledger: bool = False,
        session_id: str = "sme-shadow",
    ) -> dict[str, Any]:
        """Run deterministic PNG preflight through the packaged SME Lattice."""
        source = Path(image_path).expanduser().resolve()
        if not source.is_file():
            raise SmeShadowError(f"image does not exist: {source}")
        if not self.runner_path.is_file() or not self.package_root.is_dir():
            raise SmeShadowError("packaged Mandala SME import is incomplete")

        request_payload = {
            "intent_id": _safe_token(intent_id, "intent-shadow"),
            "actor_id": _safe_token(actor_id, "jarvis-shadow"),
            "image_path": str(source),
        }
        completed = subprocess.run(
            [self.node_binary, str(self.runner_path)],
            input=json.dumps(request_payload),
            text=True,
            capture_output=True,
            cwd=str(self.root),
            timeout=self.timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            detail = " ".join(completed.stderr.split())[:1000]
            raise SmeShadowError(f"SME shadow runner failed: {detail}")

        try:
            shadow_result = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise SmeShadowError("SME shadow runner returned invalid JSON") from exc

        lrc = shadow_result.get("lrc") or {}
        if (
            shadow_result.get("status") != "completed"
            or shadow_result.get("mode") != "shadow"
            or shadow_result.get("primaryResponseChanged") is not False
            or not shadow_result.get("evidencePresent")
            or not lrc.get("evidence")
            or not lrc.get("replayHandle")
        ):
            reason = str(lrc.get("violationReason") or "missing evidence or replay")
            raise SmeShadowError(
                "SME shadow result failed its evidence boundary: " + reason
            )

        source_result = lrc.get("result") or {}
        receipt_name = (
            _safe_token(intent_id, "intent-shadow")
            + "-"
            + str(source_result.get("sourceSha256") or "nohash")[:12]
            + ".json"
        )
        receipt_path = self.runtime_root / "receipts" / receipt_name
        receipt = {
            "schema": SHADOW_SCHEMA,
            "mode": "shadow",
            "status": "verified",
            "capability": "image_preflight",
            "claim_scope": "file integrity and PNG metadata only",
            "semantic_understanding": False,
            "primary_jarvis_response_changed": False,
            "divine_core_demoted": False,
            "intent_id": request_payload["intent_id"],
            "actor_id": request_payload["actor_id"],
            "package": shadow_result.get("package"),
            "latency_ms": shadow_result.get("latencyMs"),
            "source": source_result,
            "evidence": lrc["evidence"],
            "replay_handle": lrc["replayHandle"],
            "receipt_path": str(receipt_path),
            "continuity_ledger": {
                "required_for_promotion": True,
                "status": "not_requested",
                "memory_id": None,
            },
        }
        self._write_receipt(receipt_path, receipt)

        if persist_ledger:
            try:
                memory_id = self._post_ledger(receipt, session_id=session_id)
            except Exception as exc:
                receipt["continuity_ledger"] = {
                    "required_for_promotion": True,
                    "status": "failed",
                    "memory_id": None,
                    "error": str(exc)[:500],
                }
                self._write_receipt(receipt_path, receipt)
                if isinstance(exc, ContinuityLedgerLinkError):
                    raise
                raise ContinuityLedgerLinkError(str(exc)) from exc
            receipt["continuity_ledger"] = {
                "required_for_promotion": True,
                "status": "linked",
                "memory_id": memory_id,
            }
            self._write_receipt(receipt_path, receipt)

        return receipt

    def transcribe_audio(
        self,
        audio_path: Path | str,
        *,
        intent_id: str,
        actor_id: str = "jarvis-shadow",
        provider: str | None = None,
        allow_cloud: bool | None = None,
        language: str = "en",
        local_model: str | None = None,
        cloud_model: str | None = None,
        reference_text: str | None = None,
        persist_ledger: bool = False,
        session_id: str = "sme-shadow",
    ) -> dict[str, Any]:
        """Transcribe WAV audio through governed local/cloud SME-AUD policy."""
        source = Path(audio_path).expanduser().resolve()
        if not source.is_file():
            raise SmeShadowError(f"audio does not exist: {source}")
        if not self.transcription_runner_path.is_file() or not self.package_root.is_dir():
            raise SmeShadowError("packaged Mandala SME transcription import is incomplete")

        provider_policy = str(
            provider or os.getenv("SME_TRANSCRIPTION_PROVIDER") or "local"
        ).strip().lower()
        if provider_policy not in {"local", "cloud", "auto"}:
            raise SmeShadowError("transcription provider must be local, cloud, or auto")
        if allow_cloud is None:
            allow_cloud = os.getenv("SME_TRANSCRIPTION_ALLOW_CLOUD", "").lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
        language = str(language or "").strip().lower()
        if language and not re.fullmatch(r"[a-z]{2,3}", language):
            raise SmeShadowError("language must be a 2-3 letter code")

        source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
        from src.audio_normalization import normalize_wav_for_sme

        execution_source, normalization = normalize_wav_for_sme(
            source,
            temporary_root=self.runtime_root / "normalized-audio",
        )
        request_payload = {
            "intent_id": _safe_token(intent_id, "intent-shadow"),
            "actor_id": _safe_token(actor_id, "jarvis-shadow"),
            "audio_path": str(execution_source),
            "provider": provider_policy,
            "allow_cloud": bool(allow_cloud),
            "language": language or None,
            "local_url": self.local_transcription_url,
            "cloud_url": self.cloud_transcription_url,
            "cloud_token": self.cloud_transcription_token,
            "local_model": local_model
            or os.getenv("SME_TRANSCRIPTION_LOCAL_MODEL")
            or "mandala-whisper-governed-vulkan-q4-cpu-fallback",
            "cloud_model": cloud_model
            or os.getenv("SME_TRANSCRIPTION_CLOUD_MODEL")
            or "whisper-1",
            "backend_timeout_ms": int(max(self.timeout_seconds, 1.0) * 1000),
        }
        try:
            completed = subprocess.run(
                [self.node_binary, str(self.transcription_runner_path)],
                input=json.dumps(request_payload),
                text=True,
                capture_output=True,
                cwd=str(self.root),
                timeout=max(self.timeout_seconds + 5.0, 10.0),
                check=False,
            )
        finally:
            if execution_source != source:
                execution_source.unlink(missing_ok=True)
        if completed.returncode != 0:
            detail = " ".join(completed.stderr.split())[:1000]
            raise SmeShadowError(f"SME transcription runner failed: {detail}")
        try:
            shadow_result = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise SmeShadowError("SME transcription runner returned invalid JSON") from exc

        lrc = shadow_result.get("lrc") or {}
        shadow_status = str(shadow_result.get("status") or "")
        if (
            shadow_status not in {"completed", "refused"}
            or shadow_result.get("mode") != "shadow"
            or shadow_result.get("primaryResponseChanged") is not False
            or not shadow_result.get("evidencePresent")
            or not lrc.get("evidence")
            or not lrc.get("replayHandle")
        ):
            raise SmeShadowError(
                "SME transcription failed its evidence boundary: "
                + str(lrc.get("violationReason") or "missing evidence or replay")
            )

        evidence = lrc["evidence"]
        segments = (evidence.get("segments") or {}) if isinstance(evidence, dict) else {}
        present_segments = [name for name in EVIDENCE_SEGMENTS if name in segments]
        evidence_complete = len(present_segments) == len(EVIDENCE_SEGMENTS)
        if not evidence_complete:
            raise SmeShadowError("SME transcription evidence bundle is incomplete")

        result = lrc.get("result") or {}
        result_sha256 = str(result.get("sourceSha256") or source_sha256)
        receipt_name = (
            _safe_token(intent_id, "intent-shadow")
            + "-transcription-"
            + provider_policy
            + "-"
            + result_sha256[:12]
            + ".json"
        )
        receipt_path = self.runtime_root / "receipts" / receipt_name
        transcript = str(result.get("transcript") or "").strip()
        receipt = {
            "schema": SHADOW_SCHEMA,
            "mode": "shadow",
            "status": "verified" if shadow_status == "completed" else "refused",
            "capability": "transcription",
            "claim_scope": "speech-to-text hypothesis only",
            "primary_jarvis_response_changed": False,
            "divine_core_demoted": False,
            "intent_id": request_payload["intent_id"],
            "actor_id": request_payload["actor_id"],
            "package": shadow_result.get("package"),
            "latency_ms": shadow_result.get("latencyMs"),
            "source": {
                "sourceName": source.name,
                "sourceSha256": source_sha256,
                "executionSourceSha256": result_sha256,
                "byteLength": source.stat().st_size,
                "mimeType": result.get("mimeType") or "audio/wav",
                "channels": result.get("channels"),
                "sampleRate": result.get("sampleRate"),
                "bitsPerSample": result.get("bitsPerSample"),
                "durationSec": result.get("durationSec"),
                "normalization": normalization,
            },
            "transcription": {
                "text": transcript,
                "language": result.get("language"),
                "segments": result.get("segments") or [],
            },
            "provider": result.get("provider")
            or {
                "requestedPolicy": provider_policy,
                "cloudAllowed": bool(allow_cloud),
            },
            "attempts": result.get("attempts") or [],
            "refusal": None
            if shadow_status == "completed"
            else {"reason": str(lrc.get("violationReason") or "provider refused")[:1000]},
            "accuracy": self._score_transcript(reference_text, transcript),
            "evidence_completeness": {
                "required": len(EVIDENCE_SEGMENTS),
                "present": len(present_segments),
                "complete": evidence_complete,
                "segments": present_segments,
            },
            "evidence": evidence,
            "replay_handle": lrc["replayHandle"],
            "receipt_path": str(receipt_path),
            "continuity_ledger": {
                "required_for_promotion": True,
                "status": "not_requested",
                "memory_id": None,
            },
        }
        self._write_receipt(receipt_path, receipt)

        if persist_ledger:
            try:
                memory_id = self._post_ledger(receipt, session_id=session_id)
            except Exception as exc:
                receipt["continuity_ledger"] = {
                    "required_for_promotion": True,
                    "status": "failed",
                    "memory_id": None,
                    "error": str(exc)[:500],
                }
                self._write_receipt(receipt_path, receipt)
                if isinstance(exc, ContinuityLedgerLinkError):
                    raise
                raise ContinuityLedgerLinkError(str(exc)) from exc
            receipt["continuity_ledger"] = {
                "required_for_promotion": True,
                "status": "linked",
                "memory_id": memory_id,
            }
            self._write_receipt(receipt_path, receipt)

        return receipt

    @staticmethod
    def _score_transcript(reference_text: str | None, transcript: str) -> dict[str, Any]:
        if reference_text is None:
            return {"status": "not_scored"}
        reference_words = re.findall(r"[a-z0-9']+", reference_text.lower())
        observed_words = re.findall(r"[a-z0-9']+", transcript.lower())
        previous = list(range(len(observed_words) + 1))
        for row, expected in enumerate(reference_words, start=1):
            current = [row]
            for column, observed in enumerate(observed_words, start=1):
                current.append(
                    min(
                        current[-1] + 1,
                        previous[column] + 1,
                        previous[column - 1] + (expected != observed),
                    )
                )
            previous = current
        edits = previous[-1]
        denominator = max(len(reference_words), 1)
        word_error_rate = edits / denominator
        return {
            "status": "scored",
            "reference": reference_text,
            "referenceWordCount": len(reference_words),
            "observedWordCount": len(observed_words),
            "wordErrors": edits,
            "wordErrorRate": round(word_error_rate, 6),
            "wordAccuracy": round(max(0.0, 1.0 - word_error_rate), 6),
            "exactMatch": reference_words == observed_words,
        }

    def compare_transcription(
        self,
        audio_path: Path | str,
        *,
        intent_id: str,
        reference_text: str,
        provider: str | None = None,
        allow_cloud: bool | None = None,
        language: str = "en",
        primary_transcriber: Any | None = None,
        persist_ledger: bool = False,
        session_id: str = "sme-transcription-comparison",
    ) -> dict[str, Any]:
        """Compare Jarvis' current transcription path with the SME shadow result."""
        source = Path(audio_path).expanduser().resolve()
        primary_started = time.perf_counter()
        primary_result: dict[str, Any]
        try:
            if primary_transcriber is None:
                from src.speech import speech_to_text

                primary_transcriber = speech_to_text.transcribe
            observed = primary_transcriber(str(source), language=language)
            primary_text = str((observed or {}).get("text") or "").strip()
            if not primary_text:
                raise RuntimeError("primary transcription returned empty text")
            primary_result = {
                "status": "completed",
                "latency_ms": round((time.perf_counter() - primary_started) * 1000, 3),
                "transcription": primary_text,
                "accuracy": self._score_transcript(reference_text, primary_text),
                "evidence_completeness": {
                    "status": "not_provided_by_primary_path"
                },
            }
        except Exception as exc:
            primary_result = {
                "status": "unavailable",
                "latency_ms": round((time.perf_counter() - primary_started) * 1000, 3),
                "reason": str(exc)[:500],
                "accuracy": {"status": "not_scored"},
                "evidence_completeness": {
                    "status": "not_provided_by_primary_path"
                },
            }

        sme_receipt = self.transcribe_audio(
            source,
            intent_id=intent_id,
            provider=provider,
            allow_cloud=allow_cloud,
            language=language,
            reference_text=reference_text,
            persist_ledger=persist_ledger,
            session_id=session_id,
        )
        both_completed = (
            primary_result["status"] == "completed"
            and sme_receipt["status"] == "verified"
        )
        accuracy_non_inferior = None
        latency_ratio = None
        if both_completed:
            accuracy_non_inferior = (
                sme_receipt["accuracy"].get("wordAccuracy", 0)
                >= primary_result["accuracy"].get("wordAccuracy", 0)
            )
            primary_latency = float(primary_result["latency_ms"] or 0)
            if primary_latency > 0:
                latency_ratio = round(float(sme_receipt["latency_ms"]) / primary_latency, 6)

        report_path = (
            self.runtime_root
            / "comparisons"
            / (_safe_token(intent_id, "intent-shadow") + ".json")
        )
        report = {
            "schema": "jarvis-sme-transcription-comparison/1.0",
            "mode": "shadow",
            "intent_id": _safe_token(intent_id, "intent-shadow"),
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "reference_text": reference_text,
            "primary_jarvis": primary_result,
            "sme_shadow": {
                "status": sme_receipt["status"],
                "latency_ms": sme_receipt["latency_ms"],
                "provider": sme_receipt["provider"],
                "transcription": sme_receipt["transcription"]["text"],
                "accuracy": sme_receipt["accuracy"],
                "refusal": sme_receipt["refusal"],
                "evidence_completeness": sme_receipt["evidence_completeness"],
                "replay_handle": sme_receipt["replay_handle"],
                "receipt_path": sme_receipt["receipt_path"],
                "continuity_ledger": sme_receipt["continuity_ledger"],
            },
            "comparison": {
                "complete": both_completed,
                "accuracy_non_inferior": accuracy_non_inferior,
                "sme_to_primary_latency_ratio": latency_ratio,
            },
            "promotion_gate": {
                "eligible": bool(
                    both_completed
                    and accuracy_non_inferior
                    and sme_receipt["evidence_completeness"]["complete"]
                    and sme_receipt["continuity_ledger"]["status"] == "linked"
                ),
                "operator_review_required": True,
                "divine_core_demoted": False,
            },
            "report_path": str(report_path),
        }
        self._write_receipt(report_path, report)
        return report

    @staticmethod
    def _write_receipt(path: Path, receipt: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    def _post_ledger(self, receipt: dict[str, Any], *, session_id: str) -> str:
        source = receipt.get("source") or {}
        package = receipt.get("package") or {}
        capability = _safe_token(str(receipt.get("capability") or "unknown"), "unknown")
        receipt_status = str(receipt.get("status") or "unknown")
        payload = {
            "content": (
                f"SME shadow {capability} finished with status {receipt_status}, "
                "governed evidence, and "
                f"replay for source sha256 {source.get('sourceSha256')}; "
                f"package {package.get('name')}@{package.get('version')}."
            ),
            "source_agent": "mandala-sme-shadow",
            "session_id": _safe_token(session_id, "sme-shadow"),
            "type": "fact",
            "confidence": 1.0,
            "status": "verified",
            "subject": f"sme-shadow-{capability}",
            "tags": ["jarvis", "sme", "shadow", "evidence", capability],
            "evidence": [
                {
                    "kind": "receipt",
                    "ref": str(receipt["receipt_path"]),
                    "note": "Shadow execution receipt; bounded claim only.",
                },
                {
                    "kind": "replay",
                    "ref": str(receipt["replay_handle"]),
                    "note": "SME Lattice replay handle.",
                },
            ],
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib_request.Request(
            self.ledger_url + "/api/jarvis/memory",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib_request.urlopen(req, timeout=5.0) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError, urllib_error.URLError) as exc:
            raise ContinuityLedgerLinkError(
                f"Continuity Ledger link failed at {self.ledger_url}"
            ) from exc

        memory_id = str((result.get("memory") or {}).get("id") or "").strip()
        if not memory_id:
            raise ContinuityLedgerLinkError(
                "Continuity Ledger response did not include a memory id"
            )
        return memory_id
