from __future__ import annotations

WORKFLOW_TEMPLATES = [
    {
        "id": "email-summary-slack",
        "name": "Email Summary to Slack",
        "description": "Summarize incoming emails with AI and post the result into Slack.",
        "category": "email",
        "difficulty": "easy",
        "integrations": ["email", "slack"],
        "workflow": {
            "name": "Email Summary to Slack",
            "nodes": [
                {
                    "id": "trigger-1",
                    "type": "triggerNode",
                    "position": {"x": 40, "y": 220},
                    "data": {
                        "label": "Incoming Email",
                        "kind": "trigger",
                        "subtype": "email.received",
                        "config": {
                            "inbox": "primary",
                            "middleware_plug": "middleware.google.gmail",
                        },
                    },
                },
                {
                    "id": "action-1",
                    "type": "actionNode",
                    "position": {"x": 360, "y": 140},
                    "data": {
                        "label": "Summarize with AI",
                        "kind": "action",
                        "subtype": "ai.analyze",
                        "config": {"goal": "Summarize email and detect urgency"},
                    },
                },
                {
                    "id": "action-2",
                    "type": "actionNode",
                    "position": {"x": 700, "y": 140},
                    "data": {
                        "label": "Send to Slack",
                        "kind": "action",
                        "subtype": "slack.send",
                        "config": {"channel": "#alerts"},
                    },
                },
            ],
            "edges": [
                {"id": "e1", "source": "trigger-1", "target": "action-1"},
                {"id": "e2", "source": "action-1", "target": "action-2"},
            ],
            "config": {
                "schemaVersion": 1,
                "name": "Email Summary to Slack",
                "trigger": {
                    "type": "email.received",
                    "label": "Incoming Email",
                    "config": {
                        "inbox": "primary",
                        "middleware_plug": "middleware.google.gmail",
                    },
                },
                "steps": [
                    {
                        "id": "action-1",
                        "order": 1,
                        "type": "ai.analyze",
                        "label": "Summarize with AI",
                        "config": {"goal": "Summarize email and detect urgency"},
                    },
                    {
                        "id": "action-2",
                        "order": 2,
                        "type": "slack.send",
                        "label": "Send to Slack",
                        "config": {"channel": "#alerts"},
                    },
                ],
                "edges": [
                    {"id": "e1", "source": "trigger-1", "sourceHandle": None, "target": "action-1"},
                    {"id": "e2", "source": "action-1", "sourceHandle": None, "target": "action-2"},
                ],
            },
        },
    },
    {
        "id": "daily-ai-brief",
        "name": "Daily AI Brief",
        "description": "Run on a schedule, create a short brief, and prepare an email delivery.",
        "category": "productivity",
        "difficulty": "easy",
        "integrations": ["email", "schedules"],
        "workflow": {
            "name": "Daily AI Brief",
            "nodes": [
                {
                    "id": "trigger-1",
                    "type": "triggerNode",
                    "position": {"x": 40, "y": 220},
                    "data": {
                        "label": "Daily Schedule",
                        "kind": "trigger",
                        "subtype": "schedule.tick",
                        "config": {"cron": "0 9 * * *"},
                    },
                },
                {
                    "id": "action-1",
                    "type": "actionNode",
                    "position": {"x": 360, "y": 140},
                    "data": {
                        "label": "Generate Brief",
                        "kind": "action",
                        "subtype": "ai.analyze",
                        "config": {"goal": "Create a short daily brief"},
                    },
                },
                {
                    "id": "action-2",
                    "type": "actionNode",
                    "position": {"x": 700, "y": 140},
                    "data": {
                        "label": "Send Email",
                        "kind": "action",
                        "subtype": "email.send",
                        "config": {
                            "to": "user@example.com",
                            "subject": "Daily Brief",
                            "middleware_plug": "middleware.google.gmail",
                            "action": "email_send",
                        },
                    },
                },
            ],
            "edges": [
                {"id": "e1", "source": "trigger-1", "target": "action-1"},
                {"id": "e2", "source": "action-1", "target": "action-2"},
            ],
            "config": {
                "schemaVersion": 1,
                "name": "Daily AI Brief",
                "trigger": {
                    "type": "schedule.tick",
                    "label": "Daily Schedule",
                    "config": {"cron": "0 9 * * *"},
                },
                "steps": [
                    {
                        "id": "action-1",
                        "order": 1,
                        "type": "ai.analyze",
                        "label": "Generate Brief",
                        "config": {"goal": "Create a short daily brief"},
                    },
                    {
                        "id": "action-2",
                        "order": 2,
                        "type": "email.send",
                        "label": "Send Email",
                        "config": {
                            "to": "user@example.com",
                            "subject": "Daily Brief",
                            "middleware_plug": "middleware.google.gmail",
                            "action": "email_send",
                        },
                    },
                ],
                "edges": [
                    {"id": "e1", "source": "trigger-1", "sourceHandle": None, "target": "action-1"},
                    {"id": "e2", "source": "action-1", "sourceHandle": None, "target": "action-2"},
                ],
            },
        },
    },
    {
        "id": "webhook-summary-slack-safe",
        "name": "Webhook Summary to Slack (Safe Mode)",
        "description": "Receive webhook payloads, summarize them, and prepare a safe Slack alert without sending live.",
        "category": "api",
        "difficulty": "medium",
        "integrations": ["api", "slack"],
        "workflow": {
            "name": "Webhook Summary to Slack (Safe Mode)",
            "nodes": [
                {
                    "id": "trigger-1",
                    "type": "triggerNode",
                    "position": {"x": 40, "y": 220},
                    "data": {
                        "label": "Incoming Webhook",
                        "kind": "trigger",
                        "subtype": "webhook.received",
                        "config": {"source": "partner-system", "secret": "smoke-secret"},
                    },
                },
                {
                    "id": "action-1",
                    "type": "actionNode",
                    "position": {"x": 360, "y": 140},
                    "data": {
                        "label": "Summarize Event",
                        "kind": "action",
                        "subtype": "ai.analyze",
                        "config": {"goal": "Summarize the webhook event and surface urgent signals", "mode": "fake"},
                    },
                },
                {
                    "id": "action-2",
                    "type": "actionNode",
                    "position": {"x": 700, "y": 140},
                    "data": {
                        "label": "Prepare Slack Alert",
                        "kind": "action",
                        "subtype": "slack.send",
                        "config": {
                            "channel": "#alerts",
                            "deliveryMode": "fake",
                            "simulateDelayMs": "12000",
                        },
                    },
                },
            ],
            "edges": [
                {"id": "e1", "source": "trigger-1", "target": "action-1"},
                {"id": "e2", "source": "action-1", "target": "action-2"},
            ],
            "config": {
                "schemaVersion": 1,
                "name": "Webhook Summary to Slack (Safe Mode)",
                "trigger": {
                    "type": "webhook.received",
                    "label": "Incoming Webhook",
                    "config": {"source": "partner-system", "secret": "smoke-secret"},
                },
                "steps": [
                    {
                        "id": "action-1",
                        "order": 1,
                        "type": "ai.analyze",
                        "label": "Summarize Event",
                        "config": {"goal": "Summarize the webhook event and surface urgent signals", "mode": "fake"},
                    },
                    {
                        "id": "action-2",
                        "order": 2,
                        "type": "slack.send",
                        "label": "Prepare Slack Alert",
                        "config": {
                            "channel": "#alerts",
                            "deliveryMode": "fake",
                            "simulateDelayMs": "12000",
                        },
                    },
                ],
                "edges": [
                    {"id": "e1", "source": "trigger-1", "sourceHandle": None, "target": "action-1"},
                    {"id": "e2", "source": "action-1", "sourceHandle": None, "target": "action-2"},
                ],
            },
        },
    },
    {
        "id": "sovereign-sound-loop",
        "name": "Sovereign Sound Loop",
        "description": "Scene axes → Beatbox score → Speakers mix → Mandala plan → optional HoloRT4D probe.",
        "category": "media",
        "difficulty": "medium",
        "integrations": ["adaptive_music", "mandala", "holo", "speakers", "beatbox"],
        "workflow": {
            "name": "Sovereign Sound Loop",
            "nodes": [
                {
                    "id": "trigger-1",
                    "type": "triggerNode",
                    "position": {"x": 40, "y": 220},
                    "data": {
                        "label": "Operator Scene Axes",
                        "kind": "trigger",
                        "subtype": "operator.manual",
                        "config": {"surface": "/adaptive-music?panel=sovereign-sound"},
                    },
                },
                {
                    "id": "action-1",
                    "type": "actionNode",
                    "position": {"x": 320, "y": 120},
                    "data": {
                        "label": "Compose + Mix",
                        "kind": "action",
                        "subtype": "capability.execute",
                        "config": {"tool": "adaptive_music_compose", "include_mandala_sync": True},
                    },
                },
                {
                    "id": "action-2",
                    "type": "actionNode",
                    "position": {"x": 600, "y": 120},
                    "data": {
                        "label": "Mandala Visual Sync",
                        "kind": "action",
                        "subtype": "capability.execute",
                        "config": {"tool": "mandala_visual_sync"},
                    },
                },
                {
                    "id": "action-3",
                    "type": "actionNode",
                    "position": {"x": 880, "y": 220},
                    "data": {
                        "label": "Optional Holo Probe",
                        "kind": "action",
                        "subtype": "capability.execute",
                        "config": {"tool": "holo_rt4d_spatial_vision", "optional": True},
                    },
                },
            ],
            "edges": [
                {"id": "e1", "source": "trigger-1", "target": "action-1"},
                {"id": "e2", "source": "action-1", "target": "action-2"},
                {"id": "e3", "source": "action-2", "target": "action-3"},
            ],
            "config": {
                "schemaVersion": 1,
                "name": "Sovereign Sound Loop",
                "trigger": {
                    "type": "operator.manual",
                    "label": "Operator Scene Axes",
                    "config": {"surface": "/adaptive-music?panel=sovereign-sound"},
                },
                "steps": [
                    {
                        "id": "action-1",
                        "order": 1,
                        "type": "capability.execute",
                        "label": "Compose + Mix",
                        "config": {"tool": "adaptive_music_compose", "include_mandala_sync": True},
                    },
                    {
                        "id": "action-2",
                        "order": 2,
                        "type": "capability.execute",
                        "label": "Mandala Visual Sync",
                        "config": {"tool": "mandala_visual_sync"},
                    },
                    {
                        "id": "action-3",
                        "order": 3,
                        "type": "capability.execute",
                        "label": "Optional Holo Probe",
                        "config": {"tool": "holo_rt4d_spatial_vision", "optional": True},
                    },
                ],
                "edges": [
                    {"id": "e1", "source": "trigger-1", "sourceHandle": None, "target": "action-1"},
                    {"id": "e2", "source": "action-1", "sourceHandle": None, "target": "action-2"},
                    {"id": "e3", "source": "action-2", "sourceHandle": None, "target": "action-3"},
                ],
            },
        },
    },
    {
        "id": "spatial-score-couple",
        "name": "Spatial Score Couple",
        "description": "Feed HoloRT4D visibility/occlusion into adaptive compose mood and tension.",
        "category": "media",
        "difficulty": "medium",
        "integrations": ["holo", "adaptive_music", "spatial"],
        "workflow": {
            "name": "Spatial Score Couple",
            "nodes": [
                {
                    "id": "trigger-1",
                    "type": "triggerNode",
                    "position": {"x": 40, "y": 200},
                    "data": {
                        "label": "Holo Visibility Frame",
                        "kind": "trigger",
                        "subtype": "capability.execute",
                        "config": {"tool": "holo_rt4d_spatial_vision"},
                    },
                },
                {
                    "id": "action-1",
                    "type": "actionNode",
                    "position": {"x": 360, "y": 140},
                    "data": {
                        "label": "Couple Axes",
                        "kind": "action",
                        "subtype": "capability.execute",
                        "config": {"endpoint": "/api/jarvis/adaptive-music/spatial-score-couple"},
                    },
                },
                {
                    "id": "action-2",
                    "type": "actionNode",
                    "position": {"x": 700, "y": 140},
                    "data": {
                        "label": "Compose Adaptive Score",
                        "kind": "action",
                        "subtype": "capability.execute",
                        "config": {"tool": "adaptive_music_compose", "couple_mode": "override"},
                    },
                },
            ],
            "edges": [
                {"id": "e1", "source": "trigger-1", "target": "action-1"},
                {"id": "e2", "source": "action-1", "target": "action-2"},
            ],
            "config": {
                "schemaVersion": 1,
                "name": "Spatial Score Couple",
                "trigger": {
                    "type": "capability.execute",
                    "label": "Holo Visibility Frame",
                    "config": {"tool": "holo_rt4d_spatial_vision"},
                },
                "steps": [
                    {
                        "id": "action-1",
                        "order": 1,
                        "type": "capability.execute",
                        "label": "Couple Axes",
                        "config": {"endpoint": "/api/jarvis/adaptive-music/spatial-score-couple"},
                    },
                    {
                        "id": "action-2",
                        "order": 2,
                        "type": "capability.execute",
                        "label": "Compose Adaptive Score",
                        "config": {"tool": "adaptive_music_compose", "couple_mode": "override"},
                    },
                ],
                "edges": [
                    {"id": "e1", "source": "trigger-1", "sourceHandle": None, "target": "action-1"},
                    {"id": "e2", "source": "action-1", "sourceHandle": None, "target": "action-2"},
                ],
            },
        },
    },
    {
        "id": "voice-to-mix",
        "name": "Voice → Mix",
        "description": "Extract human voice traits, sign off, hand off Speakers constraints, then mix.",
        "category": "media",
        "difficulty": "easy",
        "integrations": ["voice", "speakers", "adaptive_music"],
        "workflow": {
            "name": "Voice to Mix",
            "nodes": [
                {
                    "id": "trigger-1",
                    "type": "triggerNode",
                    "position": {"x": 40, "y": 200},
                    "data": {
                        "label": "Voice Notes",
                        "kind": "trigger",
                        "subtype": "operator.manual",
                        "config": {"surface": "/adaptive-music?panel=voice-mix"},
                    },
                },
                {
                    "id": "action-1",
                    "type": "actionNode",
                    "position": {"x": 360, "y": 140},
                    "data": {
                        "label": "Voice → Speakers Pipeline",
                        "kind": "action",
                        "subtype": "capability.execute",
                        "config": {"tool": "human_voice_speakers_pipeline", "auto_signoff": True},
                    },
                },
                {
                    "id": "action-2",
                    "type": "actionNode",
                    "position": {"x": 700, "y": 140},
                    "data": {
                        "label": "Speakers Mix",
                        "kind": "action",
                        "subtype": "capability.execute",
                        "config": {"tool": "speakers_mix"},
                    },
                },
            ],
            "edges": [
                {"id": "e1", "source": "trigger-1", "target": "action-1"},
                {"id": "e2", "source": "action-1", "target": "action-2"},
            ],
            "config": {
                "schemaVersion": 1,
                "name": "Voice to Mix",
                "trigger": {
                    "type": "operator.manual",
                    "label": "Voice Notes",
                    "config": {"surface": "/adaptive-music?panel=voice-mix"},
                },
                "steps": [
                    {
                        "id": "action-1",
                        "order": 1,
                        "type": "capability.execute",
                        "label": "Voice → Speakers Pipeline",
                        "config": {"tool": "human_voice_speakers_pipeline", "auto_signoff": True},
                    },
                    {
                        "id": "action-2",
                        "order": 2,
                        "type": "capability.execute",
                        "label": "Speakers Mix",
                        "config": {"tool": "speakers_mix"},
                    },
                ],
                "edges": [
                    {"id": "e1", "source": "trigger-1", "sourceHandle": None, "target": "action-1"},
                    {"id": "e2", "source": "action-1", "sourceHandle": None, "target": "action-2"},
                ],
            },
        },
    },
    {
        "id": "imagine-audio-pack",
        "name": "Imagine → Audio Pack",
        "description": "Turn an Imagine generation brief into an adaptive score + Mandala visual pack.",
        "category": "media",
        "difficulty": "medium",
        "integrations": ["imagine", "adaptive_music", "mandala"],
        "workflow": {
            "name": "Imagine to Audio Pack",
            "nodes": [
                {
                    "id": "trigger-1",
                    "type": "triggerNode",
                    "position": {"x": 40, "y": 200},
                    "data": {
                        "label": "Imagine Brief",
                        "kind": "trigger",
                        "subtype": "capability.execute",
                        "config": {"tool": "imagine_generate"},
                    },
                },
                {
                    "id": "action-1",
                    "type": "actionNode",
                    "position": {"x": 360, "y": 140},
                    "data": {
                        "label": "Adaptive Compose Pack",
                        "kind": "action",
                        "subtype": "capability.execute",
                        "config": {"tool": "adaptive_music_compose", "include_mandala_sync": True},
                    },
                },
                {
                    "id": "action-2",
                    "type": "actionNode",
                    "position": {"x": 700, "y": 140},
                    "data": {
                        "label": "Mandala Sync",
                        "kind": "action",
                        "subtype": "capability.execute",
                        "config": {"tool": "mandala_visual_sync"},
                    },
                },
            ],
            "edges": [
                {"id": "e1", "source": "trigger-1", "target": "action-1"},
                {"id": "e2", "source": "action-1", "target": "action-2"},
            ],
            "config": {
                "schemaVersion": 1,
                "name": "Imagine to Audio Pack",
                "trigger": {
                    "type": "capability.execute",
                    "label": "Imagine Brief",
                    "config": {"tool": "imagine_generate"},
                },
                "steps": [
                    {
                        "id": "action-1",
                        "order": 1,
                        "type": "capability.execute",
                        "label": "Adaptive Compose Pack",
                        "config": {"tool": "adaptive_music_compose", "include_mandala_sync": True},
                    },
                    {
                        "id": "action-2",
                        "order": 2,
                        "type": "capability.execute",
                        "label": "Mandala Sync",
                        "config": {"tool": "mandala_visual_sync"},
                    },
                ],
                "edges": [
                    {"id": "e1", "source": "trigger-1", "sourceHandle": None, "target": "action-1"},
                    {"id": "e2", "source": "action-1", "sourceHandle": None, "target": "action-2"},
                ],
            },
        },
    },
    {
        "id": "constitutional-task-bus-mixed",
        "name": "Constitutional Task Bus (mixed ask)",
        "description": (
            "Dispatch a multi-lane ask through the Task & Skills Bus: "
            "plan / write / code / pictures under one governed trace."
        ),
        "category": "productivity",
        "difficulty": "easy",
        "integrations": ["task_bus", "image", "workflows"],
        "workflow": {
            "name": "Task Bus Mixed Dispatch",
            "nodes": [
                {
                    "id": "trigger-1",
                    "type": "triggerNode",
                    "position": {"x": 40, "y": 200},
                    "data": {
                        "label": "Operator Ask",
                        "kind": "trigger",
                        "subtype": "operator.manual",
                        "config": {"surface": "/task-bus"},
                    },
                },
                {
                    "id": "action-1",
                    "type": "actionNode",
                    "position": {"x": 360, "y": 140},
                    "data": {
                        "label": "Task Bus Dispatch",
                        "kind": "action",
                        "subtype": "capability.execute",
                        "config": {
                            "tool": "task_bus",
                            "action": "dispatch",
                            "force_demo": True,
                            "text": "Plan this, write this, code this, give me pictures",
                        },
                    },
                },
                {
                    "id": "action-2",
                    "type": "actionNode",
                    "position": {"x": 640, "y": 140},
                    "data": {
                        "label": "Open Image Generator",
                        "kind": "action",
                        "subtype": "operator.manual",
                        "config": {"surface": "/image-generator"},
                    },
                },
            ],
            "edges": [
                {"id": "e1", "source": "trigger-1", "target": "action-1"},
                {"id": "e2", "source": "action-1", "target": "action-2"},
            ],
            "config": {
                "schemaVersion": 1,
                "name": "Task Bus Mixed Dispatch",
                "trigger": {
                    "type": "operator.manual",
                    "label": "Operator Ask",
                    "config": {"surface": "/task-bus"},
                },
                "steps": [
                    {
                        "id": "action-1",
                        "order": 1,
                        "type": "capability.execute",
                        "label": "Task Bus Dispatch",
                        "config": {
                            "tool": "task_bus",
                            "action": "dispatch",
                            "force_demo": True,
                            "text": "Plan this, write this, code this, give me pictures",
                        },
                    },
                    {
                        "id": "action-2",
                        "order": 2,
                        "type": "operator.manual",
                        "label": "Open Image Generator",
                        "config": {"surface": "/image-generator"},
                    },
                ],
                "edges": [
                    {"id": "e1", "source": "trigger-1", "sourceHandle": None, "target": "action-1"},
                    {"id": "e2", "source": "action-1", "sourceHandle": None, "target": "action-2"},
                ],
            },
        },
    },
]


def get_workflow_template(template_id: str) -> dict | None:
    for template in WORKFLOW_TEMPLATES:
        if template["id"] == template_id:
            return template
    return None
