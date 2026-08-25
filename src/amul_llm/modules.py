"""AMUL Modular layer: swappable engine modules.

Each module role is a Protocol so implementations can be swapped without the
runtime knowing. The first real core-model module targets Lemonade's
OpenAI-compatible API (http://localhost:13305/api/v1).
"""

from __future__ import annotations

import json
from typing import Any, Protocol, runtime_checkable

import httpx


@runtime_checkable
class CoreModelModule(Protocol):
    """Turns chat messages + generation config into generated text."""

    def generate(self, messages: list[dict[str, str]], config: dict[str, Any]) -> str: ...


@runtime_checkable
class ToolModule(Protocol):
    """Executes validated tool calls."""

    def call(self, name: str, args: dict[str, Any]) -> Any: ...

    def available(self) -> dict[str, dict[str, Any]]: ...


class LemonadeCoreModule:
    """Core model backed by Lemonade Server's OpenAI-compatible endpoint."""

    def __init__(
        self,
        model: str = "Qwen3-0.6B-GGUF",
        *,
        base_url: str = "http://localhost:13305/api/v1",
        transport: httpx.BaseTransport | None = None,
        timeout: float = 120.0,
    ):
        self.model = model
        self._client = httpx.Client(base_url=base_url, transport=transport, timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def generate(self, messages: list[dict[str, str]], config: dict[str, Any]) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": config.get("temperature", 0.7),
            "max_tokens": config.get("max_tokens", 1024),
        }
        response = self._client.post("/chat/completions", json=payload)
        if response.status_code >= 400:
            raise RuntimeError(f"core model error {response.status_code}: {response.text[:200]}")
        data = response.json()
        return data["choices"][0]["message"]["content"] or ""


class RegistryToolModule:
    """Schema-validated tool execution over an in-process registry."""

    def __init__(self) -> None:
        self._tools: dict[str, tuple[dict[str, Any], Any]] = {}

    def register(self, name: str, schema: dict[str, Any], fn: Any, description: str = "") -> None:
        self._tools[name] = (schema, fn)

    def available(self) -> dict[str, dict[str, Any]]:
        return {
            name: {"name": name, "schema": schema}
            for name, (schema, _fn) in self._tools.items()
        }

    def call(self, name: str, args: dict[str, Any]) -> Any:
        if name not in self._tools:
            raise KeyError(f"unknown tool: {name}")
        _schema, fn = self._tools[name]
        return fn(**args)

    def validate(self, name: str, raw_args: str | dict[str, Any]) -> list[str]:
        if name not in self._tools:
            return [f"unknown tool: {name}"]
        schema = self._tools[name][0]
        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        errors: list[str] = []
        for required in schema.get("required", []):
            if required not in args:
                errors.append(f"missing required arg: {required}")
        for key in args:
            if key not in schema.get("properties", {}):
                errors.append(f"unknown arg: {key}")
        return errors
