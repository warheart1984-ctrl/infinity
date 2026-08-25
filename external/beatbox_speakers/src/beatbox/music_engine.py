"""
Beatbox — Music Engine
Core music generation logic preserved from adaptive-music-v4,
adapted to accept SceneState instead of UserState.
No external dependencies required for deterministic output.
MIDI export requires midiutil (optional).
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Optional

from beatbox.contracts import MusicCue, SceneState, ShotSceneState


# ── Music Data ────────────────────────────────────────────────────────────────

CHORD_SETS: dict[str, list[list[str]]] = {
    "calm":    [["C4","E4","G4"], ["A3","C4","E4"], ["F3","A3","C4"], ["G3","B3","D4"]],
    "focused": [["D4","A4","C5"], ["Bb3","D4","F4"], ["F3","A3","C4"], ["C4","E4","G4"]],
    "intense": [["E3","G3","B3"], ["C3","Eb3","G3"], ["D3","F3","A3"], ["B2","D3","F#3"]],
    "happy":   [["C4","G4","A4"], ["F3","A3","C4"], ["G3","B3","D4"], ["E3","G3","C4"]],
}

BASS_ROOTS: dict[str, list[str]] = {
    "calm":    ["C2","A1","F1","G1"],
    "focused": ["D2","Bb1","F1","C2"],
    "intense": ["E1","C1","D1","B0"],
    "happy":   ["C2","F1","G1","E1"],
}

FALLBACK_VOCAL_PATTERNS: dict[str, list[dict[str, Any]]] = {
    "calm":    [{"note":"E4","durationBeats":1,"lyric":"breathe","velocity":0.55},
                {"note":"G4","durationBeats":1,"lyric":"slow","velocity":0.58},
                {"note":"A4","durationBeats":2,"lyric":"tonight","velocity":0.52},
                {"note":"G4","durationBeats":2,"lyric":"glow","velocity":0.5}],
    "focused": [{"note":"D4","durationBeats":1,"lyric":"lock","velocity":0.72},
                {"note":"F4","durationBeats":1,"lyric":"in","velocity":0.7},
                {"note":"A4","durationBeats":1,"lyric":"the","velocity":0.68},
                {"note":"C5","durationBeats":1,"lyric":"frame","velocity":0.74},
                {"note":"A4","durationBeats":2,"lyric":"steady","velocity":0.7}],
    "intense": [{"note":"E4","durationBeats":0.5,"lyric":"push","velocity":0.88},
                {"note":"G4","durationBeats":0.5,"lyric":"the","velocity":0.82},
                {"note":"B4","durationBeats":1,"lyric":"fire","velocity":0.9},
                {"note":"A4","durationBeats":1,"lyric":"higher","velocity":0.86},
                {"note":"G4","durationBeats":1,"lyric":"now","velocity":0.84}],
    "happy":   [{"note":"G4","durationBeats":1,"lyric":"rise","velocity":0.76},
                {"note":"A4","durationBeats":1,"lyric":"up","velocity":0.78},
                {"note":"C5","durationBeats":1,"lyric":"into","velocity":0.74},
                {"note":"A4","durationBeats":1,"lyric":"the","velocity":0.72},
                {"note":"G4","durationBeats":2,"lyric":"light","velocity":0.74}],
}

LYRIC_TEMPLATES: dict[str, list[str]] = {
    "calm":    ["Breathe slow, let the night move softly",
                "Every step turns quiet into light",
                "Hold the line, keep your center glowing"],
    "focused": ["Eyes ahead, every second is a signal",
                "Build the rhythm, lock into the frame",
                "Cut through noise, stay sharp inside the motion"],
    "intense": ["Heart up, fire in the circuit",
                "Push the pulse, break into the ceiling",
                "No delay, turn pressure into power"],
    "happy":   ["Sunrise in the speakers, lift it higher",
                "Bright feet on the floor, catch the feeling",
                "Laugh loud, let the chorus open wide"],
}


# ── Drum Patterns ─────────────────────────────────────────────────────────────

@dataclass
class DrumPattern:
    kick:  list[bool]
    snare: list[bool]
    hat:   list[bool]


def create_drum_pattern(mood: str, energy: float, focus: float, tension: float) -> DrumPattern:
    kick  = [False] * 16
    snare = [False] * 16
    hat   = [False] * 16

    for i in range(16):
        if i % 4 == 0:
            kick[i] = True
        if i in (4, 12):
            snare[i] = True

    if mood == "happy":
        for i in (0, 4, 8, 12, 2, 6, 10, 14):
            hat[i] = True
        if energy > 75:
            kick[10] = True

    elif mood == "focused":
        for i in range(0, 16, 2):
            hat[i] = True
        if focus > 75:
            hat[15] = True

    elif mood == "intense":
        for i in range(16):
            hat[i] = True
        for i in (3, 7, 11, 15):
            kick[i] = True
        if tension > 75 or energy > 80:
            snare[7] = True
            snare[15] = True

    elif mood == "calm":
        for i in (0, 4, 8, 12):
            hat[i] = True
        if tension < 30:
            hat[10] = True

    return DrumPattern(kick=kick, snare=snare, hat=hat)


# ── Arrangement ───────────────────────────────────────────────────────────────

@dataclass
class Arrangement:
    bars: int
    bpm: int
    ppq: int
    ticks_per_16: int
    drum_pattern: DrumPattern
    bass_roots: list[str]
    chords: list[list[str]]
    vocal_notes: list[dict[str, Any]]


def build_arrangement(state: SceneState, vocal_notes: Optional[list[dict[str, Any]]] = None) -> Arrangement:
    mood = state.mood
    bars = max(4, math.ceil(3.0 / (60.0 / max(state.bpm, 1)) / 4))  # ~3s minimum
    return Arrangement(
        bars=bars,
        bpm=state.bpm,
        ppq=480,
        ticks_per_16=120,
        drum_pattern=create_drum_pattern(mood, state.energy, state.focus, state.tension),
        bass_roots=BASS_ROOTS.get(mood, BASS_ROOTS["calm"]),
        chords=CHORD_SETS.get(mood, CHORD_SETS["calm"]),
        vocal_notes=vocal_notes if vocal_notes else FALLBACK_VOCAL_PATTERNS.get(mood, FALLBACK_VOCAL_PATTERNS["calm"]),
    )


def build_lyrics(mood: str, description: str, tone: str) -> list[str]:
    base = LYRIC_TEMPLATES.get(mood, LYRIC_TEMPLATES["calm"])
    return [
        base[0],
        f"Scene: {description[:40]}" if description else base[1],
        base[1],
        f"Tone: {tone.replace('_', ' ')}" if tone else base[2],
        base[2],
        "The score holds what words cannot",
    ]


# ── Cue Builder ───────────────────────────────────────────────────────────────

def build_cue_from_shot(shot_state: ShotSceneState) -> MusicCue:
    ss = shot_state.scene_state
    return MusicCue(
        shot_number=shot_state.shot_number,
        cue_start_seconds=shot_state.cue_start_seconds,
        duration_seconds=shot_state.duration_seconds,
        mood=ss.mood,
        bpm=ss.bpm,
        energy=ss.energy,
        tension=ss.tension,
        valence=ss.valence,
        description=ss.description,
    )


# ── MIDI Export ───────────────────────────────────────────────────────────────

def export_midi_bytes(state: SceneState, vocal_notes: Optional[list[dict[str, Any]]] = None) -> Optional[bytes]:
    """
    Export a MIDI arrangement for a single SceneState.
    Returns None if midiutil is not available.
    """
    try:
        from midiutil import MIDIFile  # type: ignore[import]
    except ImportError:
        return None

    arr = build_arrangement(state, vocal_notes)
    midi = MIDIFile(4)  # 4 tracks: drums, bass, chords, vocals

    for track, name in enumerate(["Drums", "Bass", "Chords", "Vocals"]):
        midi.addTrackName(track, 0, name)
        midi.addTempo(track, 0, arr.bpm)

    # Drums (track 0, channel 9)
    for bar in range(arr.bars):
        bar_start = bar * 4.0  # in beats
        for step in range(16):
            beat = bar_start + step * 0.25
            if arr.drum_pattern.kick[step]:
                midi.addNote(0, 9, 36, beat, 0.25, 115)
            if arr.drum_pattern.snare[step]:
                midi.addNote(0, 9, 38, beat, 0.25, 83)
            if arr.drum_pattern.hat[step]:
                midi.addNote(0, 9, 42, beat, 0.125, 45)

    # Bass (track 1, channel 0)
    for bar in range(arr.bars):
        root_note = arr.bass_roots[bar % len(arr.bass_roots)]
        midi_note = _note_to_midi(root_note)
        midi.addNote(1, 0, midi_note, bar * 4.0, 2.0, 90)

    # Chords (track 2, channel 1)
    for bar in range(arr.bars):
        chord = arr.chords[bar % len(arr.chords)]
        for note in chord:
            midi.addNote(2, 1, _note_to_midi(note), bar * 4.0, 4.0, 58)

    # Vocals (track 3, channel 2)
    cursor = 0.0
    while cursor < arr.bars * 4.0:
        for event in arr.vocal_notes:
            dur = max(0.25, float(event.get("durationBeats", 1)))
            vel = int(max(26, min(127, float(event.get("velocity", 0.7)) * 127)))
            midi.addNote(3, 2, _note_to_midi(event.get("note", "C4")), cursor, dur, vel)
            cursor += dur
            if cursor >= arr.bars * 4.0:
                break

    import io
    buf = io.BytesIO()
    midi.writeFile(buf)
    return buf.getvalue()


_NOTE_NAMES = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
_ENHARMONICS = {"Bb": "A#", "Eb": "D#", "Ab": "G#", "Db": "C#", "Gb": "F#"}
STEM_NAMES = ("kick", "snare", "hat", "bass", "chords", "voice")
DEFAULT_SAMPLE_RATE = 44100


def _note_to_midi(note: str) -> int:
    """Convert note string like 'C4', 'Bb3', 'F#3' to MIDI number."""
    if len(note) >= 2 and note[-1].isdigit():
        octave = int(note[-1])
        name = note[:-1]
    else:
        octave = 4
        name = note
    name = _ENHARMONICS.get(name, name)
    if name not in _NOTE_NAMES:
        return 60  # fallback to middle C
    return (_NOTE_NAMES.index(name)) + (octave + 1) * 12


def _midi_to_freq(midi_note: int) -> float:
    return 440.0 * (2.0 ** ((int(midi_note) - 69) / 12.0))


def _noise(index: int, seed: int) -> float:
    x = (int(seed) * 1103515245 + int(index) * 12345) & 0x7FFFFFFF
    return (x / 0x7FFFFFFF) * 2.0 - 1.0


def _add_decaying_sine(
    buf: list[float],
    start: int,
    length: int,
    freq: float,
    amp: float,
    sample_rate: int,
    decay: float,
) -> None:
    end = min(len(buf), start + length)
    if end <= start or amp == 0:
        return
    two_pi = 2.0 * math.pi * freq / sample_rate
    for i, idx in enumerate(range(start, end)):
        env = math.exp(-decay * i / sample_rate)
        buf[idx] += amp * env * math.sin(two_pi * i)


def _add_held_sine(
    buf: list[float],
    start: int,
    length: int,
    freq: float,
    amp: float,
    sample_rate: int,
) -> None:
    end = min(len(buf), start + length)
    if end <= start or amp == 0:
        return
    fade = min(int(0.01 * sample_rate), max(1, (end - start) // 8))
    two_pi = 2.0 * math.pi * freq / sample_rate
    span = end - start
    for i, idx in enumerate(range(start, end)):
        env = 1.0
        if i < fade:
            env = i / fade
        elif i > span - fade:
            env = max(0.0, (span - i) / fade)
        buf[idx] += amp * env * math.sin(two_pi * i)


def _add_noise_burst(
    buf: list[float],
    start: int,
    length: int,
    amp: float,
    seed: int,
    decay: float,
    sample_rate: int,
) -> None:
    end = min(len(buf), start + length)
    if end <= start or amp == 0:
        return
    for i, idx in enumerate(range(start, end)):
        env = math.exp(-decay * i / sample_rate)
        buf[idx] += amp * env * _noise(idx, seed)


def render_arrangement_pcm(
    arr: Arrangement,
    duration_seconds: float,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    energy: float = 55.0,
) -> dict[str, list[float]]:
    """Render arrangement stems as float PCM. Deterministic; no I/O or network."""
    n = max(1, int(max(0.05, float(duration_seconds)) * sample_rate))
    stems = {name: [0.0] * n for name in STEM_NAMES}
    seconds_per_beat = 60.0 / max(int(arr.bpm), 1)
    step_sec = seconds_per_beat * 0.25
    step_samples = max(1, int(step_sec * sample_rate))
    energy_gain = 0.35 + (max(0.0, min(100.0, float(energy))) / 100.0) * 0.6
    seed = (arr.bpm * 17 + arr.bars * 13 + len(arr.bass_roots) * 7) & 0x7FFFFFFF

    total_steps = int(math.ceil(n / step_samples))
    for step_index in range(total_steps):
        start = step_index * step_samples
        if start >= n:
            break
        pattern_step = step_index % 16
        bar = (step_index // 16) % max(arr.bars, 1)
        if arr.drum_pattern.kick[pattern_step]:
            _add_decaying_sine(
                stems["kick"], start, int(0.12 * sample_rate), 58.0, 0.95 * energy_gain,
                sample_rate, decay=18.0,
            )
        if arr.drum_pattern.snare[pattern_step]:
            _add_noise_burst(
                stems["snare"], start, int(0.14 * sample_rate), 0.55 * energy_gain,
                seed + step_index, decay=22.0, sample_rate=sample_rate,
            )
            _add_decaying_sine(
                stems["snare"], start, int(0.1 * sample_rate), 186.0, 0.28 * energy_gain,
                sample_rate, decay=16.0,
            )
        if arr.drum_pattern.hat[pattern_step]:
            _add_noise_burst(
                stems["hat"], start, int(0.04 * sample_rate), 0.22 * energy_gain,
                seed + 99 + step_index, decay=40.0, sample_rate=sample_rate,
            )

    beat_samples = max(1, int(seconds_per_beat * sample_rate))
    total_beats = int(math.ceil(n / beat_samples))
    for beat in range(total_beats):
        start = beat * beat_samples
        bar = (beat // 4) % max(len(arr.bass_roots), 1)
        if beat % 2 == 0:
            bass_note = arr.bass_roots[bar % len(arr.bass_roots)]
            _add_held_sine(
                stems["bass"], start, beat_samples * 2,
                _midi_to_freq(_note_to_midi(bass_note)), 0.42,
                sample_rate,
            )
        chord = arr.chords[bar % len(arr.chords)]
        if beat % 4 == 0:
            for note in chord:
                _add_held_sine(
                    stems["chords"], start, beat_samples * 4,
                    _midi_to_freq(_note_to_midi(note)), 0.14,
                    sample_rate,
                )

    cursor = 0.0
    while cursor * beat_samples < n:
        for event in arr.vocal_notes:
            dur_beats = max(0.25, float(event.get("durationBeats", 1)))
            start = int(cursor * beat_samples)
            length = int(dur_beats * beat_samples)
            vel = float(event.get("velocity", 0.7))
            _add_held_sine(
                stems["voice"], start, length,
                _midi_to_freq(_note_to_midi(str(event.get("note", "C4")))),
                0.22 * vel,
                sample_rate,
            )
            cursor += dur_beats
            if cursor * beat_samples >= n:
                break
    return stems


def mix_music_stems(stems: dict[str, list[float]]) -> list[float]:
    """Beatbox score mix: drums/bass/chords only. Voice stays a Speakers stem."""
    length = max((len(buf) for buf in stems.values()), default=0)
    mixed = [0.0] * length
    gains = {"kick": 1.0, "snare": 0.85, "hat": 0.45, "bass": 0.9, "chords": 0.7}
    for name, gain in gains.items():
        buf = stems.get(name) or []
        for i, sample in enumerate(buf):
            mixed[i] += sample * gain
    return mixed


def pcm_to_wav_bytes(samples: list[float], sample_rate: int = DEFAULT_SAMPLE_RATE) -> bytes:
    import io
    import wave
    from array import array

    frames = array("h")
    for sample in samples:
        clamped = max(-1.0, min(1.0, sample))
        frames.append(int(clamped * 32767.0))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(int(sample_rate))
        handle.writeframes(frames.tobytes())
    return buffer.getvalue()


def scene_state_from_cue(cue: MusicCue) -> SceneState:
    mood = cue.mood if cue.mood in CHORD_SETS else "calm"
    return SceneState(
        energy=float(cue.energy),
        tension=float(cue.tension),
        focus=60.0,
        valence=float(cue.valence),
        mood=mood,  # type: ignore[arg-type]
        bpm=int(cue.bpm),
        shot_number=int(cue.shot_number),
        description=str(cue.description or ""),
    )


def render_cue_stems(cue: MusicCue, sample_rate: int = DEFAULT_SAMPLE_RATE) -> dict[str, list[float]]:
    state = scene_state_from_cue(cue)
    arrangement = build_arrangement(state)
    return render_arrangement_pcm(
        arrangement,
        cue.duration_seconds,
        sample_rate=sample_rate,
        energy=cue.energy,
    )


def concat_stem_maps(parts: list[dict[str, list[float]]]) -> dict[str, list[float]]:
    combined = {name: [] for name in STEM_NAMES}
    for part in parts:
        for name in STEM_NAMES:
            combined[name].extend(part.get(name) or [])
    return combined
