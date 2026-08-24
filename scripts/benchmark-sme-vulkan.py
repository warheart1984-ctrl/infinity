"""Benchmark SME-AUD on Vulkan while reusing the fixed v2 primary baseline."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import statistics

from src.mandala_sme_shadow import MandalaSMEShadow


ROOT = Path(__file__).resolve().parents[1]
BASELINE_ROOT = ROOT / ".runtime" / "sme-shadow" / "hardening-benchmark-v2"
BENCHMARK_LABEL = os.getenv("SME_BENCHMARK_LABEL", "v3-vulkan")
ENDPOINT = os.getenv("SME_BENCHMARK_URL", "http://127.0.0.1:13313/inference")
MODEL_LABEL = os.getenv("SME_BENCHMARK_MODEL", "whisper-base.en-q8_0-vulkan")
BACKEND_LABEL = os.getenv(
    "SME_BENCHMARK_BACKEND",
    "whisper.cpp base.en Q8_0 Vulkan RX 580",
)
RUNTIME_ROOT = ROOT / ".runtime" / "sme-shadow" / f"hardening-benchmark-{BENCHMARK_LABEL}"
SUMMARY_PATH = RUNTIME_ROOT / "promotion-benchmark.json"


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)]


def main() -> int:
    adapter = MandalaSMEShadow(
        root=ROOT,
        runtime_root=RUNTIME_ROOT,
        local_transcription_url=ENDPOINT,
        timeout_seconds=120,
    )
    comparisons: list[dict] = []
    for index in range(1, 26):
        old_path = (
            BASELINE_ROOT
            / "comparisons"
            / f"hardening-benchmark-v2-{index:02d}.json"
        )
        baseline = json.loads(old_path.read_text(encoding="utf-8"))
        audio_path = BASELINE_ROOT / "audio" / f"sample-{index:02d}.wav"
        receipt = adapter.transcribe_audio(
            audio_path,
            intent_id=f"hardening-benchmark-{BENCHMARK_LABEL}-{index:02d}",
            provider="local",
            allow_cloud=False,
            language="en",
            local_model=MODEL_LABEL,
            reference_text=baseline["reference_text"],
            persist_ledger=True,
            session_id="sme-transcription-vulkan-benchmark",
        )
        comparison = {
            "schema": "jarvis-sme-transcription-comparison/1.0",
            "mode": "shadow",
            "intent_id": f"hardening-benchmark-{BENCHMARK_LABEL}-{index:02d}",
            "reference_text": baseline["reference_text"],
            "source_sha256": baseline["source_sha256"],
            "primary_jarvis": baseline["primary_jarvis"],
            "sme_shadow": {
                "status": receipt["status"],
                "transcription": receipt["transcription"]["text"],
                "latency_ms": receipt["latency_ms"],
                "accuracy": receipt["accuracy"],
                "provider": receipt["provider"],
                "refusal": receipt["refusal"],
                "evidence_completeness": receipt["evidence_completeness"],
                "continuity_ledger": receipt["continuity_ledger"],
                "replay_handle": receipt["replay_handle"],
                "receipt_path": receipt["receipt_path"],
            },
        }
        comparison_path = (
            RUNTIME_ROOT
            / "comparisons"
            / f"hardening-benchmark-{BENCHMARK_LABEL}-{index:02d}.json"
        )
        comparison_path.parent.mkdir(parents=True, exist_ok=True)
        comparison["report_path"] = str(comparison_path)
        comparison_path.write_text(
            json.dumps(comparison, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        comparisons.append(comparison)

    primary_accuracy = [
        float(item["primary_jarvis"]["accuracy"]["wordAccuracy"])
        for item in comparisons
        if item["primary_jarvis"]["status"] == "completed"
    ]
    sme_complete = [
        item for item in comparisons if item["sme_shadow"]["status"] == "verified"
    ]
    sme_accuracy = [
        float(item["sme_shadow"]["accuracy"]["wordAccuracy"])
        for item in sme_complete
    ]
    sme_latencies = [
        float(item["sme_shadow"]["latency_ms"]) for item in sme_complete
    ]
    primary_mean = statistics.fmean(primary_accuracy) if primary_accuracy else 0.0
    sme_mean = statistics.fmean(sme_accuracy) if sme_accuracy else 0.0
    evidence_complete = sum(
        item["sme_shadow"]["evidence_completeness"].get("complete") is True
        for item in comparisons
    )
    ledger_linked = sum(
        item["sme_shadow"]["continuity_ledger"].get("status") == "linked"
        for item in comparisons
    )
    refusals = sum(item["sme_shadow"].get("refusal") is not None for item in comparisons)
    criteria = {
        "minimum_25_observations": len(comparisons) >= 25,
        "sme_completion_100_percent": len(sme_complete) == len(comparisons),
        "sme_mean_word_accuracy_at_least_90_percent": sme_mean >= 0.90,
        "sme_mean_accuracy_noninferior_within_2_points": sme_mean >= primary_mean - 0.02,
        "sme_p95_latency_at_most_2500_ms": (_p95(sme_latencies) or float("inf")) <= 2500,
        "evidence_completeness_100_percent": evidence_complete == len(comparisons),
        "continuity_ledger_linked_100_percent": ledger_linked == len(comparisons),
        "refusal_rate_zero": refusals == 0,
    }
    summary = {
        "schema": "jarvis-sme-transcription-promotion-benchmark/1.0",
        "status": "verified" if all(criteria.values()) else "hold",
        "baseline": str(BASELINE_ROOT / "promotion-benchmark.json"),
        "dataset": {
            "kind": "synthetic_piper_clean_speech",
            "observations": len(comparisons),
            "audio_root": str(BASELINE_ROOT / "audio"),
        },
        "primary": {
            "backend": "Systran/faster-whisper-base (v2 fixed baseline)",
            "mean_word_accuracy": round(primary_mean, 6),
        },
        "sme": {
            "backend": BACKEND_LABEL,
            "build_commit": "c122757fddf358397bb7f33b6ac3aab24a5bca04",
            "completed": len(sme_complete),
            "mean_word_accuracy": round(sme_mean, 6),
            "p95_latency_ms": round(_p95(sme_latencies) or 0.0, 3),
            "evidence_complete": evidence_complete,
            "continuity_ledger_linked": ledger_linked,
            "refusals": refusals,
        },
        "criteria": criteria,
        "transcription_backend_promotion_eligible": all(criteria.values()),
        "operator_review_required": True,
        "jarvis_executive_authority_changed": False,
        "comparison_reports": [item["report_path"] for item in comparisons],
        "summary_path": str(SUMMARY_PATH),
    }
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if all(criteria.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
