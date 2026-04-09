from __future__ import annotations

"""
Database repository layer.
All repositories accept an optional async SQLAlchemy session.
When db_session is provided, operations are persisted to Postgres.
When db_session is None, operations fall back to process-level dicts (dev/test).
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..schemas.workspace import WorkspaceCreate, WorkspaceUpdate


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


_WORKSPACES: Dict[str, Dict[str, Any]] = {}
_SESSIONS: Dict[str, Dict[str, Any]] = {}
_AUDIT_RECORDS: List[Dict[str, Any]] = []


class WorkspaceRepository:
    """
    Workspace persistence.
    DB-backed when db_session is provided; process-dict otherwise.
    """

    def __init__(self, db_session=None) -> None:
        self._db = db_session

    async def create(self, body: WorkspaceCreate) -> Dict[str, Any]:
        ws_id = _new_id()
        if self._db is not None:
            from .models import Workspace
            ws = Workspace(
                id=ws_id,
                name=body.name,
                description=body.description or "",
                trust_level=body.trust_level,
                policy_yaml=getattr(body, "policy_yaml", None),
            )
            self._db.add(ws)
            await self._db.commit()
            await self._db.refresh(ws)
            record = _ws_to_dict(ws)
        else:
            record = {
                "id": ws_id,
                "name": body.name,
                "description": body.description or "",
                "trust_level": body.trust_level,
                "created_at": _now(),
                "updated_at": _now(),
            }
        _WORKSPACES[body.name] = record
        return record

    async def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        if self._db is not None:
            from .models import Workspace
            from sqlalchemy import select
            result = await self._db.execute(select(Workspace).where(Workspace.name == name))
            ws = result.scalar_one_or_none()
            if ws:
                record = _ws_to_dict(ws)
                _WORKSPACES[name] = record
                return record
            return None
        return _WORKSPACES.get(name)

    async def get_by_id(self, ws_id: str) -> Optional[Dict[str, Any]]:
        """Lookup workspace by UUID (for reverse resolution of name from DB UUID)."""
        for rec in _WORKSPACES.values():
            if rec.get("id") == ws_id:
                return rec
        if self._db is not None:
            from .models import Workspace
            from sqlalchemy import select
            result = await self._db.execute(select(Workspace).where(Workspace.id == ws_id))
            ws = result.scalar_one_or_none()
            if ws:
                record = _ws_to_dict(ws)
                _WORKSPACES[ws.name] = record
                return record
        return None

    async def get_id_by_name(self, name: str) -> Optional[str]:
        """Resolve workspace name to UUID for FK usage."""
        if name in _WORKSPACES:
            return _WORKSPACES[name]["id"]
        rec = await self.get_by_name(name)
        return rec["id"] if rec else None

    async def list_all(self) -> List[Dict[str, Any]]:
        if self._db is not None:
            from .models import Workspace
            from sqlalchemy import select
            result = await self._db.execute(select(Workspace))
            records = [_ws_to_dict(ws) for ws in result.scalars().all()]
            for r in records:
                _WORKSPACES[r["name"]] = r
            return records
        return list(_WORKSPACES.values())

    async def update(self, name: str, body: WorkspaceUpdate) -> Optional[Dict[str, Any]]:
        if self._db is not None:
            from .models import Workspace
            from sqlalchemy import select
            result = await self._db.execute(select(Workspace).where(Workspace.name == name))
            ws = result.scalar_one_or_none()
            if not ws:
                return None
            if body.description is not None:
                ws.description = body.description
            if body.trust_level is not None:
                ws.trust_level = body.trust_level
            if getattr(body, "policy_yaml", None) is not None:
                ws.policy_yaml = body.policy_yaml
            await self._db.commit()
            await self._db.refresh(ws)
            record = _ws_to_dict(ws)
            _WORKSPACES[name] = record
            return record

        rec = _WORKSPACES.get(name)
        if not rec:
            return None
        if body.description is not None:
            rec["description"] = body.description
        if body.trust_level is not None:
            rec["trust_level"] = body.trust_level
        rec["updated_at"] = _now()
        return rec


def _ws_to_dict(ws) -> Dict[str, Any]:
    return {
        "id": ws.id,
        "name": ws.name,
        "description": ws.description,
        "trust_level": ws.trust_level,
        "created_at": ws.created_at.isoformat() if ws.created_at else None,
        "updated_at": ws.updated_at.isoformat() if ws.updated_at else None,
    }


class SessionRepository:
    """
    Session persistence.
    DB-backed when db_session is provided; process-dict otherwise.
    Note: DB sessions store workspace_id as UUID resolved from workspace name.
    """

    def __init__(self, db_session=None) -> None:
        self._db = db_session

    async def create(
        self,
        session_id: str,
        workspace_id: str,
        channel: str,
        trust_level: str,
        dry_run: bool,
    ) -> Dict[str, Any]:
        rec = {
            "id": session_id,
            "workspace_id": workspace_id,
            "channel": channel,
            "trust_level": trust_level,
            "dry_run": dry_run,
            "messages": [],
            "created_at": _now(),
            "updated_at": _now(),
        }
        _SESSIONS[session_id] = rec

        if self._db is not None:
            ws_uuid = await self._resolve_workspace_uuid(workspace_id)
            if ws_uuid is not None:
                from .models import Session
                db_sess = Session(
                    id=session_id,
                    workspace_id=ws_uuid,
                    channel=channel,
                    trust_level=trust_level,
                    dry_run=dry_run,
                    messages=[],
                )
                self._db.add(db_sess)
                try:
                    await self._db.commit()
                except Exception:
                    await self._db.rollback()

        return rec

    async def _resolve_workspace_uuid(self, workspace_name_or_id: str) -> Optional[str]:
        """Resolve workspace name or UUID to DB workspace UUID."""
        from .models import Workspace
        from sqlalchemy import select
        result = await self._db.execute(
            select(Workspace).where(Workspace.name == workspace_name_or_id)
        )
        ws = result.scalar_one_or_none()
        if ws:
            return ws.id
        result2 = await self._db.execute(
            select(Workspace).where(Workspace.id == workspace_name_or_id)
        )
        ws2 = result2.scalar_one_or_none()
        return ws2.id if ws2 else None

    async def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        if self._db is not None:
            from .models import Session
            from sqlalchemy import select
            result = await self._db.execute(select(Session).where(Session.id == session_id))
            s = result.scalar_one_or_none()
            if s:
                return {
                    "id": s.id,
                    "workspace_id": s.workspace_id,
                    "channel": s.channel,
                    "trust_level": s.trust_level,
                    "dry_run": s.dry_run,
                    "messages": s.messages or [],
                }
        return _SESSIONS.get(session_id)

    async def persist_messages(self, session_id: str, messages: list) -> None:
        if session_id in _SESSIONS:
            _SESSIONS[session_id]["messages"] = messages
            _SESSIONS[session_id]["updated_at"] = _now()

        if self._db is not None:
            from .models import Session
            from sqlalchemy import select
            result = await self._db.execute(select(Session).where(Session.id == session_id))
            s = result.scalar_one_or_none()
            if s:
                s.messages = messages
                try:
                    await self._db.commit()
                except Exception:
                    await self._db.rollback()


class AuditRepository:
    """
    AuditLog persistence.
    DB-backed when db_session is provided; in-memory list otherwise.
    Workspace attribution: resolves workspace name to UUID for FK field.
    """

    def __init__(self, db_session=None) -> None:
        self._db = db_session

    async def write(self, record: Dict[str, Any]) -> None:
        _AUDIT_RECORDS.append(record)

        if self._db is not None:
            workspace_name = record.get("workspace")
            workspace_uuid: Optional[str] = None
            if workspace_name:
                ws_repo = WorkspaceRepository(db_session=self._db)
                workspace_uuid = await ws_repo.get_id_by_name(workspace_name)

            from .models import AuditLog
            entry = AuditLog(
                id=_new_id(),
                workspace_id=workspace_uuid,
                actor=record.get("actor", "unknown"),
                action=record.get("action", "unknown"),
                tool_name=record.get("tool_name"),
                input_hash=record.get("input_hash"),
                policy_decision=record.get("policy_decision", "unknown"),
                approval_status=record.get("approval_status", "not_required"),
                dry_run=record.get("dry_run", False),
                result_summary=(record.get("result_summary") or "")[:2000],
                error=record.get("error"),
                correlation_id=record.get("correlation_id", _new_id()),
            )
            self._db.add(entry)
            try:
                await self._db.commit()
            except Exception:
                await self._db.rollback()

    def get_records(self) -> List[Dict[str, Any]]:
        return list(_AUDIT_RECORDS)
