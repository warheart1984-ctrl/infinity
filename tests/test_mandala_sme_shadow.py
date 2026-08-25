"""Consumer tests for the packaged Mandala SME shadow adapter."""

from __future__ import annotations

import base64
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import wave

import pytest

from src.mandala_sme_shadow import MandalaSMEShadow, SmeShadowError


ROOT = Path(__file__).resolve().parents[1]
ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
    "/x8AAusB9Y9Z4S0AAAAASUVORK5CYII="
)


def _write_png(tmp_path: Path) -> Path:
    image = tmp_path / "input.png"
    image.write_bytes(ONE_PIXEL_PNG)
    return image


def _write_wav(tmp_path: Path, *, sample_rate: int = 16000) -> Path:
    audio = tmp_path / "input.wav"
    with wave.open(str(audio), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x00" * sample_rate)
    return audio


@contextmanager
def _transcription_backend(text: str):
    observed: dict[str, object] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
            length = int(self.headers.get("Content-Length", "0"))
            observed["authorization"] = self.headers.get("Authorization")
            observed["content_type"] = self.headers.get("Content-Type")
            observed["body"] = self.rfile.read(length)
            payload = json.dumps({"text": text, "language": "en"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/inference", observed
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_packaged_sme_runs_png_preflight_with_evidence(tmp_path: Path) -> None:
    shadow = MandalaSMEShadow(root=ROOT, runtime_root=tmp_path / "runtime")

    receipt = shadow.inspect_image(
        _write_png(tmp_path),
        intent_id="test-image-preflight",
    )

    assert receipt["status"] == "verified"
    assert receipt["mode"] == "shadow"
    assert receipt["package"]["name"] == "@mandala/sme"
    assert receipt["package"]["version"] == "0.1.1"
    assert receipt["source"]["width"] == 1
    assert receipt["source"]["height"] == 1
    assert receipt["source"]["semanticUnderstanding"] is False
    assert receipt["evidence"]
    assert len(receipt["replay_handle"]) == 64
    assert receipt["primary_jarvis_response_changed"] is False
    assert receipt["divine_core_demoted"] is False
    assert Path(receipt["receipt_path"]).is_file()


def test_shadow_preflight_fails_closed_for_non_png(tmp_path: Path) -> None:
    source = tmp_path / "not-an-image.txt"
    source.write_text("not a png", encoding="utf-8")
    shadow = MandalaSMEShadow(root=ROOT, runtime_root=tmp_path / "runtime")

    with pytest.raises(SmeShadowError, match="currently accepts PNG only"):
        shadow.inspect_image(source, intent_id="reject-text")


def test_explicit_ledger_persistence_records_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shadow = MandalaSMEShadow(root=ROOT, runtime_root=tmp_path / "runtime")
    observed: dict[str, object] = {}

    def fake_post(receipt: dict[str, object], *, session_id: str) -> str:
        observed["receipt_exists"] = Path(str(receipt["receipt_path"])).is_file()
        observed["session_id"] = session_id
        return "mem-shadow-test"

    monkeypatch.setattr(shadow, "_post_ledger", fake_post)
    receipt = shadow.inspect_image(
        _write_png(tmp_path),
        intent_id="ledger-link",
        persist_ledger=True,
        session_id="test-session",
    )

    assert observed == {"receipt_exists": True, "session_id": "test-session"}
    assert receipt["continuity_ledger"]["status"] == "linked"
    assert receipt["continuity_ledger"]["memory_id"] == "mem-shadow-test"
    persisted = json.loads(Path(receipt["receipt_path"]).read_text(encoding="utf-8"))
    assert persisted["continuity_ledger"]["memory_id"] == "mem-shadow-test"


def test_transcription_normalizes_pcm_wav_and_deletes_private_copy(tmp_path: Path) -> None:
    source = _write_wav(tmp_path, sample_rate=22050)
    with _transcription_backend("normalized transcript") as (endpoint, _):
        shadow = MandalaSMEShadow(
            root=ROOT,
            runtime_root=tmp_path / "runtime",
            local_transcription_url=endpoint,
        )
        receipt = shadow.transcribe_audio(
            source,
            intent_id="normalization-test",
            provider="local",
            reference_text="normalized transcript",
        )

    assert receipt["status"] == "verified"
    assert receipt["source"]["normalization"]["applied"] is True
    assert receipt["source"]["normalization"]["original"]["sampleRate"] == 22050
    assert receipt["source"]["normalization"]["target"]["sampleRate"] == 16000
    assert not list((tmp_path / "runtime" / "normalized-audio").glob("*.wav"))


def test_local_transcription_records_accuracy_latency_and_evidence(tmp_path: Path) -> None:
    reference = "Jarvis keeps the story coherent."
    with _transcription_backend(reference) as (endpoint, observed):
        shadow = MandalaSMEShadow(
            root=ROOT,
            runtime_root=tmp_path / "runtime",
            local_transcription_url=endpoint,
        )
        receipt = shadow.transcribe_audio(
            _write_wav(tmp_path),
            intent_id="local-transcription",
            provider="local",
            reference_text=reference,
        )

    assert receipt["status"] == "verified"
    assert receipt["provider"]["kind"] == "local"
    assert receipt["provider"]["outboundData"] is False
    assert receipt["accuracy"]["wordErrorRate"] == 0
    assert receipt["accuracy"]["exactMatch"] is True
    assert receipt["latency_ms"] >= 0
    assert receipt["evidence_completeness"]["complete"] is True
    assert receipt["evidence_completeness"]["present"] == 7
    assert str(observed["content_type"]).startswith("multipart/form-data;")


def test_cloud_transcription_requires_explicit_consent(tmp_path: Path) -> None:
    with _transcription_backend("should not be called") as (endpoint, observed):
        shadow = MandalaSMEShadow(
            root=ROOT,
            runtime_root=tmp_path / "runtime",
            cloud_transcription_url=endpoint,
        )
        receipt = shadow.transcribe_audio(
            _write_wav(tmp_path),
            intent_id="cloud-refusal",
            provider="cloud",
            allow_cloud=False,
        )

    assert receipt["status"] == "refused"
    assert receipt["refusal"]
    assert "explicit allow_cloud consent is required" in receipt["refusal"]["reason"]
    assert receipt["evidence_completeness"]["complete"] is True
    assert observed == {}


def test_cloud_transcription_is_switchable_and_redacts_token(tmp_path: Path) -> None:
    token = "unit-test-cloud-secret"
    with _transcription_backend("Cloud provider completed.") as (endpoint, observed):
        shadow = MandalaSMEShadow(
            root=ROOT,
            runtime_root=tmp_path / "runtime",
            cloud_transcription_url=endpoint,
            cloud_transcription_token=token,
        )
        receipt = shadow.transcribe_audio(
            _write_wav(tmp_path),
            intent_id="cloud-transcription",
            provider="cloud",
            allow_cloud=True,
        )

    assert receipt["status"] == "verified"
    assert receipt["provider"]["kind"] == "cloud"
    assert receipt["provider"]["outboundData"] is True
    assert observed["authorization"] == f"Bearer {token}"
    assert token not in json.dumps(receipt)


def test_auto_policy_falls_back_from_local_to_cloud(tmp_path: Path) -> None:
    with _transcription_backend("Cloud fallback completed.") as (endpoint, _):
        shadow = MandalaSMEShadow(
            root=ROOT,
            runtime_root=tmp_path / "runtime",
            local_transcription_url="http://127.0.0.1:1/inference",
            cloud_transcription_url=endpoint,
        )
        receipt = shadow.transcribe_audio(
            _write_wav(tmp_path),
            intent_id="auto-fallback",
            provider="auto",
            allow_cloud=True,
        )

    assert receipt["status"] == "verified"
    assert receipt["provider"]["kind"] == "cloud"
    assert [attempt["kind"] for attempt in receipt["attempts"]] == ["local", "cloud"]
    assert [attempt["status"] for attempt in receipt["attempts"]] == ["failed", "completed"]


def test_comparison_report_keeps_promotion_gated(tmp_path: Path) -> None:
    reference = "The governed comparison is complete."

    def primary(audio_path: str, *, language: str) -> dict[str, str]:
        assert Path(audio_path).is_file()
        assert language == "en"
        return {"text": reference}

    with _transcription_backend(reference) as (endpoint, _):
        shadow = MandalaSMEShadow(
            root=ROOT,
            runtime_root=tmp_path / "runtime",
            local_transcription_url=endpoint,
        )
        report = shadow.compare_transcription(
            _write_wav(tmp_path),
            intent_id="comparison-gate",
            reference_text=reference,
            provider="local",
            primary_transcriber=primary,
        )

    assert report["comparison"]["complete"] is True
    assert report["comparison"]["accuracy_non_inferior"] is True
    assert report["promotion_gate"]["eligible"] is False
    assert report["promotion_gate"]["operator_review_required"] is True
    assert report["promotion_gate"]["divine_core_demoted"] is False
    assert Path(report["report_path"]).is_file()


def test_comparison_can_link_ledger_but_still_requires_operator_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference = "Evidence can qualify a capability without automatic promotion."

    with _transcription_backend(reference) as (endpoint, _):
        shadow = MandalaSMEShadow(
            root=ROOT,
            runtime_root=tmp_path / "runtime",
            local_transcription_url=endpoint,
        )
        monkeypatch.setattr(shadow, "_post_ledger", lambda *args, **kwargs: "mem-linked")
        report = shadow.compare_transcription(
            _write_wav(tmp_path),
            intent_id="comparison-ledger-gate",
            reference_text=reference,
            provider="local",
            primary_transcriber=lambda *args, **kwargs: {"text": reference},
            persist_ledger=True,
        )

    assert report["sme_shadow"]["continuity_ledger"]["status"] == "linked"
    assert report["promotion_gate"]["eligible"] is True
    assert report["promotion_gate"]["operator_review_required"] is True
    assert report["promotion_gate"]["divine_core_demoted"] is False


def test_import_manifest_matches_stable_package() -> None:
    manifest = json.loads(
        (ROOT / "external" / "mandala_sme" / "IMPORT_MANIFEST.json").read_text(
            encoding="utf-8"
        )
    )
    package = json.loads(
        (ROOT / "external" / "mandala_sme" / "package" / "package.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["package"]["name"] == package["name"] == "@mandala/sme"
    assert manifest["package"]["version"] == package["version"] == "0.1.1"
    assert manifest["activation"]["mode"] == "shadow"
    assert manifest["activation"]["primary_jarvis_response_changed"] is False
    assert manifest["activation"]["divine_core_demoted"] is False
