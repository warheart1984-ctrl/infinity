"""Microsoft Graph Tasks / Calendar / Mail plugs — live when token present.

# Mythic: Microsoft Tasks / Outlook
# Engineering: MicrosoftGraphMiddlewarePlugs
"""

from __future__ import annotations

from typing import Any

from src.operator_middleware_plugs.clients.graph_client import (
    graph_create_event,
    graph_create_todo_task,
    graph_list_todo_tasks,
    graph_send_mail,
    graph_workbook_stub,
)
from src.operator_middleware_plugs.contract import (
    MiddlewarePlug,
    MiddlewarePlugAction,
    MiddlewarePlugDescriptor,
)
from src.operator_middleware_plugs.oauth_token_store import resolve_graph_token


def _graph_token() -> str | None:
    return resolve_graph_token()


class MicrosoftTasksMiddlewarePlug(MiddlewarePlug):
    plug_id = "middleware.microsoft.tasks"
    aliases = ("native.microsoft.tasks",)

    def describe(self) -> MiddlewarePlugDescriptor:
        token = _graph_token()
        return MiddlewarePlugDescriptor(
            plug_id=self.plug_id,
            display_name="Microsoft Graph Tasks / To Do",
            provider="microsoft",
            authority_level="execute",
            actions=[
                MiddlewarePlugAction("list_tasks", "List tasks"),
                MiddlewarePlugAction("create_task", "Create task"),
            ],
            auth_status="ready" if token else "needs_auth",
            activation_hint=(
                None if token else "Connect Microsoft 365 or set AAIS_MS_GRAPH_TOKEN."
            ),
        )

    def execute(self, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = dict(payload or {})
        action = (action or "list_tasks").strip() or "list_tasks"
        force_demo = bool(payload.get("force_demo", True))
        token = _graph_token()
        title = str(payload.get("title") or payload.get("text") or "AAIS task")
        if force_demo or not token:
            if not force_demo and not token:
                return self._needs_auth(action, "Connect Microsoft 365 for live Graph tasks.")
            tasks = [{"id": "demo-1", "title": title[:120], "status": "notStarted"}]
            return self._demo(action, f"Demo Graph tasks ({action}).", {"tasks": tasks})

        if action == "list_tasks":
            result = graph_list_todo_tasks(token)
        else:
            result = graph_create_todo_task(
                token,
                title,
                due_date=payload.get("dueDate") or payload.get("due_date"),
            )
        if not result.get("ok"):
            return {
                "ok": False,
                "outcome": "error",
                "plug_id": self.plug_id,
                "action": action,
                "auth_status": "ready",
                "summary": result.get("error") or "Graph tasks failed",
                "data": result,
                "reason_code": result.get("reason_code"),
            }
        return {
            "ok": True,
            "outcome": "live",
            "plug_id": self.plug_id,
            "action": action,
            "auth_status": "ready",
            "summary": f"Graph tasks {action} ok",
            "data": result,
            "reason_code": result.get("reason_code"),
        }


class MicrosoftCalendarMiddlewarePlug(MiddlewarePlug):
    plug_id = "native.calendar.schedule"

    def describe(self) -> MiddlewarePlugDescriptor:
        token = _graph_token()
        return MiddlewarePlugDescriptor(
            plug_id=self.plug_id,
            display_name="Microsoft Calendar Schedule",
            provider="microsoft",
            authority_level="execute",
            actions=[
                MiddlewarePlugAction("schedule", "Schedule event"),
                MiddlewarePlugAction("list_events", "List events"),
            ],
            auth_status="ready" if token else "needs_auth",
            activation_hint=(
                None if token else "Connect Microsoft 365 for live Calendar. Demo without token."
            ),
        )

    def execute(self, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = dict(payload or {})
        action = (action or "schedule").strip() or "schedule"
        force_demo = bool(payload.get("force_demo", True))
        token = _graph_token()
        title = str(payload.get("title") or payload.get("subject") or "AAIS follow-up")
        when = str(payload.get("when") or payload.get("start") or "next business day 10:00")
        if force_demo or not token:
            if not force_demo and not token:
                return self._needs_auth(action, "Connect Microsoft 365 for live Calendar.")
            return self._demo(
                action,
                f"Demo calendar block: {title} @ {when}",
                {"event": {"title": title, "when": when, "provider": "microsoft_graph_calendar"}},
            )
        result = graph_create_event(
            token,
            subject=title,
            start=payload.get("start") if isinstance(payload.get("start"), str) else None,
            end=payload.get("end") if isinstance(payload.get("end"), str) else None,
            body=str(payload.get("body") or ""),
        )
        if not result.get("ok"):
            return {
                "ok": False,
                "outcome": "error",
                "plug_id": self.plug_id,
                "action": action,
                "auth_status": "ready",
                "summary": result.get("error") or "Calendar failed",
                "data": result,
                "reason_code": result.get("reason_code"),
            }
        return {
            "ok": True,
            "outcome": "live",
            "plug_id": self.plug_id,
            "action": action,
            "auth_status": "ready",
            "summary": f"Calendar event created: {title}",
            "data": result,
            "reason_code": result.get("reason_code"),
        }


class MicrosoftMailMiddlewarePlug(MiddlewarePlug):
    plug_id = "middleware.microsoft.mail"

    def describe(self) -> MiddlewarePlugDescriptor:
        token = _graph_token()
        return MiddlewarePlugDescriptor(
            plug_id=self.plug_id,
            display_name="Microsoft Outlook / Graph Mail",
            provider="microsoft",
            authority_level="execute",
            actions=[
                MiddlewarePlugAction("send_mail", "Send mail"),
                MiddlewarePlugAction("email_send", "Email send (workflow)"),
            ],
            auth_status="ready" if token else "needs_auth",
            activation_hint=(
                None if token else "Connect Microsoft 365 for live Outlook mail."
            ),
        )

    def execute(self, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = dict(payload or {})
        action = (action or "email_send").strip() or "email_send"
        force_demo = bool(payload.get("force_demo", True))
        token = _graph_token()
        to = str(payload.get("to") or "operator@local")
        subject = str(payload.get("subject") or "AAIS mail")
        body = str(payload.get("body") or "")
        if force_demo or not token:
            if not force_demo and not token:
                return self._needs_auth(action, "Connect Microsoft 365 for live Outlook send.")
            return self._demo(
                action,
                f"Demo Outlook draft to {to}",
                {"to": to, "subject": subject, "body": body[:2000]},
            )
        result = graph_send_mail(token, to=to, subject=subject, body=body)
        if not result.get("ok"):
            return {
                "ok": False,
                "outcome": "error",
                "plug_id": self.plug_id,
                "action": action,
                "auth_status": "ready",
                "summary": result.get("error") or "Outlook send failed",
                "data": result,
                "reason_code": result.get("reason_code"),
            }
        return {
            "ok": True,
            "outcome": "live",
            "plug_id": self.plug_id,
            "action": action,
            "auth_status": "ready",
            "summary": f"Outlook mail sent to {to}",
            "data": result,
            "reason_code": result.get("reason_code"),
        }


class SpreadsheetGraphMiddlewarePlug(MiddlewarePlug):
    """Optional Graph workbook path for spreadsheet (stub path documented)."""

    plug_id = "middleware.microsoft.spreadsheet"

    def describe(self) -> MiddlewarePlugDescriptor:
        token = _graph_token()
        return MiddlewarePlugDescriptor(
            plug_id=self.plug_id,
            display_name="Microsoft Workbook (stub path)",
            provider="microsoft",
            authority_level="assist",
            actions=[MiddlewarePlugAction("workbook_get", "Get workbook stub")],
            auth_status="ready" if token else "needs_auth",
            activation_hint="Uses me/drive/root:/AAIS/exports/{name}:/workbook — full workbook API deferred.",
        )

    def execute(self, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = dict(payload or {})
        force_demo = bool(payload.get("force_demo", True))
        token = _graph_token()
        name = str(payload.get("name") or "export")
        if force_demo or not token:
            return self._demo(action or "workbook_get", f"Demo workbook stub {name}", {"name": name})
        result = graph_workbook_stub(token, name)
        return {
            "ok": result.get("ok", False),
            "outcome": "live" if result.get("ok") else "error",
            "plug_id": self.plug_id,
            "action": action or "workbook_get",
            "data": result,
            "reason_code": result.get("reason_code"),
            "summary": "Workbook stub path — full Excel session API deferred",
        }
