"""Operator Sovereign Sound Loop — scene → score → mix → Mandala → optional Holo.

Mythic: Sovereign Sound Loop
Engineering: SovereignSoundLoopWorkflow

Inputs:
  scene axes (mood/energy/tension/…), optional holo_probe / run_holo_probe
Outputs:
  SovereignSoundLoopResult with compose receipt + mandala plan + optional probe
Constraints:
  guided/operator path only; no autonomous mutation of spatial spaces
Failure modes:
  compose ValueError → rejected with reason; holo probe optional fail-soft
"""

from __future__ import annotations

from typing import Any


def run_sovereign_sound_loop(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run the guided SovereignSoundLoop path in-process (also used by API/UI)."""
    from src.adaptive_music_runtime import compose_and_mix
    from src.mandala_music_synesthesia import derive_visual_adaptation
    from src.spatial_score_couple import apply_spatial_score_couple

    body = apply_spatial_score_couple(dict(payload or {}))
    include_audio = str(body.get("include_audio", "true")).strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    run_holo = str(body.get("run_holo_probe", "false")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    holo_probe = body.get("holo_probe") if isinstance(body.get("holo_probe"), dict) else None
    if run_holo and not holo_probe:
        try:
            from src.holo_runtime_4d_spatial_vision import probe_spatial_vision

            holo_probe = probe_spatial_vision(
                {
                    "space_id": body.get("space_id"),
                    "observer": body.get("observer"),
                    "tick": body.get("tick", 0),
                    "seed_demo": body.get("seed_demo", True),
                    "targets": body.get("targets"),
                }
            )
            body = apply_spatial_score_couple({**body, "holo_probe": holo_probe})
        except Exception as exc:  # noqa: BLE001 — optional probe fail-soft
            holo_probe = {
                "ok": False,
                "error": str(exc),
                "type": "holo_rt4d_spatial_vision",
            }

    composed = compose_and_mix(body, include_audio=include_audio)
    sync_payload = dict(body)
    sync_payload.update(
        {
            "mood": composed.get("mood") or body.get("mood"),
            "bpm": composed.get("bpm") or body.get("bpm"),
            "duration_sec": composed.get("duration_sec") or body.get("duration_sec"),
            "cue_plan": composed.get("cue_plan") or {},
            "mix_sha256": composed.get("mix_sha256") or "",
            "session_id": composed.get("session_id") or "",
            "scene_id": composed.get("scene_id") or "",
        }
    )
    mandala_plan = derive_visual_adaptation(sync_payload)

    return {
        "ok": True,
        "workflow": "sovereign_sound_loop.v1",
        "steps": ("scene_axes", "score", "mix", "mandala_plan", "optional_holo_probe"),
        "compose": composed,
        "mandala_visual_plan": mandala_plan,
        "holo_probe": holo_probe,
        "spatial_score_couple_receipt": body.get("spatial_score_couple_receipt"),
        "console_path": "/adaptive-music?panel=sovereign-sound",
        "holo_console_path": (holo_probe or {}).get("console_path") if isinstance(holo_probe, dict) else None,
    }


__all__ = ["run_sovereign_sound_loop"]
