from __future__ import annotations

"""
FastAPI DB dependency wiring.

Provides get_db() as an async dependency that yields an SQLAlchemy AsyncSession.
Falls back gracefully when DATABASE_URL is not configured or Postgres is unavailable.

Usage in routers:
    from ..db.deps import get_db, DBSession
    from sqlalchemy.ext.asyncio import AsyncSession

    @router.get("/example")
    async def example(db: DBSession):
        repo = WorkspaceRepository(db)
        ...
"""

from typing import AsyncGenerator, Optional

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

_session_factory = None
_db_available = False


def _get_factory():
    global _session_factory, _db_available
    if _session_factory is None:
        try:
            from .engine import session_factory
            _session_factory = session_factory()
            _db_available = True
        except Exception:
            _db_available = False
    return _session_factory


async def get_db() -> AsyncGenerator[Optional[AsyncSession], None]:
    """
    FastAPI dependency for async DB session.
    Yields a live AsyncSession when Postgres is reachable.
    Yields None when DB is unavailable (repositories fall back to in-memory).
    """
    factory = _get_factory()
    if factory is None or not _db_available:
        yield None
        return
    try:
        async with factory() as session:
            yield session
    except Exception:
        yield None


DBSession = Depends(get_db)
