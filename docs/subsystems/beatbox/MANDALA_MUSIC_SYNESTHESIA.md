# Mandala + Music Synesthesia (MVP)

Mythic: Mandala + Music / synesthetic governance  
Engineering: `MandalaVisualAdaptationLayer` (`src/mandala_music_synesthesia.py`)

## Status

Plan-only sync seam. There is **no** in-repo Mandala film/particle engine to drive
directly. This pass produces a deterministic `MandalaVisualAdaptationPlan` that
existing visual surfaces can consume later.

## Ownership

| Layer | Owns |
| --- | --- |
| Beatbox / `ConstitutionalAdaptiveAudioRuntime` | Score cues, stems, mix metadata |
| `MandalaVisualAdaptationLayer` | Score → visual hook mapping (read-only) |
| Story Forge render path | Actual lighting / camera / particles when applied |
| `ImxpMandalaAdapter` | Governance membrane for mandala-link packets (not pixels) |

## Contract

Schema: `schemas/mandala_visual_adaptation.v1.json`  
Version: `mandala_visual_adaptation.v1`

Hooks (flat `renderer_hooks`):

- lighting intensity / hue / temperature / profile ← energy + mood + valence
- camera pulse Hz / beat period / motion amplitude ← BPM + tension
- particle / glyph energy / density / sparkle ← tension + valence + cue count

Same score axes → same `plan_id` and fields (no randomness).

## APIs

- `POST /api/jarvis/adaptive-music/mandala-sync` — derive plan from scene axes and/or `cue_plan`
- `POST /api/jarvis/adaptive-music/compose` — when successful, response may include
  `mandala_visual_plan` (additive; compose still owned by adaptive audio runtime)

## UI

`/adaptive-music` shows the plan readout after compose (hook values only; no pixel preview).

## Deferred

- Live Mandala canvas / glyph shader binding
- Frame-accurate cue timeline scrubbing for visuals
- Writing hooks into Story Forge `RenderIntent` automatically
- IMXP mandala-link packet emission for visual grants
