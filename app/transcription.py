"""Native FastAPI transport for the bounded Jarvis transcription capability."""

from __future__ import annotations

from functools import partial
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.auth import require_transcription_token
from src.transcription_policy import (
    AudioValidationError,
    AudioUploadTooLarge,
    READ_CHUNK_BYTES,
    build_transcription_error_receipt,
    max_audio_bytes,
    validate_pcm16_wav,
    validate_wav_content_type,
)
from src.transcription_service import transcribe_audio_with_shadow


logger = logging.getLogger(__name__)
router = APIRouter(tags=["audio"])


async def _read_upload_bounded(audio: UploadFile, *, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await audio.read(min(READ_CHUNK_BYTES, limit - total + 1))
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        total += len(chunk)
        if total > limit:
            raise AudioUploadTooLarge(limit)


@router.post(
    "/api/audio/transcribe",
    dependencies=[Depends(require_transcription_token)],
)
async def transcribe_audio(
    audio: Annotated[UploadFile | None, File()] = None,
    language: Annotated[str | None, Form()] = None,
):
    """Transcribe an upload without blocking the FastAPI event loop."""
    if audio is None:
        return JSONResponse({"error": "Audio file is required"}, status_code=400)

    filename = audio.filename or "audio.wav"
    content_type = audio.content_type
    try:
        validate_wav_content_type(content_type, filename)
        audio_bytes = await _read_upload_bounded(audio, limit=max_audio_bytes())
        validate_pcm16_wav(
            audio_bytes,
            content_type=content_type,
            filename=filename,
        )
        result = await run_in_threadpool(
            partial(
                transcribe_audio_with_shadow,
                audio_bytes,
                filename=filename,
                language=language,
                content_type=content_type or "audio/wav",
            )
        )
        return JSONResponse(result)
    except AudioValidationError as exc:
        receipt = build_transcription_error_receipt(
            exc,
            filename=filename,
            content_type=content_type,
            audio_bytes=locals().get("audio_bytes"),
        )
        logger.warning(
            "transcription_audit event=upload_refused code=%s receipt_id=%s",
            exc.code,
            receipt["receiptId"],
        )
        return JSONResponse(
            {"error": str(exc), "receipt": receipt},
            status_code=exc.status_code,
        )
    except AudioUploadTooLarge as exc:
        return JSONResponse(
            {"error": str(exc), "max_audio_bytes": exc.max_audio_bytes},
            status_code=413,
        )
    except Exception as exc:
        logger.error("Error in transcribe_audio: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)
    finally:
        await audio.close()
