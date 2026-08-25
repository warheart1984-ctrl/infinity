"""Gmail API client — users/me/messages/send when token present.

# Mythic: Gmail conduit
# Engineering: gmail_send / send_gmail_email
"""

from __future__ import annotations

import base64
from email.mime.text import MIMEText
from typing import Any

import httpx

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"


def _raw_message(to: str, subject: str, body: str) -> str:
    msg = MIMEText(body, "plain", "utf-8")
    msg["To"] = to
    msg["Subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii").rstrip("=")
    return raw


def gmail_send(
    token: str | None,
    *,
    to: str,
    subject: str,
    body: str,
    timeout: float = 30.0,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    if not token:
        return {
            "ok": True,
            "status": 200,
            "simulated": True,
            "reason_code": "GMAIL_SIMULATE",
            "data": {"simulated": True, "to": to, "subject": subject, "body": body[:2000]},
        }
    try:
        with httpx.Client(timeout=timeout, transport=transport) as client:
            res = client.post(
                f"{GMAIL_API_BASE}/users/me/messages/send",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={"raw": _raw_message(to, subject, body)},
            )
        try:
            data: Any = res.json()
        except Exception:
            data = {"raw": res.text[:2000]}
        if res.status_code >= 400:
            return {
                "ok": False,
                "status": res.status_code,
                "data": data,
                "error": f"Gmail HTTP {res.status_code}",
                "reason_code": "GMAIL_HTTP_ERROR",
            }
        return {
            "ok": True,
            "status": res.status_code,
            "data": data,
            "reason_code": "GMAIL_LIVE_OK",
        }
    except httpx.HTTPError as exc:
        return {
            "ok": False,
            "status": 0,
            "error": str(exc),
            "reason_code": "GMAIL_NETWORK_ERROR",
        }


def send_gmail_email(
    token: str | None,
    *,
    to: str,
    subject: str,
    body: str,
    **kwargs: Any,
) -> dict[str, Any]:
    return gmail_send(token, to=to, subject=subject, body=body, **kwargs)
