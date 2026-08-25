"""Guided Human Voice Extraction → Speakers handoff pipeline.

Mythic: Voice → Speakers
Engineering: HumanVoiceSpeakersPipelineCapability

Inputs:
  notes_text or fixture; optional signoff_by / auto_signoff
Outputs:
  SpeakersHandoffPayload with constraints path + console deep-link
Constraints:
  signoff required unless auto_signoff=true (operator-gated guided path)
Failure modes:
  missing notes → ValidationRejected; unsigned without auto → signoff_required
"""

from __future__ import annotations

from typing import Any

from src.capability_module import AAISCapabilityModule

HUMAN_VOICE_SPEAKERS_PIPELINE_COMPONENT_ID = "jarvis.capability.human_voice_speakers_pipeline"

HUMAN_VOICE_SPEAKERS_PIPELINE_INPUT_FIELDS = (
    {
        "id": "notes_text",
        "label": "Voice Notes",
        "type": "textarea",
        "required": False,
        "placeholder": "Operator notes describing the human voice profile",
    },
    {
        "id": "fixture",
        "label": "Fixture",
        "type": "text",
        "required": False,
        "default": "",
        "placeholder": "notes-demo-redacted (optional)",
    },
    {
        "id": "signoff_by",
        "label": "Signoff By",
        "type": "text",
        "required": False,
        "default": "operator",
    },
    {
        "id": "auto_signoff",
        "label": "Auto Signoff",
        "type": "boolean",
        "required": False,
        "default": True,
    },
)


def _coerce_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off", ""}


class HumanVoiceSpeakersPipelineCapability(AAISCapabilityModule):
    """One guided tool: extract → constraints/signoff → Speakers-ready handoff."""

    module_name = "human_voice_speakers_pipeline"
    supported_actions = frozenset({"run", "status"})

    def __init__(self) -> None:
        super().__init__(provider_name="aais_human_voice")
        self.handlers = {"run": self._handle_run, "status": self._handle_status}

    def _handle_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "standalone_lane": True,
            "execution_ready": True,
            "engine": "human_voice_speakers_pipeline.v1",
            "console_path": "/adaptive-music?panel=voice-mix",
            "steps": ("extract", "signoff", "handoff"),
        }

    def _handle_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        from src.capabilities.human_voice_extraction import run_human_voice_extraction_capability

        body = dict(payload or {})
        runtime_context = str(body.get("runtime_context") or "operator_runtime")
        auto_signoff = _coerce_bool(body.get("auto_signoff"), default=True)
        signoff_by = str(body.get("signoff_by") or "operator").strip() or "operator"

        extract_req = {
            "action": "extract",
            "runtime_context": runtime_context,
            "notes_text": body.get("notes_text") or "",
            "fixture": body.get("fixture") or None,
            "source_kind": body.get("source_kind") or "human_notes",
            "mission_id": body.get("mission_id"),
            "session_id": body.get("session_id"),
            "extraction_root": body.get("extraction_root"),
        }
        if not extract_req["fixture"] and not str(extract_req["notes_text"] or "").strip():
            extract_req["fixture"] = "notes-demo-redacted"

        extracted = run_human_voice_extraction_capability(extract_req)
        if not extracted.get("ok"):
            raise ValueError(extracted.get("message") or "extract failed")

        pack = extracted.get("extraction") or {}
        extraction_id = pack.get("extraction_id")
        steps: dict[str, Any] = {"extract": {"ok": True, "extraction_id": extraction_id}}

        if auto_signoff or not (pack.get("speakers_handoff") or {}).get("handoff_ready"):
            signed = run_human_voice_extraction_capability(
                {
                    "action": "signoff",
                    "runtime_context": runtime_context,
                    "extraction_id": extraction_id,
                    "extraction": pack,
                    "signoff_by": signoff_by,
                    "extraction_root": body.get("extraction_root"),
                }
            )
            steps["signoff"] = {
                "ok": bool(signed.get("ok")),
                "status": signed.get("status"),
                "message": signed.get("message"),
            }
            if not signed.get("ok"):
                raise ValueError(signed.get("message") or "signoff failed")
            pack = signed.get("extraction") or pack

        handoff = run_human_voice_extraction_capability(
            {
                "action": "handoff",
                "runtime_context": runtime_context,
                "extraction_id": extraction_id,
                "extraction": pack,
                "extraction_root": body.get("extraction_root"),
                "speakers_root": body.get("speakers_root"),
            }
        )
        steps["handoff"] = {
            "ok": bool(handoff.get("ok")),
            "status": handoff.get("status"),
            "result": handoff.get("result"),
        }
        if not handoff.get("ok"):
            reason = (handoff.get("result") or {}).get("reason") or "handoff failed"
            raise ValueError(str(reason))

        result = handoff.get("result") or {}
        constraints = result.get("constraints") or {}
        profile_id = constraints.get("profile_id") or (pack.get("voice_profile") or {}).get("profile_id")
        return {
            "ok": True,
            "status": "speakers_ready",
            "extraction_id": extraction_id,
            "profile_id": profile_id,
            "constraints_path": result.get("constraints_path"),
            "constraints": constraints,
            "speakers_handoff_payload": {
                "profile_id": profile_id,
                "constraints_path": result.get("constraints_path"),
                "target_lane": "speakers_render",
                "claim_label": constraints.get("claim_label") or pack.get("claim_label"),
                "mix_hint": {
                    "apply_voice_constraints": True,
                    "profile_id": profile_id,
                },
            },
            "steps": steps,
            "console_path": "/adaptive-music?panel=voice-mix",
            "standalone_lane": True,
            "engine": "human_voice_speakers_pipeline.v1",
        }
