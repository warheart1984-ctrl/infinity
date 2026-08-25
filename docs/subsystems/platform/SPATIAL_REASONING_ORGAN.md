# Spatial Reasoning Organ

Status: **governed** (Alt-14 summon wave `alt14-summon-wave-2026-06`; promoted v1.10.0)

## Runtime

- Module: `src/spatial_reasoning_organ.py`
- API: `GET /api/jarvis/spatial-reasoning/status`
- Gate: `make spatial-reasoning-organ-gate`

## Seam: HoloRT4D Spatial Vision

Mythic **HoloRT4D** maps to engineering `HoloRuntime4dSpatialVisionEngine`
(`src/holo_runtime_4d_spatial_vision.py`).

- Capability: `holo_rt4d` / tool `holo_rt4d_spatial_vision` / action `probe`
- Bridge: `POST /api/jarvis/capability-bridge/execute`
- Probe API: `POST /api/jarvis/holo-rt4d-spatial-vision/probe` (includes map layout + view_model)
- Status: `GET /api/jarvis/holo-rt4d-spatial-vision/status`
- Operator surface: `/holo-rt4d` (alias `/spatial-vision`)
- Adapter: `src/capabilities/holo_rt4d_spatial_vision.py`

Shares the Jarvis `SpatialReasoningPlug` when present; otherwise seeds a
deterministic demo space for governed probes.

## Proof

[SPATIAL_REASONING_ORGAN_V1_PROOF.md](../../proof/platform/SPATIAL_REASONING_ORGAN_V1_PROOF.md)
