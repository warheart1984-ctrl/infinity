"""OAuth token store — secure under .runtime/oauth/ (never return raw tokens to UI).

# Mythic: Provider credential vault
# Engineering: OauthTokenStore
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Literal

ProviderId = Literal["gmail", "microsoft"]
TokenMode = Literal["simulate", "live", "expired"]


def _runtime_root() -> Path:
    configured = os.getenv("AAIS_RUNTIME_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path(__file__).resolve().parents[2] / ".runtime"


class OauthTokenStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (_runtime_root() / "oauth" / "tokens.json")
        self._lock = threading.Lock()

    def _load(self) -> dict[str, Any]:
        if not self._path.is_file():
            return {"providers": {}}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"providers": {}}

    def _save(self, data: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def put_token(
        self,
        provider: ProviderId,
        *,
        access_token: str,
        refresh_token: str | None = None,
        expires_at: float | None = None,
        scopes: list[str] | None = None,
    ) -> None:
        with self._lock:
            data = self._load()
            providers = dict(data.get("providers") or {})
            providers[provider] = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "scopes": scopes or [],
                "updated_at": time.time(),
            }
            data["providers"] = providers
            self._save(data)

    def get_access_token(self, provider: ProviderId) -> str | None:
        with self._lock:
            row = (self._load().get("providers") or {}).get(provider) or {}
            token = str(row.get("access_token") or "").strip()
            if not token:
                return None
            expires_at = row.get("expires_at")
            if expires_at and float(expires_at) < time.time():
                return None
            return token

    def status(self, provider: ProviderId) -> dict[str, Any]:
        """UI-safe status — never includes raw token."""
        with self._lock:
            row = (self._load().get("providers") or {}).get(provider) or {}
        token = str(row.get("access_token") or "").strip()
        expires_at = row.get("expires_at")
        if not token:
            mode: TokenMode = "simulate"
            connected = False
        elif expires_at and float(expires_at) < time.time():
            mode = "expired"
            connected = False
        else:
            mode = "live"
            connected = True
        return {
            "provider": provider,
            "connected": connected,
            "mode": mode,
            "scopes": row.get("scopes") or [],
            "updated_at": row.get("updated_at"),
            # never: access_token / refresh_token
        }

    def clear(self, provider: ProviderId) -> None:
        with self._lock:
            data = self._load()
            providers = dict(data.get("providers") or {})
            providers.pop(provider, None)
            data["providers"] = providers
            self._save(data)


oauth_token_store = OauthTokenStore()


def resolve_gmail_token() -> str | None:
    return (
        oauth_token_store.get_access_token("gmail")
        or os.getenv("AAIS_GMAIL_ACCESS_TOKEN")
        or os.getenv("GMAIL_ACCESS_TOKEN")
        or os.getenv("GOOGLE_OAUTH_ACCESS_TOKEN")
        or None
    )


def resolve_graph_token() -> str | None:
    return (
        oauth_token_store.get_access_token("microsoft")
        or os.getenv("AAIS_MS_GRAPH_TOKEN")
        or os.getenv("MICROSOFT_GRAPH_TOKEN")
        or os.getenv("MS_GRAPH_ACCESS_TOKEN")
        or os.getenv("AAIS_OUTLOOK_ACCESS_TOKEN")
        or None
    )
