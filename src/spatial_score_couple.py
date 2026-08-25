"""Map HoloRT4D visibility/occlusion into adaptive compose mood/tension axes.

Mythic: Spatial Score Couple
Engineering: SpatialScoreCoupleLayer

Inputs:
  optional holo_probe / spatial_vision dict, or mood/energy/tension overrides
Outputs:
  payload with mood/energy/tension adjusted from visibility ratio
Constraints:
  additive only; does not run Holo probe itself unless probe dict provided
Failure modes:
  invalid probe shape → leave axes unchanged (fail-open for compose)
"""

from __future__ import annotations

from typing import Any

VALID_MOODS = ("calm", "focused", "intense", "happy")


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def visibility_axes_from_probe(probe: dict[str, Any] | None) -> dict[str, Any]:
    """Derive energy/tension/mood hints from a HoloRT4D probe frame."""
    frame = dict(probe or {})
    visible = int(frame.get("visible_count") or 0)
    occluded = int(frame.get("occluded_count") or 0)
    total = visible + occluded
    if total <= 0:
        return {
            "ok": False,
            "reason": "empty_probe",
            "visibility_ratio": None,
            "occlusion_ratio": None,
        }

    visibility_ratio = visible / total
    occlusion_ratio = occluded / total
    # Occlusion raises tension; open sightlines raise energy/focus calm.
    tension = _clamp(35.0 + (occlusion_ratio * 55.0), 0.0, 100.0)
    energy = _clamp(45.0 + (visibility_ratio * 40.0), 0.0, 100.0)
    if occlusion_ratio >= 0.6:
        mood = "intense"
    elif visibility_ratio >= 0.75:
        mood = "calm"
    elif energy >= 70:
        mood = "happy"
    else:
        mood = "focused"

    return {
        "ok": True,
        "visibility_ratio": round(visibility_ratio, 4),
        "occlusion_ratio": round(occlusion_ratio, 4),
        "visible_count": visible,
        "occluded_count": occluded,
        "mood": mood,
        "energy": round(energy, 2),
        "tension": round(tension, 2),
        "focus": round(_clamp(50.0 + (visibility_ratio * 30.0), 0.0, 100.0), 2),
        "source": "spatial_score_couple.v1",
        "space_id": frame.get("space_id"),
        "tick": frame.get("tick"),
    }


def apply_spatial_score_couple(payload: dict[str, Any] | None) -> dict[str, Any]:
    """
    Merge Holo probe axes into an adaptive compose payload.

    Looks for nested keys: holo_probe, spatial_vision, spatial_score_couple.
    When present, fills mood/energy/tension/focus unless operator already set them
    and couple_mode is 'fill_missing' (default). Use couple_mode='override' to force.
    """
    body = dict(payload or {})
    probe = (
        body.get("holo_probe")
        or body.get("spatial_vision")
        or body.get("spatial_score_couple")
    )
    if not isinstance(probe, dict) or not probe:
        return body

    axes = visibility_axes_from_probe(probe)
    body["spatial_score_couple_receipt"] = axes
    if not axes.get("ok"):
        return body

    couple_mode = str(body.get("couple_mode") or "fill_missing").strip().lower()
    for key in ("mood", "energy", "tension", "focus"):
        if couple_mode == "override" or body.get(key) in (None, "", []):
            body[key] = axes[key]
        elif key == "mood" and str(body.get("mood") or "").strip().lower() not in VALID_MOODS:
            body[key] = axes[key]

    description = str(body.get("description") or "").strip()
    couple_note = (
        f"[SpatialScoreCouple] visibility={axes['visibility_ratio']} "
        f"occlusion={axes['occlusion_ratio']} space={axes.get('space_id')}"
    )
    if couple_note not in description:
        body["description"] = f"{description} {couple_note}".strip() if description else couple_note
    return body


__all__ = [
    "apply_spatial_score_couple",
    "visibility_axes_from_probe",
]
