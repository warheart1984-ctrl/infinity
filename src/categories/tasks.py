CATEGORY = {
    "name": "tasks",
    "label": "Tasks",
    "icon": "✅",
    "fields": {
        "title": {"type": "string", "required": True},
        "content": {"type": "text", "required": True},
        "due_date": {"type": "date", "required": False},
        "status": {"type": "enum", "options": ["open", "blocked", "done"], "default": "open"},
    },
    "default_sensitivity": 3,
    "default_priority": 40,
    "allow_pin": True,
    "retrieval_hints": ["due_date", "status"],
}
