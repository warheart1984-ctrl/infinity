"""CategoryManager — the only component that knows how memory categories work.

Auto-discovers CATEGORY dicts from src/categories/*.py. New category =
drop a new file there. No core rewrites anywhere else.
"""

from __future__ import annotations

import datetime as _dt
import importlib
import pkgutil
from pathlib import Path

import src.categories as cat_pkg


class CategoryManager:
    def __init__(self):
        self.registry: dict[str, dict] = {}
        self.load_all()

    def load_all(self) -> None:
        for mod in pkgutil.iter_modules(cat_pkg.__path__):
            m = importlib.import_module(f"src.categories.{mod.name}")
            if hasattr(m, "CATEGORY"):
                cat = m.CATEGORY
                self.registry[cat["name"]] = cat

    def list(self) -> list[dict]:
        return sorted(self.registry.values(), key=lambda c: c["name"])

    def get(self, name: str) -> dict | None:
        return self.registry.get(str(name or "").strip().lower())

    def validate(self, category_name: str, data: dict) -> dict:
        cat = self.get(category_name)
        if not cat:
            raise ValueError(f"Unknown category {category_name}")

        cleaned: dict = {}
        for field, rules in (cat.get("fields") or {}).items():
            value = data.get(field)
            ftype = rules.get("type", "string")
            required = rules.get("required", False)

            if value is None or (isinstance(value, str) and not value.strip()):
                if required:
                    raise ValueError(f"Missing required field: {field}")
                continue

            if ftype == "string":
                value = str(value).strip()
                if len(value) > 300:
                    value = value[:300]
            elif ftype == "text":
                value = str(value)
            elif ftype == "date":
                try:
                    _dt.date.fromisoformat(str(value)[:10])
                    value = str(value)[:10]
                except ValueError as exc:
                    raise ValueError(f"{field}: invalid date (YYYY-MM-DD)") from exc
            elif ftype == "enum":
                options = rules.get("options") or []
                if str(value) not in options:
                    raise ValueError(f"{field}: must be one of {options}")
            cleaned[field] = value

        # enum defaults fill-in for optional enums left blank
        for field, rules in (cat.get("fields") or {}).items():
            if field not in cleaned and rules.get("type") == "enum" and rules.get("default"):
                cleaned[field] = rules["default"]

        missing_required_content = (
            "content" in (cat.get("fields") or {})
            and not str(data.get("content") or "").strip()
        )
        if missing_required_content:
            raise ValueError("Missing required field: content")
        return cleaned

    def defaults_for(self, name: str) -> dict:
        cat = self.get(name) or {}
        return {
            "priority": int(cat.get("default_priority", 30)),
            "sensitivity": int(cat.get("default_sensitivity", 1)),
            "allow_pin": bool(cat.get("allow_pin", True)),
            "icon": cat.get("icon", ""),
            "label": cat.get("label", name),
        }


category_manager = CategoryManager()
