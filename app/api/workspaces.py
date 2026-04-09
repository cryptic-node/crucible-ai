from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.trust import WORKSPACE_TRUST_DEFAULTS
from ..db.deps import get_db
from ..db.repository import WorkspaceRepository
from ..schemas.workspace import WorkspaceCreate, WorkspaceUpdate

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

_seeded = False


async def _seed_defaults(repo: WorkspaceRepository) -> None:
    global _seeded
    if _seeded:
        return
    existing = await repo.list_all()
    existing_names = {w["name"] for w in existing}
    for name, trust in WORKSPACE_TRUST_DEFAULTS.items():
        if name not in existing_names:
            await repo.create(WorkspaceCreate(
                name=name,
                description=f"{name.capitalize()} workspace",
                trust_level=trust.value,
            ))
    _seeded = True


@router.get("", response_model=List[Dict[str, Any]])
async def list_workspaces(
    db: Optional[AsyncSession] = Depends(get_db),
) -> List[Dict[str, Any]]:
    repo = WorkspaceRepository(db_session=db)
    await _seed_defaults(repo)
    return await repo.list_all()


@router.post("", response_model=Dict[str, Any])
async def create_workspace(
    body: WorkspaceCreate,
    db: Optional[AsyncSession] = Depends(get_db),
) -> Dict[str, Any]:
    repo = WorkspaceRepository(db_session=db)
    await _seed_defaults(repo)
    existing = await repo.get_by_name(body.name)
    if existing:
        raise HTTPException(status_code=409, detail=f"Workspace '{body.name}' already exists")
    return await repo.create(body)


@router.get("/{name}", response_model=Dict[str, Any])
async def get_workspace(
    name: str,
    db: Optional[AsyncSession] = Depends(get_db),
) -> Dict[str, Any]:
    repo = WorkspaceRepository(db_session=db)
    await _seed_defaults(repo)
    ws = await repo.get_by_name(name)
    if not ws:
        raise HTTPException(status_code=404, detail=f"Workspace not found: {name}")
    return ws


@router.patch("/{name}", response_model=Dict[str, Any])
async def update_workspace(
    name: str,
    body: WorkspaceUpdate,
    db: Optional[AsyncSession] = Depends(get_db),
) -> Dict[str, Any]:
    repo = WorkspaceRepository(db_session=db)
    result = await repo.update(name, body)
    if not result:
        raise HTTPException(status_code=404, detail=f"Workspace not found: {name}")
    return result
