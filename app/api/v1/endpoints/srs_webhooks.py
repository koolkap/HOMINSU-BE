"""SRS http_hooks callbacks.

SRS POSTs callbacks (JSON or form-encoded). A stream is published to
rtmp://host:1935/live/<stream_key>, so the stream key is the last path segment
of the `stream` / `stream_url` field. SRS accepts the publish only when we
answer HTTP 200 with body {"code": 0}.
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.content import Content
from app.websockets.connection_manager import manager

logger = logging.getLogger("hominsh.srs")

router = APIRouter(prefix="/srs", tags=["srs"])


async def _parse_body(request: Request) -> dict:
    body: dict = {}
    try:
        body = await request.json()
        if not isinstance(body, dict):
            body = {}
    except Exception:
        try:
            form = await request.form()
            body = dict(form)
        except Exception:
            body = {}
    return body


def _extract_stream_key(body: dict) -> str | None:
    stream = body.get("stream") or body.get("stream_url")
    if not stream:
        return None
    return str(stream).rstrip("/").rsplit("/", 1)[-1]


def _srs_ok() -> JSONResponse:
    return JSONResponse({"code": 0})


@router.post("/on_publish")
async def on_publish(request: Request) -> JSONResponse:
    """Insta360 camera started streaming: mark content live and notify viewers."""
    body = await _parse_body(request)
    stream_key = _extract_stream_key(body)
    hls_url = f"{settings.SRS_HLS_BASE_URL}/live/{stream_key}.m3u8"

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Content).where(Content.stream_key == stream_key))
        content = result.scalar_one_or_none()
        if content is None:
            logger.warning("on_publish for unknown stream_key=%s", stream_key)
        else:
            content.is_live = True
            content.media_url = hls_url
            await db.commit()

    await manager.broadcast_to_operators(
        {
            "event": "live_started",
            "stream_key": stream_key,
            "content_id": str(content.id) if content else None,
            "title": content.title if content else None,
            "hls_url": hls_url,
        }
    )
    return _srs_ok()


@router.post("/on_unpublish")
async def on_unpublish(request: Request) -> JSONResponse:
    """Camera stopped streaming: mark content offline and notify viewers."""
    body = await _parse_body(request)
    stream_key = _extract_stream_key(body)

    content = None
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Content).where(Content.stream_key == stream_key))
        content = result.scalar_one_or_none()
        if content is not None:
            content.is_live = False
            await db.commit()

    await manager.broadcast_to_operators(
        {
            "event": "live_stopped",
            "stream_key": stream_key,
            "content_id": str(content.id) if content else None,
        }
    )
    return _srs_ok()
