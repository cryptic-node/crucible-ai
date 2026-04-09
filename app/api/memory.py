from __future__ import annotations

import inspect
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.deps import get_db
from ..memory.service import InMemoryMemoryService, PostgresMemoryService, get_memory_service
from ..schemas.memory import MemoryCreate, MemoryRead, MemorySearch, MemorySearchResult

router = APIRouter(prefix="/memory", tags=["memory"])


def _get_svc(db: Optional[AsyncSession]):
    """
    Return a PostgresMemoryService when a live DB session is available;
    fall back to the process-scoped InMemoryMemoryService otherwise.
    """
    if db is not None:
        return PostgresMemoryService(db)
    return get_memory_service()


@router.post("", response_model=MemoryRead)
async def create_memory(
    body: MemoryCreate,
    db: Optional[AsyncSession] = Depends(get_db),
) -> MemoryRead:
    svc = _get_svc(db)
    try:
        result = svc.create(body)
        if inspect.isawaitable(result):
            result = await result
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{workspace_id}", response_model=List[MemoryRead])
async def list_memory(
    workspace_id: str,
    memory_class: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    db: Optional[AsyncSession] = Depends(get_db),
) -> List[MemoryRead]:
    svc = _get_svc(db)
    result = svc.list(workspace_id, memory_class=memory_class, limit=limit)
    if inspect.isawaitable(result):
        result = await result
    return result


@router.get("/{workspace_id}/{record_id}", response_model=MemoryRead)
async def get_memory(
    workspace_id: str,
    record_id: str,
    db: Optional[AsyncSession] = Depends(get_db),
) -> MemoryRead:
    svc = _get_svc(db)
    result = svc.get(record_id, workspace_id)
    if inspect.isawaitable(result):
        result = await result
    if not result:
        raise HTTPException(status_code=404, detail=f"Memory record not found: {record_id}")
    return result


@router.post("/search", response_model=List[MemorySearchResult])
async def search_memory(
    body: MemorySearch,
    db: Optional[AsyncSession] = Depends(get_db),
) -> List[MemorySearchResult]:
    svc = _get_svc(db)
    result = svc.search(body)
    if inspect.isawaitable(result):
        result = await result
    return result


@router.delete("/{workspace_id}/{record_id}")
async def delete_memory(
    workspace_id: str,
    record_id: str,
    reason: str = "",
    db: Optional[AsyncSession] = Depends(get_db),
) -> Dict[str, Any]:
    svc = _get_svc(db)
    deleted = svc.delete(record_id, workspace_id, reason=reason)
    if inspect.isawaitable(deleted):
        deleted = await deleted
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Memory record not found: {record_id}")
    return {"deleted": True, "record_id": record_id, "reason": reason}


@router.post("/review/compact")
async def compact_ephemeral(
    workspace_id: str,
    db: Optional[AsyncSession] = Depends(get_db),
) -> Dict[str, Any]:
    svc = _get_svc(db)
    count = svc.compact_ephemeral(workspace_id)
    if inspect.isawaitable(count):
        count = await count
    return {"workspace_id": workspace_id, "deleted_ephemeral": count}
