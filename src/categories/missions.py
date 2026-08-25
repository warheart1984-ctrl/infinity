CATEGORY = {
    "name": "missions",
    "label": "Missions",
    "icon": "🎯",
    "fields": {
        "title": {"type": "string", "required": True},
        "content": {"type": "text", "required": True},
        "objective": {"type": "text"},
        "status": {"type": "enum", "options": ["active", "blocked", "complete"], "default": "active"},
    },
    "default_sensitivity": 8,
    "default_priority": 60,
    "allow_pin": True,
    "retrieval_hints": ["objective", "status"],
}
