CATEGORY = {
    "name": "characters",
    "label": "Characters",
    "icon": "🎭",
    "fields": {
        "title": {"type": "string", "required": True},
        "content": {"type": "text", "required": True},
        "role": {"type": "string", "required": False},
    },
    "default_sensitivity": 4,
    "default_priority": 35,
    "allow_pin": True,
    "retrieval_hints": ["role"],
}
