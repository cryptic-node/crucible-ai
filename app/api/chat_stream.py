from __future__ import annotations

"""
Server-Sent Events (SSE) streaming chat endpoint.

Streams the assistant reply token-by-token (or chunk-by-chunk).
When no LLM is available, streams the stub reply in chunks.
"""

import asyncio
import json
from typing import AsyncIterator, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..brain.brain import get_brain
from ..db.deps import get_db
from ..schemas.session import ChatRequest

router = APIRouter(prefix="/chat/stream", tags=["chat"])


async def _stream_text(text: str, chunk_size: int = 20) -> AsyncIterator[str]:
    """Yield SSE events for a text string, split into chunks."""
    for i in range(0, len(text), chunk_size):
        chunk = text[i: i + chunk_size]
        data = json.dumps({"delta": chunk, "done": False})
        yield f"data: {data}\n\n"
        await asyncio.sleep(0)
    done_data = json.dumps({"delta": "", "done": True})
    yield f"data: {done_data}\n\n"


@router.post("")
async def stream_message(
    body: ChatRequest,
    db: Optional[AsyncSession] = Depends(get_db),
) -> StreamingResponse:
    """
    SSE streaming chat endpoint.
    Emits chunks as: data: {"delta": "...", "done": false}
    Final event:    data: {"delta": "", "done": true}
    """
    from .sessions import get_or_restore_session, persist_session

    session = await get_or_restore_session(body.session_id, db)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {body.session_id}")

    if body.dry_run:
        session.dry_run = True

    session.db = db
    brain = get_brain()

    reply = await brain.chat_async(session, body.message)

    await persist_session(session, db)

    return StreamingResponse(
        _stream_text(reply),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
