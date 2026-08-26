"""Frontier multimodal model library for AAIS Jarvis.

Mythic: Model Library
Engineering: FrontierModelLibrary

Catalog of selectable models by modality (chat, image, img2img, voice, music).
Free-tier cloud chat entries feed FreeCloudFailoverRouter; creative entries
document local HF / API targets until adapters are fully wired.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Modality = Literal["chat", "image", "img2img", "voice_stt", "voice_tts", "music"]

LIBRARY_VERSION = "frontier_model_library.v1"


@dataclass(frozen=True, slots=True)
class ModelLibraryEntry:
    """One selectable model in the AAIS library."""

    id: str
    label: str
    modality: Modality
    provider_id: str
    model_id: str
    free_tier: bool = False
    cloud: bool = True
    summary: str = ""
    activation_hint: str = ""
    status: str = "available"  # available | catalog_only | disabled
    tags: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["tags"] = list(self.tags)
        return payload


# Ordered free-cloud chat failover (skip unavailable / just-failed).
FREE_CLOUD_CHAT_FAILOVER_ORDER: tuple[str, ...] = (
    "nvidia",
    "openrouter",
    "groq",
    "google",
    "local",
)


MODEL_LIBRARY: tuple[ModelLibraryEntry, ...] = (
    # --- Chat (free cloud preferred) ---
    ModelLibraryEntry(
        id="chat.nvidia.muse_glimmer",
        label="NVIDIA Muse Glimmer 30B",
        modality="chat",
        provider_id="nvidia",
        model_id="meta/muse-glimmer-30b",
        free_tier=True,
        summary="NVIDIA NIM free credits — strong open multimodal chat brain.",
        activation_hint="Set NVIDIA_API_KEY from build.nvidia.com",
        tags=("free", "nim", "primary"),
    ),
    ModelLibraryEntry(
        id="chat.openrouter.free",
        label="OpenRouter Free Router",
        modality="chat",
        provider_id="openrouter",
        model_id="openrouter/free",
        free_tier=True,
        summary="Hosted free-model pool via OpenRouter.",
        activation_hint="Set OPENROUTER_API_KEY",
        tags=("free", "failover"),
    ),
    ModelLibraryEntry(
        id="chat.groq.llama70b",
        label="Groq Llama 3.3 70B",
        modality="chat",
        provider_id="groq",
        model_id="llama-3.3-70b-versatile",
        free_tier=True,
        summary="Fast free-tier Groq inference for open weights.",
        activation_hint="Set GROQ_API_KEY",
        tags=("free", "fast", "failover"),
    ),
    ModelLibraryEntry(
        id="chat.google.gemini_flash",
        label="Google Gemini Flash",
        modality="chat",
        provider_id="google",
        model_id="gemini-2.0-flash",
        free_tier=True,
        summary="Gemini free-tier OpenAI-compatible endpoint.",
        activation_hint="Set GOOGLE_API_KEY or GEMINI_API_KEY",
        tags=("free", "failover"),
    ),
    ModelLibraryEntry(
        id="chat.local.god_brain",
        label="God Brain Local (GGUF)",
        modality="chat",
        provider_id="god_brain",
        model_id="Qwen2.5-7B-Instruct-Q4_K_M",
        free_tier=True,
        cloud=False,
        summary="Local llama.cpp GGUF — last-resort offline brain.",
        activation_hint="Run scripts/start-god-brain.sh; GOD_BRAIN_LOCAL_API_KEY=local",
        tags=("local", "offline"),
    ),
    ModelLibraryEntry(
        id="chat.local.heroine",
        label="Local Heroine",
        modality="chat",
        provider_id="local",
        model_id="local",
        free_tier=True,
        cloud=False,
        summary="Built-in local AAIS chat adapter.",
        tags=("local", "offline", "fallback"),
    ),
    # --- Image generation ---
    ModelLibraryEntry(
        id="image.local.sd2",
        label="Stable Diffusion 2 (local)",
        modality="image",
        provider_id="local",
        model_id="stabilityai/stable-diffusion-2",
        free_tier=True,
        cloud=False,
        summary="Local Diffusers text-to-image via /api/image/generate.",
        status="available",
        tags=("local", "diffusers"),
    ),
    ModelLibraryEntry(
        id="image.local.sd15",
        label="Stable Diffusion 1.5 (local)",
        modality="image",
        provider_id="local",
        model_id="runwayml/stable-diffusion-v1-5",
        free_tier=True,
        cloud=False,
        summary="Classic SD 1.5 local Diffusers pipeline.",
        status="catalog_only",
        tags=("local", "diffusers"),
    ),
    ModelLibraryEntry(
        id="image.hf.flux_schnell",
        label="FLUX.1 Schnell (HF)",
        modality="image",
        provider_id="huggingface",
        model_id="black-forest-labs/FLUX.1-schnell",
        free_tier=True,
        summary="Fast open image model; wire via HF Inference or local Diffusers.",
        status="catalog_only",
        activation_hint="HF_TOKEN optional for gated downloads",
        tags=("free", "image", "hf"),
    ),
    # --- Image-to-image ---
    ModelLibraryEntry(
        id="img2img.local.sd15",
        label="SD Image-to-Image (local)",
        modality="img2img",
        provider_id="local",
        model_id="runwayml/stable-diffusion-v1-5",
        free_tier=True,
        cloud=False,
        summary="Local img2img Diffusers path via POST /api/image/img2img.",
        status="available",
        tags=("local", "img2img"),
    ),
    ModelLibraryEntry(
        id="img2img.nvidia.cosmos",
        label="NVIDIA Cosmos Transfer (img2img / video)",
        modality="img2img",
        provider_id="nvidia",
        model_id="nvidia/Cosmos-Transfer2.5-2B",
        free_tier=True,
        summary="Open NVIDIA transfer model lineage for image/video conditioning.",
        status="catalog_only",
        activation_hint="NVIDIA_API_KEY or local HF weights",
        tags=("nim", "img2img", "hf"),
    ),
    # --- Voice ---
    ModelLibraryEntry(
        id="voice.stt.whisper_base",
        label="Whisper Base (STT)",
        modality="voice_stt",
        provider_id="local",
        model_id="whisper-base",
        free_tier=True,
        cloud=False,
        summary="Local Whisper transcription via /api/audio/transcribe.",
        status="available",
        tags=("local", "stt"),
    ),
    ModelLibraryEntry(
        id="voice.tts.speecht5",
        label="SpeechT5 TTS",
        modality="voice_tts",
        provider_id="local",
        model_id="microsoft/speecht5_tts",
        free_tier=True,
        cloud=False,
        summary="Local TTS via /api/audio/synthesize.",
        status="available",
        tags=("local", "tts"),
    ),
    # --- Music ---
    ModelLibraryEntry(
        id="music.hf.musicgen_small",
        label="MusicGen Small",
        modality="music",
        provider_id="huggingface",
        model_id="facebook/musicgen-small",
        free_tier=True,
        summary="Open music generation via POST /api/audio/music/generate.",
        status="available",
        tags=("hf", "music"),
    ),
    ModelLibraryEntry(
        id="music.local.beatbox",
        label="Beatbox Adaptive Score",
        modality="music",
        provider_id="local",
        model_id="arrangement_pcm.v1",
        free_tier=True,
        cloud=False,
        summary="Deterministic adaptive score from scene state via Beatbox + Speakers mix.",
        status="available",
        activation_hint="Open /adaptive-music — no API key. Mood/energy/tension drive the arrangement.",
        tags=("local", "beatbox", "speakers", "adaptive"),
    ),
)


def list_library(
    *,
    modality: str | None = None,
    free_only: bool = False,
) -> list[dict[str, Any]]:
    """Return library entries, optionally filtered."""
    wanted = str(modality or "").strip().lower() or None
    rows: list[dict[str, Any]] = []
    for entry in MODEL_LIBRARY:
        if wanted and entry.modality != wanted:
            continue
        if free_only and not entry.free_tier:
            continue
        rows.append(entry.to_dict())
    return rows


def library_snapshot(*, provider_status: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Bounded library + free-chat failover order for operator consoles."""
    status_by_id = {
        str(item.get("id") or "").strip(): item
        for item in (provider_status or [])
        if isinstance(item, dict)
    }
    entries = []
    for entry in MODEL_LIBRARY:
        row = entry.to_dict()
        provider = status_by_id.get(entry.provider_id)
        if provider is not None:
            row["provider_enabled"] = bool(provider.get("enabled"))
            row["provider_model"] = provider.get("model")
            row["activation_hint"] = row["activation_hint"] or provider.get("activation_hint") or ""
        else:
            row["provider_enabled"] = entry.provider_id in {"local", "huggingface"}
        entries.append(row)

    by_modality: dict[str, list[dict[str, Any]]] = {}
    for row in entries:
        by_modality.setdefault(str(row["modality"]), []).append(row)

    return {
        "library_version": LIBRARY_VERSION,
        "free_cloud_chat_failover_order": list(FREE_CLOUD_CHAT_FAILOVER_ORDER),
        "modalities": sorted(by_modality.keys()),
        "counts": {key: len(value) for key, value in sorted(by_modality.items())},
        "entries": entries,
        "by_modality": by_modality,
    }


def free_cloud_chat_provider_ids() -> tuple[str, ...]:
    return FREE_CLOUD_CHAT_FAILOVER_ORDER
