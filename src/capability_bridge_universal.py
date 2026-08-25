"""Register universal gap-path adapters on CapabilityServiceBridge."""

from __future__ import annotations

from typing import Any

from src.capabilities.action_lane import ACTION_LANE_COMPONENT_ID, ActionLaneCapability
from src.capabilities.adaptive_music_compose import (
    ADAPTIVE_MUSIC_COMPOSE_COMPONENT_ID,
    ADAPTIVE_MUSIC_COMPOSE_INPUT_FIELDS,
    AdaptiveMusicComposeCapability,
)
from src.capabilities.beatbox_score import BEATBOX_LANE_COMPONENT_ID, BeatboxScoreCapability
from src.capabilities.document_vision import DOCUMENT_VISION_COMPONENT_ID, DocumentVisionCapability
from src.capabilities.forge_lane import FORGE_LANE_COMPONENT_ID, ForgeLaneCapability
from src.capabilities.holo_rt4d_spatial_vision import (
    HOLO_RT4D_INPUT_FIELDS,
    HOLO_RT4D_SPATIAL_VISION_COMPONENT_ID,
    HoloRt4dSpatialVisionCapability,
)
from src.capabilities.human_voice_speakers_pipeline import (
    HUMAN_VOICE_SPEAKERS_PIPELINE_COMPONENT_ID,
    HUMAN_VOICE_SPEAKERS_PIPELINE_INPUT_FIELDS,
    HumanVoiceSpeakersPipelineCapability,
)
from src.capabilities.mandala_visual_sync import (
    MANDALA_VISUAL_SYNC_COMPONENT_ID,
    MANDALA_VISUAL_SYNC_INPUT_FIELDS,
    MandalaVisualSyncCapability,
)
from src.capabilities.media_processor import (
    MEDIA_PROCESSOR_COMPONENT_ID,
    AudioAnalyzeCapability,
    ImageTransformCapability,
    VideoAnalyzeCapability,
)
from src.capabilities.memory_lane import MEMORY_LANE_COMPONENT_ID, MemoryLaneCapability
from src.capabilities.speakers_mix import SPEAKERS_LANE_COMPONENT_ID, SpeakersMixCapability
from src.capabilities.story_forge_audio import STORY_FORGE_AUDIO_CAPABILITY_COMPONENT_ID
from src.capabilities.ui_vision import UI_VISION_COMPONENT_ID, UiVisionCapability
from src.capabilities.workspace_lane import WORKSPACE_LANE_COMPONENT_ID, WorkspaceLaneCapability
from src.capability_service_bridge import DEFAULT_GOVERNANCE_MODES, CapabilityServiceBridge
from src.constitutional_task_bus.capability import TaskBusCapability
from src.forge_client import forge_client
from src.evolve_client import evolve_client


def _normalize_name(value: str | None) -> str:
    return " ".join(str(value or "").replace("-", "_").split()).strip().lower()


