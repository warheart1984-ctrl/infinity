"""Mandala + Music synesthesia — score cues to visual adaptation hooks.

Mythic: Mandala + Music / synesthetic governance
Engineering: MandalaVisualAdaptationLayer

Inputs: adaptive-music cue plan and/or scene mix metadata
        (mood, bpm, energy, tension, valence, focus, cue_count, mix_sha256)
Outputs: MandalaVisualAdaptationPlan (deterministic, replayable)
Constraints: read-only mapping; no renderer mutation; no random; no new organ stems
Failure modes: missing/invalid axes → reject with reason_code; unknown mood → fail closed
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

PLAN_VERSION = "mandala_visual_adaptation.v1"
ADAPTER_VERSION = "mandala_music_synesthesia.v1"
VALID_MOODS = ("calm", "focused", "intense", "happy")

# Mood → base hue (deg) and Story Forge-aligned lighting profile labels.
# Consumers: Story Forge style.lighting / camera_motion / movement_energy;
# ImxpMandalaAdapter remains governance-only (mandala-link packets).
MOOD_LIGHTING: dict[str, dict[str, Any]] = {
    "calm": {
        "hue_deg": 210.0,
        "temperature": "cool",
        "lighting_profile": "soft_ambient_key",
        "camera_motion": "slow cinematic drift",
        "movement_energy": "measured",
    },
    "focused": {
        "hue_deg": 195.0,
        "temperature": "neutral",
        "lighting_profile": "clear_practical_key",
        "camera_motion": "restrained push",
        "movement_energy": "measured",
    },
    "intense": {
        "hue_deg": 15.0,
        "temperature": "warm",
        "lighting_profile": "high_contrast_edge",
        "camera_motion": "handheld pulse",
        "movement_energy": "urgent",
    },
    "happy": {
        "hue_deg": 48.0,
        "temperature": "warm",
        "lighting_profile": "bright_open_key",
        "camera_motion": "gentle orbit",
        "movement_energy": "buoyant",
    },
}


def _clamp(value: Any, default: float, lo: float, hi: float) -> float:
    if value is None or value == "":
        return default
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError) as exc:
        raise ValueError("scene axis values must be numbers") from exc


def _round(value: float, digits: int = 4) -> float:
    return round(float(value), digits)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _plan_id(fingerprint: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(fingerprint).encode("utf-8")).hexdigest()
    return f"mvap_{digest[:16]}"


@dataclass(frozen=True)
class MandalaVisualAdaptationPlan:
    """Deterministic visual hooks derived from adaptive score metadata."""

    plan_version: str
    adapter_version: str
    plan_id: str
    ok: bool
    mood: str
    bpm: int
    lighting: dict[str, Any]
    camera: dict[str, Any]
    glyph_particle: dict[str, Any]
    renderer_hooks: dict[str, Any]
    source: dict[str, Any]
    consumer_seam: dict[str, Any]
    claim_label: str = "asserted"
    reason_code: str = ""
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "plan_version": self.plan_version,
            "adapter_version": self.adapter_version,
            "plan_id": self.plan_id,
            "mood": self.mood,
            "bpm": self.bpm,
            "lighting": dict(self.lighting),
            "camera": dict(self.camera),
            "glyph_particle": dict(self.glyph_particle),
            "renderer_hooks": dict(self.renderer_hooks),
            "source": dict(self.source),
            "consumer_seam": dict(self.consumer_seam),
            "claim_label": self.claim_label,
            "reason_code": self.reason_code,
            "message": self.message,
        }


class MandalaVisualAdaptationLayer:
    """Map Beatbox/Speakers score metadata into Mandala-consumable visual hooks."""

    def derive_visual_adaptation(self, payload: dict[str, Any] | None = None) -> MandalaVisualAdaptationPlan:
        """Build a MandalaVisualAdaptationPlan from cue plan / mix metadata.

        Accepts either a flat scene payload or an AdaptiveMusicResult-shaped dict
        (with nested cue_plan). Does not render pixels or mutate Mandala state.
        """
        body = dict(payload or {})
        cue_plan = body.get("cue_plan") if isinstance(body.get("cue_plan"), dict) else {}
        scene = body.get("scene_state") if isinstance(body.get("scene_state"), dict) else {}

        mood = str(
            body.get("mood")
            or cue_plan.get("mood")
            or scene.get("mood")
            or "focused"
        ).strip().lower()
        if mood not in VALID_MOODS:
            raise ValueError(f"invalid mood: {mood!r}; expected one of {VALID_MOODS}")

        energy = _clamp(body.get("energy", scene.get("energy")), 62.0, 0.0, 100.0)
        tension = _clamp(body.get("tension", scene.get("tension")), 40.0, 0.0, 100.0)
        focus = _clamp(body.get("focus", scene.get("focus")), 60.0, 0.0, 100.0)
        valence = _clamp(body.get("valence", scene.get("valence")), 0.5, 0.0, 1.0)

        try:
            bpm = int(body.get("bpm") or scene.get("bpm") or cue_plan.get("bpm") or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError("bpm must be an integer") from exc
        if bpm <= 0:
            # Mirror Beatbox defaults when BPM is omitted (deterministic).
            bpm = int(round(70 + (energy * 0.55) + (tension * 0.25) - (focus * 0.05)))
        bpm = max(70, min(175, bpm))

        cue_count = 0
        for candidate in (
            body.get("cue_count"),
            cue_plan.get("cue_count"),
            len(cue_plan.get("cues") or []) if isinstance(cue_plan.get("cues"), list) else 0,
        ):
            try:
                cue_count = max(cue_count, int(candidate or 0))
            except (TypeError, ValueError):
                continue

        duration_sec = _clamp(
            body.get("duration_sec")
            or cue_plan.get("total_duration_seconds")
            or body.get("total_duration_seconds"),
            6.0,
            0.5,
            120.0,
        )
        mix_sha256 = str(body.get("mix_sha256") or "").strip()
        session_id = str(body.get("session_id") or cue_plan.get("session_id") or "")
        scene_id = str(body.get("scene_id") or cue_plan.get("scene_id") or "")

        mood_meta = MOOD_LIGHTING[mood]
        energy_n = energy / 100.0
        tension_n = tension / 100.0
        focus_n = focus / 100.0

        # Lighting: intensity from energy; hue from mood + valence tilt.
        hue_deg = (float(mood_meta["hue_deg"]) + ((valence - 0.5) * 36.0)) % 360.0
        lighting_intensity = _round(0.28 + (energy_n * 0.62) + (tension_n * 0.1), 4)
        lighting = {
            "intensity": lighting_intensity,
            "hue_deg": _round(hue_deg, 2),
            "temperature": mood_meta["temperature"],
            "profile": mood_meta["lighting_profile"],
        }

        # Camera / motion pulse from BPM + tension amplitude.
        pulse_hz = _round(bpm / 60.0, 4)
        beat_period_ms = int(round(60000.0 / float(bpm)))
        motion_amplitude = _round(0.18 + (tension_n * 0.55) + (energy_n * 0.2), 4)
        camera = {
            "pulse_hz": pulse_hz,
            "beat_period_ms": beat_period_ms,
            "motion_amplitude": motion_amplitude,
            "motion_profile": mood_meta["camera_motion"],
            "movement_energy": mood_meta["movement_energy"],
        }

        # Glyph / particle energy from tension + valence (sparkle favors high valence).
        particle_energy = _round(0.2 + (tension_n * 0.55) + (energy_n * 0.2), 4)
        density = _round(0.15 + (energy_n * 0.45) + (cue_count * 0.01), 4)
        density = min(1.0, density)
        sparkle = _round(0.1 + (valence * 0.7) + ((1.0 - tension_n) * 0.1), 4)
        glyph_particle = {
            "energy": particle_energy,
            "density": density,
            "sparkle": min(1.0, sparkle),
            "valence_bias": _round((valence * 2.0) - 1.0, 4),
            "focus_lock": _round(focus_n, 4),
        }

        renderer_hooks = {
            "lighting_intensity": lighting["intensity"],
            "lighting_hue_deg": lighting["hue_deg"],
            "lighting_temperature": lighting["temperature"],
            "lighting_profile": lighting["profile"],
            "camera_pulse_hz": camera["pulse_hz"],
            "camera_beat_period_ms": camera["beat_period_ms"],
            "camera_motion_amplitude": camera["motion_amplitude"],
            "camera_motion": camera["motion_profile"],
            "movement_energy": camera["movement_energy"],
            "particle_energy": glyph_particle["energy"],
            "particle_density": glyph_particle["density"],
            "glyph_sparkle": glyph_particle["sparkle"],
            "glyph_valence_bias": glyph_particle["valence_bias"],
        }

        source = {
            "mood": mood,
            "bpm": bpm,
            "energy": _round(energy, 4),
            "tension": _round(tension, 4),
            "focus": _round(focus, 4),
            "valence": _round(valence, 4),
            "cue_count": cue_count,
            "duration_sec": _round(duration_sec, 4),
            "session_id": session_id,
            "scene_id": scene_id,
            "mix_sha256": mix_sha256,
            "cue_plan_status": str(cue_plan.get("status") or ""),
        }
        fingerprint = {
            "plan_version": PLAN_VERSION,
            "mood": mood,
            "bpm": bpm,
            "energy": source["energy"],
            "tension": source["tension"],
            "focus": source["focus"],
            "valence": source["valence"],
            "cue_count": cue_count,
            "duration_sec": source["duration_sec"],
        }
        plan_id = _plan_id(fingerprint)

        consumer_seam = {
            "status": "plan_only",
            "owns_pixels": False,
            "existing_surfaces": [
                "external/story_forge/.../visual_generation_backend.py (style.lighting, movement_energy)",
                "external/story_forge/.../render_manager.py (camera_motion, particles)",
                "src/imxp_mandala_adapter.py (governance membrane only — not a visual engine)",
            ],
            "apply_hint": (
                "Pass renderer_hooks into Mandala/Story Forge style + camera fields; "
                "do not invent a second film renderer here."
            ),
        }

        return MandalaVisualAdaptationPlan(
            plan_version=PLAN_VERSION,
            adapter_version=ADAPTER_VERSION,
            plan_id=plan_id,
            ok=True,
            mood=mood,
            bpm=bpm,
            lighting=lighting,
            camera=camera,
            glyph_particle=glyph_particle,
            renderer_hooks=renderer_hooks,
            source=source,
            consumer_seam=consumer_seam,
            message="Mandala visual adaptation derived from adaptive score metadata",
        )

    def plan_from_cue_plan(
        self,
        cue_plan: dict[str, Any] | None = None,
        *,
        scene: dict[str, Any] | None = None,
    ) -> MandalaVisualAdaptationPlan:
        """Convenience: cue plan + optional scene axes → adaptation plan."""
        payload = dict(scene or {})
        payload["cue_plan"] = dict(cue_plan or {})
        return self.derive_visual_adaptation(payload)


def derive_visual_adaptation(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Module helper: MandalaVisualAdaptationPlan as a dict."""
    return MandalaVisualAdaptationLayer().derive_visual_adaptation(payload).to_dict()


def plan_from_cue_plan(
    cue_plan: dict[str, Any] | None = None,
    *,
    scene: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return MandalaVisualAdaptationLayer().plan_from_cue_plan(cue_plan, scene=scene).to_dict()


mandala_visual_adaptation_layer = MandalaVisualAdaptationLayer()
