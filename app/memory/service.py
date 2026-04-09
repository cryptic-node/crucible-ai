from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..schemas.memory import MemoryCreate, MemoryRead, MemorySearch, MemorySearchResult


def _stub_embed(text: str, dim: int = 1536) -> List[float]:
    """Deterministic stub embedding — replace with real model for semantic search."""
    h = hashlib.sha256(text.encode()).digest()
    base = [((b / 255.0) * 2 - 1) for b in h]
    return (base * (dim // len(base) + 1))[:dim]


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class MemoryService:
    """Abstract base for Memory Service implementations."""

    def create(self, record: MemoryCreate) -> MemoryRead:
        raise NotImplementedError

    def get(self, record_id: str, workspace_id: str) -> Optional[MemoryRead]:
        raise NotImplementedError

    def list(self, workspace_id: str, memory_class: Optional[str] = None, limit: int = 50) -> List[MemoryRead]:
        raise NotImplementedError

    def delete(self, record_id: str, workspace_id: str, reason: str = "") -> bool:
        raise NotImplementedError

    def search(self, request: MemorySearch) -> List[MemorySearchResult]:
        raise NotImplementedError

    def compact_ephemeral(self, workspace_id: str) -> int:
        raise NotImplementedError


class InMemoryMemoryService(MemoryService):
    """In-memory Memory Service for development and testing."""

    def __init__(self, embedding_dim: int = 1536) -> None:
        self._records: Dict[str, Dict[str, Any]] = {}
        self._dim = embedding_dim

    def create(self, record: MemoryCreate) -> MemoryRead:
        if record.is_secret:
            raise ValueError("Secrets must not be stored in the memory service.")
        rec_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        embedding = _stub_embed(record.value, self._dim)
        data = {
            "id": rec_id,
            "workspace_id": record.workspace_id,
            "memory_class": record.memory_class,
            "key": record.key,
            "value": record.value,
            "summary": record.summary,
            "trust_level": record.trust_level,
            "retention_class": record.retention_class,
            "provenance": record.provenance,
            "is_secret": False,
            "expires_at": None,
            "created_at": now,
            "updated_at": now,
            "created_by": record.created_by,
            "session_id": record.session_id,
            "source": record.source,
            "confidence": record.confidence,
            "timestamp": record.timestamp or now,
            "content_type": record.content_type,
            "_embedding": embedding,
        }
        self._records[rec_id] = data
        return _to_schema(data)

    def get(self, record_id: str, workspace_id: str) -> Optional[MemoryRead]:
        data = self._records.get(record_id)
        if not data or data["workspace_id"] != workspace_id:
            return None
        return _to_schema(data)

    def list(self, workspace_id: str, memory_class: Optional[str] = None, limit: int = 50) -> List[MemoryRead]:
        results = []
        for data in self._records.values():
            if data["workspace_id"] != workspace_id:
                continue
            if memory_class and data["memory_class"] != memory_class:
                continue
            results.append(_to_schema(data))
        return results[:limit]

    def delete(self, record_id: str, workspace_id: str, reason: str = "") -> bool:
        data = self._records.get(record_id)
        if not data or data["workspace_id"] != workspace_id:
            return False
        del self._records[record_id]
        return True

    def search(self, request: MemorySearch) -> List[MemorySearchResult]:
        query_embedding = _stub_embed(request.query, self._dim)
        results = []
        for data in self._records.values():
            if data["workspace_id"] != request.workspace_id:
                continue
            if request.memory_class and data["memory_class"] != request.memory_class:
                continue
            if data.get("confidence", 1.0) < request.min_confidence:
                continue
            score = _cosine_similarity(query_embedding, data.get("_embedding", [0.0] * self._dim))
            results.append(MemorySearchResult(record=_to_schema(data), score=score))
        results.sort(key=lambda r: r.score, reverse=True)
        return results[: request.limit]

    def compact_ephemeral(self, workspace_id: str) -> int:
        to_delete = [
            rid for rid, data in self._records.items()
            if data["workspace_id"] == workspace_id and data["retention_class"] == "ephemeral"
        ]
        for rid in to_delete:
            del self._records[rid]
        return len(to_delete)


def _to_schema(data: Dict[str, Any]) -> MemoryRead:
    return MemoryRead(
        id=data["id"],
        workspace_id=data["workspace_id"],
        memory_class=data["memory_class"],
        key=data["key"],
        value=data["value"],
        summary=data.get("summary"),
        trust_level=data["trust_level"],
        retention_class=data["retention_class"],
        provenance=data.get("provenance", {}),
        is_secret=data.get("is_secret", False),
        created_at=data["created_at"],
        updated_at=data["updated_at"],
        created_by=data.get("created_by", "system"),
        session_id=data.get("session_id"),
        source=data.get("source"),
        confidence=data.get("confidence", 1.0),
        timestamp=data.get("timestamp"),
        content_type=data.get("content_type", "text"),
    )


class PostgresMemoryService(MemoryService):
    """
    PostgreSQL + pgvector-backed persistent Memory Service.

    workspace_id in MemoryCreate may be a workspace name or UUID.
    This service resolves names to UUIDs via the DB before insert.
    All operations are workspace-scoped and write through to Postgres.
    """

    def __init__(self, db_session, embedding_dim: int = 1536) -> None:
        self._db = db_session
        self._dim = embedding_dim

    async def _resolve_workspace_uuid(self, workspace_name_or_id: str) -> Optional[str]:
        """Resolve workspace name or UUID to DB workspace UUID for FK constraint."""
        from ..db.models import Workspace
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

    async def _get_embedding(self, text: str) -> List[float]:
        return _stub_embed(text, self._dim)

    async def create(self, record: MemoryCreate) -> MemoryRead:  # type: ignore[override]
        if record.is_secret:
            raise ValueError("Secrets must not be stored in the memory service.")
        from ..db.models import MemoryRecord

        workspace_uuid = await self._resolve_workspace_uuid(record.workspace_id)
        if workspace_uuid is None:
            raise ValueError(f"Workspace not found: {record.workspace_id!r}")

        embedding = await self._get_embedding(record.value)
        rec_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        db_rec = MemoryRecord(
            id=rec_id,
            workspace_id=workspace_uuid,
            memory_class=record.memory_class,
            key=record.key,
            value=record.value,
            summary=record.summary,
            trust_level=record.trust_level,
            retention_class=record.retention_class,
            provenance=record.provenance,
            is_secret=False,
            created_by=record.created_by,
            session_id=record.session_id,
            source=record.source,
            confidence=record.confidence,
            timestamp=record.timestamp or now,
            content_type=record.content_type,
            embedding=embedding,
        )
        self._db.add(db_rec)
        await self._db.commit()
        await self._db.refresh(db_rec)
        return _db_to_schema(db_rec, workspace_name=record.workspace_id)

    async def get(self, record_id: str, workspace_id: str) -> Optional[MemoryRead]:  # type: ignore[override]
        from sqlalchemy import select
        from ..db.models import MemoryRecord
        workspace_uuid = await self._resolve_workspace_uuid(workspace_id)
        if workspace_uuid is None:
            return None
        result = await self._db.execute(
            select(MemoryRecord).where(
                MemoryRecord.id == record_id,
                MemoryRecord.workspace_id == workspace_uuid,
            )
        )
        rec = result.scalar_one_or_none()
        return _db_to_schema(rec, workspace_name=workspace_id) if rec else None

    async def list(self, workspace_id: str, memory_class: Optional[str] = None, limit: int = 50) -> List[MemoryRead]:  # type: ignore[override]
        from sqlalchemy import select
        from ..db.models import MemoryRecord
        workspace_uuid = await self._resolve_workspace_uuid(workspace_id)
        if workspace_uuid is None:
            return []
        q = select(MemoryRecord).where(MemoryRecord.workspace_id == workspace_uuid)
        if memory_class:
            q = q.where(MemoryRecord.memory_class == memory_class)
        q = q.limit(limit)
        result = await self._db.execute(q)
        return [_db_to_schema(r, workspace_name=workspace_id) for r in result.scalars().all()]

    async def delete(self, record_id: str, workspace_id: str, reason: str = "") -> bool:  # type: ignore[override]
        from sqlalchemy import select
        from ..db.models import MemoryRecord
        workspace_uuid = await self._resolve_workspace_uuid(workspace_id)
        if workspace_uuid is None:
            return False
        result = await self._db.execute(
            select(MemoryRecord).where(
                MemoryRecord.id == record_id,
                MemoryRecord.workspace_id == workspace_uuid,
            )
        )
        rec = result.scalar_one_or_none()
        if not rec:
            return False
        await self._db.delete(rec)
        await self._db.commit()
        return True

    async def search(self, request: MemorySearch) -> List[MemorySearchResult]:  # type: ignore[override]
        from sqlalchemy import select
        from ..db.models import MemoryRecord
        workspace_uuid = await self._resolve_workspace_uuid(request.workspace_id)
        if workspace_uuid is None:
            return []
        query_embedding = await self._get_embedding(request.query)
        q = select(MemoryRecord).where(MemoryRecord.workspace_id == workspace_uuid)
        if request.memory_class:
            q = q.where(MemoryRecord.memory_class == request.memory_class)
        if request.min_confidence > 0.0:
            q = q.where(MemoryRecord.confidence >= request.min_confidence)
        q = q.limit(request.limit * 5)
        result = await self._db.execute(q)
        records = result.scalars().all()
        scored = []
        for rec in records:
            emb = rec.embedding if isinstance(rec.embedding, list) else []
            score = _cosine_similarity(query_embedding, emb) if emb else 0.0
            scored.append(MemorySearchResult(record=_db_to_schema(rec, workspace_name=request.workspace_id), score=score))
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[: request.limit]

    async def compact_ephemeral(self, workspace_id: str) -> int:  # type: ignore[override]
        from sqlalchemy import select
        from ..db.models import MemoryRecord
        workspace_uuid = await self._resolve_workspace_uuid(workspace_id)
        if workspace_uuid is None:
            return 0
        result = await self._db.execute(
            select(MemoryRecord).where(
                MemoryRecord.workspace_id == workspace_uuid,
                MemoryRecord.retention_class == "ephemeral",
            )
        )
        records = result.scalars().all()
        for rec in records:
            await self._db.delete(rec)
        await self._db.commit()
        return len(records)


def _db_to_schema(rec, workspace_name: Optional[str] = None) -> MemoryRead:
    """Convert DB MemoryRecord to MemoryRead, using workspace_name if available."""
    return MemoryRead(
        id=rec.id,
        workspace_id=workspace_name or rec.workspace_id,
        memory_class=rec.memory_class,
        key=rec.key,
        value=rec.value,
        summary=rec.summary,
        trust_level=rec.trust_level,
        retention_class=rec.retention_class,
        provenance=rec.provenance or {},
        is_secret=rec.is_secret,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
        created_by=rec.created_by,
        session_id=rec.session_id,
        source=getattr(rec, "source", None),
        confidence=getattr(rec, "confidence", 1.0),
        timestamp=getattr(rec, "timestamp", None),
        content_type=getattr(rec, "content_type", "text"),
    )


_memory_service: Optional[MemoryService] = None


def get_memory_service() -> MemoryService:
    global _memory_service
    if _memory_service is None:
        _memory_service = InMemoryMemoryService()
    return _memory_service


def reset_memory_service(instance: Optional[MemoryService] = None) -> None:
    global _memory_service
    _memory_service = instance
