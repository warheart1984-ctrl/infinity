from fastapi import Header, HTTPException, Request, WebSocket
from app.config import APP_BEARER_TOKEN
from src.transcription_policy import (
    TranscriptionAccessDenied,
    TranscriptionRateLimited,
    enforce_transcription_rate_limit,
    require_transcription_access as enforce_transcription_access,
)

def require_token(authorization: str | None = Header(default=None)):
    if not APP_BEARER_TOKEN:
        return
    expected = f"Bearer {APP_BEARER_TOKEN}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

def check_sse_token(request: Request) -> None:
    if not APP_BEARER_TOKEN:
        return
    token = request.query_params.get("token", "")
    if token != APP_BEARER_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

async def check_ws_token(websocket: WebSocket) -> None:
    if not APP_BEARER_TOKEN:
        return
    token = websocket.query_params.get("token", "")
    if token != APP_BEARER_TOKEN:
        await websocket.close(code=4401)
        raise RuntimeError("Unauthorized websocket")


def require_transcription_token(
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    """Protect transcription while retaining trusted loopback operation."""
    try:
        enforce_transcription_access(
            authorization=authorization,
            client_host=request.client.host if request.client else None,
            forwarded_for=request.headers.get("x-forwarded-for"),
        )
        enforce_transcription_rate_limit(
            authorization=authorization,
            client_host=request.client.host if request.client else None,
            forwarded_for=request.headers.get("x-forwarded-for"),
        )
    except TranscriptionAccessDenied as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except TranscriptionRateLimited as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
