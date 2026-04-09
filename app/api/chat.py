from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..brain.brain import get_brain
from ..db.deps import get_db
from ..schemas.session import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def send_message(
    body: ChatRequest,
    db: Optional[AsyncSession] = Depends(get_db),
) -> ChatResponse:
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

    backend_name = "unknown"
    if brain._router:
        try:
            backend_name = brain._router.select_backend({}).name
        except Exception:
            pass

    return ChatResponse(
        session_id=body.session_id,
        reply=reply,
        backend_used=backend_name,
        model_used="unknown",
        tool_calls=session.tool_calls[-5:] if session.tool_calls else [],
        policy_decisions=session.policy_decisions[-5:] if session.policy_decisions else [],
        dry_run=session.dry_run,
    )
