from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..brain.brain import BrainSession
from ..core.trust import TrustLevel, get_workspace_trust
from ..db.deps import get_db
from ..db.repository import SessionRepository, WorkspaceRepository
from ..schemas.session import SessionCreate

router = APIRouter(prefix="/sessions", tags=["sessions"])

_active_sessions: Dict[str, BrainSession] = {}


def _make_repo(db: Optional[AsyncSession]) -> SessionRepository:
    return SessionRepository(db_session=db)


def _make_ws_repo(db: Optional[AsyncSession]) -> WorkspaceRepository:
    return WorkspaceRepository(db_session=db)


async def _resolve_workspace_name(workspace_id_or_name: str, db: Optional[AsyncSession]) -> str:
    """
    Ensure we always work with workspace name (not UUID) for policy enforcement.
    If the value looks like a UUID and DB is available, resolve it back to a name.
    """
    import re
    UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
    if UUID_PATTERN.match(workspace_id_or_name) and db is not None:
        ws_repo = _make_ws_repo(db)
        rec = await ws_repo.get_by_id(workspace_id_or_name)
        if rec:
            return rec["name"]
    return workspace_id_or_name


async def get_or_restore_session(session_id: str, db: Optional[AsyncSession]) -> Optional[BrainSession]:
    """Return active BrainSession or attempt to restore from persistent store."""
    if session_id in _active_sessions:
        return _active_sessions[session_id]
    repo = _make_repo(db)
    rec = await repo.get(session_id)
    if not rec:
        return None
    workspace_name = await _resolve_workspace_name(rec.get("workspace_id", "personal"), db)
    session = BrainSession(
        session_id=session_id,
        workspace=workspace_name,
        channel=rec.get("channel", "web"),
        trust_level=rec.get("trust_level", "MEDIUM"),
        dry_run=rec.get("dry_run", False),
        db=db,
    )
    session.messages = rec.get("messages", [])
    _active_sessions[session_id] = session
    return session


@router.post("", response_model=Dict[str, str])
async def create_session(
    body: SessionCreate,
    db: Optional[AsyncSession] = Depends(get_db),
) -> Dict[str, str]:
    session_id = str(uuid.uuid4())
    trust_level = body.trust_level
    if not any(trust_level == t.value for t in TrustLevel):
        trust_level = get_workspace_trust(body.workspace_id).value

    session = BrainSession(
        session_id=session_id,
        workspace=body.workspace_id,
        channel=body.channel,
        trust_level=trust_level,
        dry_run=body.dry_run,
        db=db,
    )
    _active_sessions[session_id] = session

    repo = _make_repo(db)
    await repo.create(
        session_id=session_id,
        workspace_id=body.workspace_id,
        channel=body.channel,
        trust_level=trust_level,
        dry_run=body.dry_run,
    )

    return {"session_id": session_id, "workspace_id": body.workspace_id}


@router.get("", response_model=List[Dict[str, Any]])
async def list_sessions() -> List[Dict[str, Any]]:
    return [
        {
            "session_id": s.session_id,
            "workspace": s.workspace,
            "channel": s.channel,
            "trust_level": s.trust_level,
            "message_count": len(s.messages),
        }
        for s in _active_sessions.values()
    ]


@router.get("/{session_id}", response_model=Dict[str, Any])
async def get_session(
    session_id: str,
    db: Optional[AsyncSession] = Depends(get_db),
) -> Dict[str, Any]:
    session = await get_or_restore_session(session_id, db)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return {
        "session_id": session.session_id,
        "workspace": session.workspace,
        "channel": session.channel,
        "trust_level": session.trust_level,
        "dry_run": session.dry_run,
        "messages": session.messages,
        "tool_calls": session.tool_calls,
        "policy_decisions": session.policy_decisions,
    }


async def persist_session(session: BrainSession, db: Optional[AsyncSession]) -> None:
    """Persist session messages to DB."""
    repo = _make_repo(db)
    await repo.persist_messages(session.session_id, session.messages)