def attach_universal_gap_adapters(
    bridge: CapabilityServiceBridge,
    *,
    memory_enforcer: Any,
    workspace_tools: Any,
    profile_detector: Any,
    governance_layer: Any,
    patchforge: Any,
    spatial_plug: Any = None,
) -> None:
    """Extend bridge routes for memory/workspace/action/forge and media/story lanes."""
    if getattr(bridge, "_universal_adapters_attached", False):
        return

    bridge._memory_lane_module = MemoryLaneCapability(memory_enforcer=memory_enforcer)
    bridge._workspace_lane_module = WorkspaceLaneCapability(
        workspace_tools=workspace_tools,
        profile_detector=profile_detector,
    )
    bridge._action_lane_module = ActionLaneCapability(governance_layer=governance_layer)
    bridge._forge_lane_module = ForgeLaneCapability(patchforge=patchforge)
    bridge._document_vision_module = DocumentVisionCapability()
    bridge._ui_vision_module = UiVisionCapability()
    bridge._audio_module = AudioAnalyzeCapability()
    bridge._video_module = VideoAnalyzeCapability()
    bridge._image_module = ImageTransformCapability()
    bridge._beatbox_module = BeatboxScoreCapability()
    bridge._speakers_module = SpeakersMixCapability()
    bridge._adaptive_music_module = AdaptiveMusicComposeCapability()
    bridge._mandala_visual_sync_module = MandalaVisualSyncCapability()
    bridge._human_voice_speakers_pipeline_module = HumanVoiceSpeakersPipelineCapability()
    resolved_plug = spatial_plug if spatial_plug is not None else getattr(bridge, "_spatial_plug", None)
    bridge._holo_rt4d_module = HoloRt4dSpatialVisionCapability(spatial_plug=resolved_plug)
    if resolved_plug is not None:
        bridge._spatial_plug = resolved_plug
    bridge._story_forge_audio_module = ConfiguredStoryForgeAudioModule()
    bridge._task_bus_module = TaskBusCapability()

    beatbox_fields = (
        {
            "id": "mood",
            "label": "Mood",
            "type": "text",
            "required": False,
            "default": "focused",
            "placeholder": "calm | focused | intense | happy",
        },
        {
            "id": "energy",
            "label": "Energy",
            "type": "text",
            "required": False,
            "default": "62",
        },
        {
            "id": "tension",
            "label": "Tension",
            "type": "text",
            "required": False,
            "default": "40",
        },
        {
            "id": "duration_sec",
            "label": "Duration (sec)",
            "type": "text",
            "required": False,
            "default": "6",
        },
        {
            "id": "description",
            "label": "Scene / Intent",
            "type": "textarea",
            "required": False,
        },
    )
    speakers_fields = (
        {
            "id": "music_stem_path",
            "label": "Music Stem Path",
            "type": "text",
            "required": False,
            "placeholder": "from Beatbox score receipt",
        },
        {
            "id": "voice_stem_path",
            "label": "Voice Stem Path",
            "type": "text",
            "required": False,
        },
        {
            "id": "profile_id",
            "label": "Voice Profile Id",
            "type": "text",
            "required": False,
            "placeholder": "optional HumanVoice constraints",
        },
        {
            "id": "session_id",
            "label": "Session Id",
            "type": "text",
            "required": False,
        },
    )
    story_forge_fields = (
        {
            "id": "rendered_video_path",
            "label": "Rendered Video Path",
            "type": "text",
            "required": True,
            "placeholder": "/path/to/rendered.mp4",
        },
        {
            "id": "dialogue_lines",
            "label": "Dialogue Lines (JSON or text)",
            "type": "textarea",
            "required": False,
            "placeholder": "Required with narration_lines for validation",
        },
        {
            "id": "narration_lines",
            "label": "Narration Lines",
            "type": "textarea",
            "required": False,
        },
        {
            "id": "session_id",
            "label": "Session Id",
            "type": "text",
            "required": False,
        },
    )

    extra_specs = [
        _spec("memory", "memory_lane", "memory_list", "list", bridge._memory_lane_module, ("memory_list",)),
        _spec("workspace", "workspace_lane", "workspace_projects", "list_projects", bridge._workspace_lane_module, ("workspace_projects",)),
        _spec("action", "action_lane", "action_status", "status", bridge._action_lane_module, ("action_status",)),
        _spec("forge", "forge_lane", "forge_status", "status", bridge._forge_lane_module, ("forge_status",)),
        _spec("document_vision", "document_vision", "document_vision_extract", "extract_text", bridge._document_vision_module, ("document_vision",)),
        _spec("ui_vision", "ui_vision", "ui_vision_analyze", "analyze_screenshot", bridge._ui_vision_module, ("ui_vision",)),
        _spec("media", "audio_analyze", "audio_analyze", "analyze", bridge._audio_module, ("audio_analyze",)),
        _spec("media", "video_analyze", "video_analyze", "analyze", bridge._video_module, ("video_analyze",)),
        _spec("media", "image_transform", "image_transform", "transform", bridge._image_module, ("image_transform",)),
        _spec(
            "beatbox",
            "beatbox_score",
            "beatbox_score",
            "score",
            bridge._beatbox_module,
            ("beatbox_score",),
            capability_label="Beatbox Score",
            capability_summary="Compose a deterministic Beatbox arrangement from scene axes.",
            input_fields=beatbox_fields,
        ),
        _spec(
            "speakers",
            "speakers_mix",
            "speakers_mix",
            "mix",
            bridge._speakers_module,
            ("speakers_mix",),
            capability_label="Speakers Mix",
            capability_summary="Duck and render a Speakers final mix from Beatbox stems.",
            input_fields=speakers_fields,
        ),
        _spec(
            "adaptive_music",
            "adaptive_music_compose",
            "adaptive_music_compose",
            "compose",
            bridge._adaptive_music_module,
            ("adaptive_music_compose", "adaptive_music", "adaptive_score"),
            capability_label="Adaptive Music Compose",
            capability_summary=(
                "Compose Beatbox score and Speakers mix in one call; optional Mandala visual plan."
            ),
            input_fields=ADAPTIVE_MUSIC_COMPOSE_INPUT_FIELDS,
        ),
        _spec(
            "mandala",
            "mandala_visual_sync",
            "mandala_visual_sync",
            "sync",
            bridge._mandala_visual_sync_module,
            ("mandala_visual_sync", "mandala_sync"),
            capability_label="Mandala Visual Sync",
            capability_summary="Derive a plan-only Mandala visual adaptation from score/scene axes.",
            input_fields=MANDALA_VISUAL_SYNC_INPUT_FIELDS,
        ),
        _spec(
            "human_voice_speakers",
            "human_voice_speakers_pipeline",
            "human_voice_speakers_pipeline",
            "run",
            bridge._human_voice_speakers_pipeline_module,
            ("human_voice_speakers_pipeline", "voice_to_mix", "voice_speakers_handoff"),
            capability_label="Voice → Speakers Handoff",
            capability_summary=(
                "Guided extract → signoff → Speakers constraints handoff for mix-ready voice profiles."
            ),
            input_fields=HUMAN_VOICE_SPEAKERS_PIPELINE_INPUT_FIELDS,
        ),
        _spec(
            "holo_rt4d",
            "holo_rt4d_spatial_vision",
            "holo_rt4d_spatial_vision",
            "probe",
            bridge._holo_rt4d_module,
            ("holo_rt4d_spatial_vision", "holort4d", "holo_rt4d", "spatial_vision"),
            capability_label="HoloRT4D Spatial Vision",
            capability_summary=(
                "Probe governed 4D spatial vision: observer frustum visibility, "
                "occlusion, and depth order over a spatial graph."
            ),
            input_fields=HOLO_RT4D_INPUT_FIELDS,
        ),
        _spec(
            "story_forge",
            "story_forge_audio",
            "story_forge_audio",
            "run",
            bridge._story_forge_audio_module,
            ("story_forge_audio",),
            capability_label="Story Forge Audio",
            capability_summary=(
                "Fail-closed Story Forge → Beatbox → Speakers movie audio pipeline "
                "with receipt metadata (beside Score tools)."
            ),
            input_fields=story_forge_fields,
        ),
        _spec(
            "task_bus",
            "task_bus",
            "task_bus",
            "dispatch",
            bridge._task_bus_module,
            ("task_bus", "constitutional_task_bus", "dispatch_task_bus"),
            capability_label="Constitutional Task Bus",
            capability_summary=(
                "Single ingress: Intent → Evidence → Authority → Decision across "
                "governed Microsoft/OpenAI/Anthropic-style and picture lanes."
            ),
            input_fields=(
                {
                    "id": "text",
                    "label": "Operator ask",
                    "type": "text",
                    "required": True,
                    "default": "Plan this, write this, code this, give me pictures",
                    "placeholder": "plan / write / code / pictures",
                },
                {
                    "id": "force_demo",
                    "label": "Force demo",
                    "type": "boolean",
                    "required": False,
                    "default": True,
                },
            ),
        ),
        _spec(
            "task_bus",
            "task_bus_status",
            "task_bus_status",
            "status",
            bridge._task_bus_module,
            ("task_bus_status", "task_bus_catalog"),
            capability_label="Task Bus Status",
            capability_summary="Lane catalog and auth posture for the Constitutional Task Bus.",
            input_fields=(),
        ),
    ]

    for spec in extra_specs:
        spec["handler"] = _generic_handler(bridge, spec)
        bridge._route_specs.append(spec)

    bridge._routes = {
        _normalize_name(alias): spec
        for spec in bridge._route_specs
        for alias in spec["aliases"]
    }
    bridge._selection_routes = {
        (spec["capability_id"], spec["action"]): spec for spec in bridge._route_specs
    }
    bridge._universal_adapters_attached = True


