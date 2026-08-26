"""Constitutional adaptive audio runtime — Beatbox score + Speakers mix.

Mythic: Sovereign Sound / Adaptive Sonic Organism
Engineering: ConstitutionalAdaptiveAudioRuntime

Inputs: operator/narrative fields (mood, energy, tension, focus, valence, bpm,
        duration, description) or an existing Beatbox score payload
Outputs: AdaptiveMusicResult with mix WAV, stem WAVs, cue plan, lineage metadata
Constraints: deterministic local PCM; no network; Beatbox owns score truth;
             Speakers owns mix/ducking only; bounded duration
Failure modes: invalid mood/input → ValueError (fail closed)
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

VALID_MOODS = ("calm", "focused", "intense", "happy")
MIN_DURATION_SEC = 2.0
MAX_DURATION_SEC = 12.0
DEFAULT_DURATION_SEC = 6.0
ENGINE_VERSION = "arrangement_pcm.v1"


def ensure_beatbox_speakers_src(*, root: Path | None = None) -> Path:
    """Put vendored beatbox_speakers/src on sys.path. Does not import Story Forge."""
    repo = root or Path(__file__).resolve().parents[1]
    src = (repo / "external" / "beatbox_speakers" / "src").resolve()
    if not src.is_dir():
        raise FileNotFoundError(f"beatbox_speakers src missing: {src}")
    text = str(src)
    if text not in sys.path:
        sys.path.insert(0, text)
    return src


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _clamp_duration(value: Any, default: float = DEFAULT_DURATION_SEC) -> float:
    try:
        duration = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("duration_sec must be a number") from exc
    if duration <= 0:
        duration = default
    return max(MIN_DURATION_SEC, min(MAX_DURATION_SEC, duration))


def _clamp_axis(value: Any, default: float, lo: float, hi: float) -> float:
    if value is None or value == "":
        return default
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError) as exc:
        raise ValueError("scene axis values must be numbers") from exc


def _wav_b64(path: str | Path | None) -> str:
    if not path:
        return ""
    file_path = Path(path)
    if not file_path.is_file():
        return ""
    return base64.b64encode(file_path.read_bytes()).decode("ascii")


def _sha256_file(path: str | Path | None) -> str:
    if not path:
        return ""
    file_path = Path(path)
    if not file_path.is_file():
        return ""
    digest = hashlib.sha256()
    digest.update(file_path.read_bytes())
    return digest.hexdigest()


def _read_timeline(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    file_path = Path(path)
    if not file_path.is_file():
        return {}
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _record_lineage(payload: dict[str, Any]) -> None:
    try:
        from src.ul_lineage import record_lineage_event

        record_lineage_event(
            node_type="capability_call",
            cisiv_stage="implementation",
            claim_label="asserted",
            source_module="src.adaptive_music_runtime",
            payload=payload,
        )
    except Exception:
        pass


def _load_voice_constraints(body: dict[str, Any]) -> dict[str, Any] | None:
    """Load admitted HumanVoice → Speakers constraints when profile_id / path given."""
    inline = body.get("voice_constraints")
    if isinstance(inline, dict) and inline.get("profile_id"):
        return dict(inline)
    path_raw = str(body.get("constraints_path") or body.get("voice_constraints_path") or "").strip()
    profile_id = str(body.get("profile_id") or body.get("voice_profile_id") or "").strip()
    try:
        from src.human_voice_extraction import speakers_constraint_path

        path = Path(path_raw) if path_raw else (
            speakers_constraint_path(profile_id) if profile_id else None
        )
    except Exception:
        path = Path(path_raw) if path_raw else None
    if path is None or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


@dataclass(frozen=True)
class AdaptiveMusicResult:
    """Playable score + mix for operator consoles."""

    ok: bool
    session_id: str
    scene_id: str
    mood: str
    bpm: int
    duration_sec: float
    engine: str
    music_stem_path: str
    voice_stem_path: str
    mix_path: str
    stem_paths: dict[str, str]
    cue_plan: dict[str, Any]
    mix_sha256: str
    audio_b64: str
    stems_b64: dict[str, str]
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "session_id": self.session_id,
            "scene_id": self.scene_id,
            "mood": self.mood,
            "bpm": self.bpm,
            "duration_sec": self.duration_sec,
            "engine": self.engine,
            "music_stem_path": self.music_stem_path,
            "voice_stem_path": self.voice_stem_path,
            "mix_path": self.mix_path,
            "stem_paths": dict(self.stem_paths),
            "cue_plan": dict(self.cue_plan),
            "mix_sha256": self.mix_sha256,
            "audio": self.audio_b64,
            "format": "wav",
            "stems": dict(self.stems_b64),
            "message": self.message,
            "narrative_owned_by": "story_forge",
            "score_owned_by": "beatbox",
            "mix_owned_by": "speakers",
        }


class ConstitutionalAdaptiveAudioRuntime:
    """Compose Beatbox score, then Speakers mix. Replayable local PCM only."""

    def __init__(self, *, root: Path | None = None, output_root: Path | None = None) -> None:
        self.root = (root or _repo_root()).resolve()
        self.output_root = (output_root or (self.root / ".runtime" / "adaptive-music")).resolve()
        ensure_beatbox_speakers_src(root=self.root)

    def compose_score(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Build a ScoreRequest from operator/narrative fields and render stems."""
        request = self._build_score_request(payload or {})
        from beatbox.lanes.beatbox_lane import BeatboxLane

        result = BeatboxLane.from_env().score(request)
        if not result.ok or result.data is None:
            raise ValueError(result.message or "Beatbox score lane failed")
        artifact = result.data
        timeline = _read_timeline(artifact.timeline_path)
        stem_paths = dict(timeline.get("stem_paths") or {})
        if artifact.audio_path:
            stem_paths.setdefault("music", artifact.audio_path)
        cue_plan = {
            "engine": ENGINE_VERSION,
            "status": "rendered",
            "session_id": artifact.session_id,
            "scene_id": artifact.scene_id,
            "continuity_passed": bool(artifact.continuity_passed),
            "cue_count": int(artifact.cue_count),
            "total_duration_seconds": float(artifact.total_duration_seconds),
            "cues": timeline.get("cues") or [],
            "lyrics_summary": timeline.get("lyrics_summary") or [],
        }
        packed = {
            "session_id": artifact.session_id,
            "scene_id": artifact.scene_id,
            "mood": request.shots[0].scene_state.mood if request.shots else "calm",
            "bpm": request.shots[0].scene_state.bpm if request.shots else 90,
            "duration_sec": float(artifact.total_duration_seconds),
            "music_stem_path": stem_paths.get("music") or artifact.audio_path,
            "voice_stem_path": stem_paths.get("voice") or "",
            "stem_paths": stem_paths,
            "cue_plan": cue_plan,
            "timeline_path": artifact.timeline_path,
        }
        _record_lineage(
            {
                "capability": "beatbox_score",
                "engine": ENGINE_VERSION,
                "session_id": packed["session_id"],
                "mood": packed["mood"],
                "bpm": packed["bpm"],
                "duration_sec": packed["duration_sec"],
                "music_sha256": _sha256_file(packed["music_stem_path"]),
            }
        )
        return packed

    def mix_stems(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Duck music under the voice stem. Does not invent score."""
        body = dict(payload or {})
        score = body.get("score") if isinstance(body.get("score"), dict) else body
        music_path = str(score.get("music_stem_path") or body.get("music_stem_path") or "").strip()
        voice_path = str(score.get("voice_stem_path") or body.get("voice_stem_path") or "").strip()
        if not music_path or not Path(music_path).is_file():
            raise ValueError("music_stem_path is required and must exist")
        session_id = str(score.get("session_id") or body.get("session_id") or uuid.uuid4().hex[:12])
        scene_id = str(score.get("scene_id") or body.get("scene_id") or "operator")
        duration_sec = float(score.get("duration_sec") or 0.0)

        voice_constraints = _load_voice_constraints(body)
        duck_amount_db = 8.0
        voice_lufs = -16.0
        if voice_constraints:
            # Soft bias from admitted HumanVoice traits (fail-soft numeric clamps).
            traits = {str(t).strip().lower() for t in (voice_constraints.get("traits") or [])}
            if "soft" in traits or "intimate" in traits:
                duck_amount_db = 10.0
                voice_lufs = -15.0
            elif "projected" in traits or "loud" in traits:
                duck_amount_db = 6.0
                voice_lufs = -17.0

        from speakers.contracts import (
            BusConfig,
            DuckingRule,
            RenderTarget,
            SpeakersMixPlan,
            StemEntry,
        )
        from speakers.mix_lane import render_final_mix_from_plan

        mix_plan = SpeakersMixPlan(
            session_id=session_id,
            story_id=scene_id,
            run_id=session_id,
            mix_version="speakers_mix.v1",
            scene_id=scene_id,
            buses={
                "music": BusConfig(target_lufs=-18.0, peak_ceiling_db=-1.0),
                "voice": BusConfig(target_lufs=voice_lufs, peak_ceiling_db=-1.0),
            },
            ducking_rules=[
                DuckingRule(
                    rule_id="duck_music_under_voice",
                    when_source="voice",
                    affects="music",
                    duck_amount_db=duck_amount_db,
                    attack_ms=20,
                    release_ms=80,
                )
            ],
            render_targets=[
                RenderTarget(
                    target_id="wav_master",
                    format="wav",
                    sample_rate=44100,
                    bit_depth=16,
                    channels=1,
                    filename_pattern="{story_id}_{run_id}_final_mix.wav",
                )
            ],
            music_stem=StemEntry(
                stem_type="music",
                file_path=music_path,
                duration_seconds=duration_sec,
                provider="beatbox",
            ),
            voice_stem=StemEntry(
                stem_type="voice",
                file_path=voice_path,
                duration_seconds=duration_sec,
                provider="beatbox_guide",
            )
            if voice_path and Path(voice_path).is_file()
            else None,
            total_duration_seconds=duration_sec,
            continuity_passed=True,
        )
        mix_path = render_final_mix_from_plan(mix_plan, str(self.output_root))
        mix_sha = _sha256_file(mix_path)
        _record_lineage(
            {
                "capability": "speakers_mix",
                "engine": ENGINE_VERSION,
                "session_id": session_id,
                "mix_sha256": mix_sha,
                "music_stem_path": music_path,
                "voice_profile_id": (voice_constraints or {}).get("profile_id"),
            }
        )
        packed = {
            "session_id": session_id,
            "scene_id": scene_id,
            "mix_path": mix_path,
            "mix_sha256": mix_sha,
            "music_stem_path": music_path,
            "voice_stem_path": voice_path,
            "duration_sec": duration_sec,
            "mix_plan": mix_plan.to_payload(),
        }
        if voice_constraints:
            packed["voice_constraints"] = voice_constraints
            packed["voice_profile_id"] = voice_constraints.get("profile_id")
        return packed

    def adapt_live_state(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Map live/game signals into SceneState without owning narrative truth."""
        body = dict(payload or {})
        ensure_beatbox_speakers_src(root=self.root)
        from beatbox.contracts import LiveStateUpdate
        from beatbox.lanes.beatbox_lane import BeatboxLane

        update = LiveStateUpdate(
            game_state=dict(body.get("game_state") or {"session_id": "live", "scene_id": "live"}),
            scene_emotion=str(body.get("scene_emotion") or body.get("description") or "neutral"),
            player_input_energy=_clamp_axis(body.get("energy"), 50.0, 0.0, 100.0),
            player_input_stress=_clamp_axis(body.get("tension"), 35.0, 0.0, 100.0),
            player_input_focus=_clamp_axis(body.get("focus"), 60.0, 0.0, 100.0),
            intensity=_clamp_axis(body.get("intensity") or body.get("energy"), 50.0, 0.0, 100.0),
        )
        live = BeatboxLane.from_env().live_state(update)
        if not live.ok or live.data is None:
            raise ValueError(live.message or "Beatbox live lane failed")
        payload_out = dict(getattr(live.data, "live_payload", {}) or {})
        scene = payload_out.get("scene_state") or {}
        return {
            "ok": True,
            "mode": "live",
            "scene_state": scene,
            "live_payload": payload_out,
        }

    def compose_and_mix(self, payload: dict[str, Any] | None = None, *, include_audio: bool = True) -> AdaptiveMusicResult:
        body = dict(payload or {})
        scored = self.compose_score(body)
        mixed = self.mix_stems(scored)
        stem_paths = dict(scored.get("stem_paths") or {})
        mix_path = str(mixed.get("mix_path") or "")
        stems_b64 = {}
        if include_audio:
            for name, path in stem_paths.items():
                encoded = _wav_b64(path)
                if encoded:
                    stems_b64[name] = encoded
            if mix_path:
                stems_b64["mix"] = _wav_b64(mix_path)
        return AdaptiveMusicResult(
            ok=True,
            session_id=str(scored.get("session_id") or ""),
            scene_id=str(scored.get("scene_id") or ""),
            mood=str(scored.get("mood") or ""),
            bpm=int(scored.get("bpm") or 0),
            duration_sec=float(scored.get("duration_sec") or 0.0),
            engine=ENGINE_VERSION,
            music_stem_path=str(scored.get("music_stem_path") or ""),
            voice_stem_path=str(scored.get("voice_stem_path") or ""),
            mix_path=mix_path,
            stem_paths=stem_paths,
            cue_plan=dict(scored.get("cue_plan") or {}),
            mix_sha256=str(mixed.get("mix_sha256") or ""),
            audio_b64=stems_b64.get("mix") or _wav_b64(mix_path) if include_audio else "",
            stems_b64=stems_b64,
        )

    def _build_score_request(self, payload: dict[str, Any]):
        from beatbox.contracts import SceneState, ScoreRequest, ShotSceneState

        mood = str(payload.get("mood") or "focused").strip().lower()
        if mood not in VALID_MOODS:
            raise ValueError(f"invalid mood: {mood!r}; expected one of {VALID_MOODS}")
        duration = _clamp_duration(payload.get("duration_sec"), DEFAULT_DURATION_SEC)
        energy = _clamp_axis(payload.get("energy"), 62.0, 0.0, 100.0)
        tension = _clamp_axis(payload.get("tension"), 40.0, 0.0, 100.0)
        focus = _clamp_axis(payload.get("focus"), 60.0, 0.0, 100.0)
        valence = _clamp_axis(payload.get("valence"), 0.5, 0.0, 1.0)
        try:
            bpm = int(payload.get("bpm") or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError("bpm must be an integer") from exc
        if bpm <= 0:
            from beatbox.scene_state_builder import _derive_bpm

            bpm = _derive_bpm(energy, focus, tension, valence)
        bpm = max(70, min(175, bpm))
        session_id = str(payload.get("session_id") or uuid.uuid4().hex[:12])
        scene_id = str(payload.get("scene_id") or "operator")
        description = str(payload.get("description") or payload.get("narrative_state") or "").strip()
        output_dir = self.output_root / session_id
        output_dir.mkdir(parents=True, exist_ok=True)
        state = SceneState(
            energy=energy,
            tension=tension,
            focus=focus,
            valence=valence,
            mood=mood,  # type: ignore[arg-type]
            bpm=bpm,
            shot_number=1,
            description=description,
            intent=str(payload.get("intent") or "operator_score"),
        )
        return ScoreRequest(
            session_id=session_id,
            scene_id=scene_id,
            shots=[
                ShotSceneState(
                    shot_number=1,
                    scene_state=state,
                    duration_seconds=duration,
                    cue_start_seconds=0.0,
                )
            ],
            tone=str(payload.get("tone") or "operator"),
            target="movie",
            output_path=str(output_dir),
        )


def compose_score(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return ConstitutionalAdaptiveAudioRuntime().compose_score(payload)


def mix_stems(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return ConstitutionalAdaptiveAudioRuntime().mix_stems(payload)


def adapt_live_state(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return ConstitutionalAdaptiveAudioRuntime().adapt_live_state(payload)


def compose_and_mix(payload: dict[str, Any] | None = None, *, include_audio: bool = True) -> dict[str, Any]:
    return ConstitutionalAdaptiveAudioRuntime().compose_and_mix(payload, include_audio=include_audio).to_dict()
