"""
Beatbox — Score Lane
Fixed timeline renderer for the film pipeline.
Reads ScoreRequest, produces BeatboxArtifact with audio + timeline manifest.
"""
from __future__ import annotations

import json
import logging
import wave
from pathlib import Path
from typing import Optional

from beatbox.adapters.base_adapter import BeatboxAdapter
from beatbox.adapters.deterministic_adapter import DeterministicAdapter
from beatbox.contracts import BeatboxArtifact, MusicCue, ScoreRequest
from beatbox.music_engine import (
    STEM_NAMES,
    concat_stem_maps,
    mix_music_stems,
    pcm_to_wav_bytes,
    render_cue_stems,
    build_cue_from_shot,
)

logger = logging.getLogger(__name__)


class ScoreLane:
    """
    Score mode: reads a ScoreRequest, generates per-shot music cues,
    assembles a timeline manifest, writes a WAV audio file.
    No API key required — deterministic audio is always available.
    """

    def __init__(self, adapter: Optional[BeatboxAdapter] = None) -> None:
        self._adapter = adapter or DeterministicAdapter()

    def score(self, request: ScoreRequest) -> BeatboxArtifact:
        if not request.shots:
            return self._empty_artifact(request)

        cues: list[MusicCue] = []
        all_lyrics: list[str] = []
        total_duration = 0.0

        for shot_state in request.shots:
            cue = build_cue_from_shot(shot_state)
            cues.append(cue)
            total_duration += shot_state.duration_seconds

            # Generate lyrics for this shot via adapter
            lyric_result = self._adapter.execute("generate_lyrics", {
                "mood": shot_state.scene_state.mood,
                "description": shot_state.scene_state.description,
                "tone": request.tone,
                "bpm": shot_state.scene_state.bpm,
            })
            if lyric_result.get("ok") and lyric_result.get("lines"):
                all_lyrics.extend(lyric_result["lines"][:2])  # 2 lines per shot

        # Verify continuity: cue starts must be non-decreasing
        continuity_passed = self._check_continuity(cues)

        # Write outputs
        output_dir = self._resolve_output_dir(request)
        audio_path, stem_paths = self._write_audio(output_dir, request, cues)
        timeline_path = self._write_timeline(output_dir, request, cues, all_lyrics, stem_paths)

        return BeatboxArtifact(
            session_id=request.session_id,
            scene_id=request.scene_id,
            audio_path=str(audio_path),
            timeline_path=str(timeline_path),
            mode="score",
            provider=self._adapter.provider_name,
            continuity_passed=continuity_passed,
            cue_count=len(cues),
            total_duration_seconds=total_duration,
            cues=cues,
        )

    # ── Continuity ────────────────────────────────────────────────────────────

    def _check_continuity(self, cues: list[MusicCue]) -> bool:
        for i in range(1, len(cues)):
            expected = cues[i - 1].cue_start_seconds + cues[i - 1].duration_seconds
            if abs(cues[i].cue_start_seconds - expected) > 0.01:
                logger.warning(
                    "Beatbox continuity: gap at cue %d (expected %.2fs, got %.2fs)",
                    cues[i].shot_number, expected, cues[i].cue_start_seconds,
                )
                return False
        return True

    # ── Audio Writer ──────────────────────────────────────────────────────────

    def _write_audio(
        self, output_dir: Path, request: ScoreRequest, cues: list[MusicCue]
    ) -> tuple[Path, dict[str, str]]:
        """Write arrangement-engine stems plus a music mix (no voice).

        Score truth stays in Beatbox. Voice remains a separate stem for Speakers.
        """
        audio_path = output_dir / f"{request.session_id}_score.wav"
        sample_rate = 44100
        parts = [render_cue_stems(cue, sample_rate=sample_rate) for cue in cues]
        combined = concat_stem_maps(parts)
        music = mix_music_stems(combined)
        audio_path.write_bytes(pcm_to_wav_bytes(music, sample_rate=sample_rate))

        stems_dir = output_dir / "stems"
        stems_dir.mkdir(parents=True, exist_ok=True)
        stem_paths: dict[str, str] = {}
        for name in STEM_NAMES:
            path = stems_dir / f"{name}.wav"
            path.write_bytes(pcm_to_wav_bytes(combined.get(name) or [], sample_rate=sample_rate))
            stem_paths[name] = str(path)
        stem_paths["music"] = str(audio_path)

        logger.info(
            "Beatbox: wrote arrangement mix %s (%.1fs, %d stems)",
            audio_path.name,
            sum(c.duration_seconds for c in cues),
            len(stem_paths),
        )
        return audio_path, stem_paths

    # ── Timeline Writer ───────────────────────────────────────────────────────

    def _write_timeline(
        self,
        output_dir: Path,
        request: ScoreRequest,
        cues: list[MusicCue],
        lyrics: list[str],
        stem_paths: dict[str, str] | None = None,
    ) -> Path:
        timeline_path = output_dir / f"{request.session_id}_timeline.json"
        manifest = {
            "session_id": request.session_id,
            "scene_id": request.scene_id,
            "tone": request.tone,
            "target": request.target,
            "engine": "arrangement_pcm.v1",
            "total_duration_seconds": sum(c.duration_seconds for c in cues),
            "cue_count": len(cues),
            "lyrics_summary": lyrics[:12],
            "stem_paths": dict(stem_paths or {}),
            "cues": [
                {
                    "shot_number": c.shot_number,
                    "cue_start_seconds": round(c.cue_start_seconds, 3),
                    "duration_seconds": round(c.duration_seconds, 3),
                    "mood": c.mood,
                    "bpm": c.bpm,
                    "energy": round(c.energy, 1),
                    "tension": round(c.tension, 1),
                    "valence": round(c.valence, 3),
                    "description": c.description,
                }
                for c in cues
            ],
        }
        timeline_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        logger.info("Beatbox: wrote timeline %s (%d cues)", timeline_path.name, len(cues))
        return timeline_path

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _resolve_output_dir(self, request: ScoreRequest) -> Path:
        if request.output_path:
            p = Path(request.output_path)
        else:
            p = Path(".runtime-beatbox") / request.session_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _empty_artifact(self, request: ScoreRequest) -> BeatboxArtifact:
        output_dir = self._resolve_output_dir(request)
        # Write empty files so downstream Speaker doesn't crash on missing paths
        audio_path = output_dir / f"{request.session_id}_score.wav"
        timeline_path = output_dir / f"{request.session_id}_timeline.json"
        with wave.open(str(audio_path), "w") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(44100)
            wav.writeframes(b"")
        timeline_path.write_text(json.dumps({
            "session_id": request.session_id,
            "scene_id": request.scene_id,
            "cues": [],
            "total_duration_seconds": 0.0,
        }), encoding="utf-8")
        return BeatboxArtifact(
            session_id=request.session_id,
            scene_id=request.scene_id,
            audio_path=str(audio_path),
            timeline_path=str(timeline_path),
            mode="score",
            provider=self._adapter.provider_name,
            continuity_passed=True,
            cue_count=0,
            total_duration_seconds=0.0,
            cues=[],
        )
