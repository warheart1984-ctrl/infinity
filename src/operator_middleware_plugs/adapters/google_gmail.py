"""Google Gmail / email workflow plug — live Gmail API when token present.

# Mythic: Google email workflows
# Engineering: GoogleGmailMiddlewarePlug
"""

from __future__ import annotations

from typing import Any

from src.operator_middleware_plugs.clients.gmail_client import gmail_send
from src.operator_middleware_plugs.contract import (
    MiddlewarePlug,
    MiddlewarePlugAction,
    MiddlewarePlugDescriptor,
)
from src.operator_middleware_plugs.oauth_token_store import resolve_gmail_token


class GoogleGmailMiddlewarePlug(MiddlewarePlug):
    plug_id = "middleware.google.gmail"

    def describe(self) -> MiddlewarePlugDescriptor:
        token = resolve_gmail_token()
        return MiddlewarePlugDescriptor(
            plug_id=self.plug_id,
            display_name="Google Gmail / Email Workflows",
            provider="google",
            authority_level="execute",
            actions=[
                MiddlewarePlugAction("list_drafts", "List drafts", "List or simulate drafts"),
                MiddlewarePlugAction("send_draft", "Send / prepare draft", "Send when live; else demo draft"),
                MiddlewarePlugAction("email_send", "Email send", "Workflow email.send path"),
            ],
            auth_status="ready" if token else "needs_auth",
            activation_hint=(
                None
                if token
                else "Connect Gmail (OAuth) or set AAIS_GMAIL_ACCESS_TOKEN."
            ),
        )

    def execute(self, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = dict(payload or {})
        action = (action or "email_send").strip() or "email_send"
        force_demo = bool(payload.get("force_demo", True))
        token = resolve_gmail_token()
        to = str(payload.get("to") or "operator@local")
        subject = str(payload.get("subject") or "AAIS email")
        body = str(payload.get("body") or payload.get("text") or "")

        if force_demo or not token:
            if not force_demo and not token:
                return self._needs_auth(
                    action,
                    "Connect Gmail or set AAIS_GMAIL_ACCESS_TOKEN for live send.",
                )
            return self._demo(
                action,
                f"Demo email draft to {to} (no Gmail API call).",
                {"to": to, "subject": subject, "body": body[:2000], "provider": "google_gmail"},
            )

        # Token present → live Gmail API (fail closed on HTTP errors)
        result = gmail_send(token, to=to, subject=subject, body=body)
        if not result.get("ok"):
            return {
                "ok": False,
                "outcome": "error",
                "plug_id": self.plug_id,
                "action": action,
                "auth_status": "ready",
                "summary": result.get("error") or "Gmail send failed",
                "data": result,
                "reason_code": result.get("reason_code") or "GMAIL_HTTP_ERROR",
            }
        return {
            "ok": True,
            "outcome": "live",
            "plug_id": self.plug_id,
            "action": action,
            "auth_status": "ready",
            "summary": f"Gmail message sent to {to}",
            "data": result,
            "reason_code": result.get("reason_code") or "GMAIL_LIVE_OK",
        }
