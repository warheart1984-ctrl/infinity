"""Microsoft Graph HTTP client — live when token present; simulate otherwise.

# Mythic: Microsoft Graph conduit
# Engineering: call_graph / GraphClient
"""

from __future__ import annotations

from typing import Any

import httpx

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def call_graph(
    token: str | None,
    path: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    timeout: float = 30.0,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    clean = path.lstrip("/")
    if not token:
        return {
            "ok": True,
            "status": 200,
            "simulated": True,
            "reason_code": "GRAPH_SIMULATE",
            "data": {"simulated": True, "method": method, "path": clean, "body": body},
        }
    try:
        with httpx.Client(timeout=timeout, transport=transport) as client:
            res = client.request(
                method.upper(),
                f"{GRAPH_BASE}/{clean}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json=body,
            )
        data: Any
        try:
            data = res.json()
        except Exception:
            data = {"raw": res.text[:2000]}
        if res.status_code >= 400:
            return {
                "ok": False,
                "status": res.status_code,
                "data": data,
                "error": f"Graph HTTP {res.status_code}",
                "reason_code": "GRAPH_HTTP_ERROR",
            }
        return {
            "ok": True,
            "status": res.status_code,
            "data": data,
            "reason_code": "GRAPH_LIVE_OK",
        }
    except httpx.HTTPError as exc:
        return {
            "ok": False,
            "status": 0,
            "error": str(exc),
            "reason_code": "GRAPH_NETWORK_ERROR",
        }


def graph_create_todo_task(
    token: str | None,
    title: str,
    *,
    list_id: str = "tasks",
    due_date: str | None = None,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"title": title, "status": "notStarted"}
    if due_date:
        body["dueDateTime"] = {"dateTime": due_date, "timeZone": "UTC"}
    return call_graph(
        token,
        f"me/todo/lists/{list_id}/tasks",
        method="POST",
        body=body,
        transport=transport,
    )


def graph_list_todo_tasks(
    token: str | None,
    *,
    list_id: str = "tasks",
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    return call_graph(
        token,
        f"me/todo/lists/{list_id}/tasks",
        method="GET",
        transport=transport,
    )


def graph_send_mail(
    token: str | None,
    *,
    to: str,
    subject: str,
    body: str,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    return call_graph(
        token,
        "me/sendMail",
        method="POST",
        body={
            "message": {
                "subject": subject,
                "body": {"contentType": "Text", "content": body},
                "toRecipients": [{"emailAddress": {"address": to}}],
            },
            "saveToSentItems": True,
        },
        transport=transport,
    )


def graph_create_event(
    token: str | None,
    *,
    subject: str,
    start: str | None = None,
    end: str | None = None,
    body: str = "",
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    from datetime import datetime, timedelta, timezone

    start_dt = start or datetime.now(timezone.utc).isoformat()
    end_dt = end or (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    return call_graph(
        token,
        "me/events",
        method="POST",
        body={
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "start": {"dateTime": start_dt, "timeZone": "UTC"},
            "end": {"dateTime": end_dt, "timeZone": "UTC"},
        },
        transport=transport,
    )


def graph_workbook_stub(
    token: str | None,
    name: str = "export",
    *,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    """Workbook path stub — full Excel API is heavy; document for later."""
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)[:80] or "export"
    return call_graph(
        token,
        f"me/drive/root:/AAIS/exports/{safe}:/workbook",
        method="GET",
        transport=transport,
    )