def universal_bridge_enforced(bridge: CapabilityServiceBridge) -> bool:
    return bool(getattr(bridge, "_universal_adapters_attached", False))


def _spec(
    capability_id: str,
    label: str,
    tool: str,
    action: str,
    module: Any,
    aliases: tuple[str, ...],
    *,
    capability_label: str | None = None,
    capability_summary: str | None = None,
    input_fields: tuple[dict[str, Any], ...] | list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "capability_id": capability_id,
        "capability_label": capability_label or label.replace("_", " ").title(),
        "capability_summary": capability_summary or f"Governed {label} adapter.",
        "tool": tool,
        "tool_label": tool.replace("_", " ").title(),
        "action": action,
        "action_label": action.replace("_", " ").title(),
        "module": module,
        "aliases": aliases,
        "endpoint": "/api/jarvis/capability-bridge/execute",
        "provider_modes": ("deterministic",),
        "default_provider_mode": "deterministic",
        "governance_modes": DEFAULT_GOVERNANCE_MODES,
        "default_governance_mode": "strict",
        "input_fields": tuple(input_fields or ()),
    }


def _generic_handler(bridge: CapabilityServiceBridge, spec: dict[str, Any]):
    def handler(
        args: dict[str, Any],
        *,
        execution_profile: dict[str, Any] | None = None,
        phase_gate: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = dict(args or {})
        tool = spec.get("tool", "")
        cap_id = spec.get("capability_id", "")

        # MVP wiring for non-OTEM capability bridge flows: delegate forge/evolve to live contractors if reachable.
        # This makes direct capability.execute (used by some agents/workflows) use the live services (6060/6062)
        # and records the via + results for observability, falling back to local module otherwise.
        if "forge" in tool.lower() or "forge" in cap_id.lower():
            try:
                forge_client.health()
                kind = payload.get("kind", "generate_diff")
                ctx = payload.get("context") or payload
                result = forge_client.request(kind=kind, context=dict(ctx))
                cap_res = {"ok": True, "data": result, "via": "live_forge"}
                return bridge._finalize_result(
                    spec=spec,
                    tool_result={
                        "type": spec["tool"],
                        "tool": spec["tool"],
                        "status": "completed",
                        "args": payload,
                        "result": result,
                        "via": "live_forge",
                    },
                    capability_result=cap_res,
                    response=f"{spec['tool']} completed via live Forge.",
                    execution_profile=execution_profile,
                    phase_gate=phase_gate,
                )
            except Exception:
                pass  # fall to local
        if "evolve" in tool.lower() or "evolve" in cap_id.lower():
            try:
                evolve_client.health()
                task = payload.get("task") or payload.get("goal") or "evolve"
                result = evolve_client.evolve(task=task, config=dict(payload.get("config") or {}))
                cap_res = {"ok": True, "data": result, "via": "live_evolve"}
                return bridge._finalize_result(
                    spec=spec,
                    tool_result={
                        "type": spec["tool"],
                        "tool": spec["tool"],
                        "status": "completed",
                        "args": payload,
                        "result": result,
                        "via": "live_evolve",
                    },
                    capability_result=cap_res,
                    response=f"{spec['tool']} completed via live Evolve.",
                    execution_profile=execution_profile,
                    phase_gate=phase_gate,
                )
            except Exception:
                pass  # fall to local

        capability_result = spec["module"].execute(spec["action"], payload)
        response = (
            f"{spec['tool']} completed."
            if capability_result.get("ok")
            else f"{spec['tool']} failed: {capability_result.get('message', 'error')}"
        )
        return bridge._finalize_result(
            spec=spec,
            tool_result={
                "type": spec["tool"],
                "tool": spec["tool"],
                "status": "completed" if capability_result.get("ok") else "failed",
                "args": payload,
                "result": capability_result.get("data") or {},
            },
            capability_result=capability_result,
            response=response,
            execution_profile=execution_profile,
            phase_gate=phase_gate,
        )

    return handler


GAP_COMPONENT_IDS = (
    MEMORY_LANE_COMPONENT_ID,
    WORKSPACE_LANE_COMPONENT_ID,
    ACTION_LANE_COMPONENT_ID,
    FORGE_LANE_COMPONENT_ID,
    DOCUMENT_VISION_COMPONENT_ID,
    UI_VISION_COMPONENT_ID,
    MEDIA_PROCESSOR_COMPONENT_ID,
    BEATBOX_LANE_COMPONENT_ID,
    SPEAKERS_LANE_COMPONENT_ID,
    ADAPTIVE_MUSIC_COMPOSE_COMPONENT_ID,
    MANDALA_VISUAL_SYNC_COMPONENT_ID,
    HUMAN_VOICE_SPEAKERS_PIPELINE_COMPONENT_ID,
    HOLO_RT4D_SPATIAL_VISION_COMPONENT_ID,
    STORY_FORGE_AUDIO_CAPABILITY_COMPONENT_ID,
)


class ConfiguredStoryForgeAudioModule:
    """Story Forge audio capability module.

    This follows the same shape as other capability modules so that
    CapabilityServiceBridge / _spec / generic handlers can read
    .provider_name, .module_name, .supported_actions etc. on the *instance*.
    """

    module_name = "story_forge_audio"
    provider_name = "aais_story_forge"
    supported_actions = frozenset({"run"})

    def __init__(self) -> None:
        # Ensure instance attributes exist (some bridge code does getattr on instances).
        self.module_name = self.module_name
        self.provider_name = self.provider_name
        self.supported_actions = self.supported_actions

    def execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        from src.capabilities.story_forge_audio import run_story_forge_audio_capability

        if action != "run":
            return {"ok": False, "message": f"unsupported action: {action}"}
        try:
            result = run_story_forge_audio_capability(dict(payload or {}))
            status = str((result or {}).get("status") or "").strip().lower()
            ok = status in {"completed", "ok"} or bool((result or {}).get("ok"))
            if status in {"rejected", "failed"}:
                ok = False
            # Fail-closed: AuthorityRejected / ValidationRejected stay ok=False
            if (result or {}).get("error_type") in {
                "AuthorityRejected",
                "ValidationRejected",
                "ExecutionError",
            }:
                ok = False
            enriched = dict(result or {})
            enriched.setdefault("console_path", "/adaptive-music?panel=story-forge")
            enriched.setdefault("lane_neighbors", ("beatbox_score", "speakers_mix", "adaptive_music_compose"))
            enriched.setdefault(
                "receipt",
                {
                    "capability": "story_forge_audio",
                    "status": enriched.get("status"),
                    "session_id": enriched.get("session_id"),
                    "story_id": enriched.get("story_id"),
                    "run_id": enriched.get("run_id"),
                    "scene_id": enriched.get("scene_id"),
                    "mix_sha256": enriched.get("mix_sha256") or enriched.get("final_audio_sha256"),
                    "error_type": enriched.get("error_type"),
                },
            )
            return {
                "ok": ok,
                "data": enriched,
                "message": enriched.get("message") or ("ok" if ok else "rejected"),
                "error_type": enriched.get("error_type"),
            }
        except Exception as exc:
            return {"ok": False, "message": str(exc), "error_type": "ExecutionError"}
