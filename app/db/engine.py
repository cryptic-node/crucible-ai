from __future__ import annotations

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from ..core.config import get_settings


class Base(DeclarativeBase):
    pass


def get_engine():
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_pre_ping=True,
    )


def get_session_factory(engine=None):
    if engine is None:
        engine = get_engine()
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


_engine = None
_session_factory = None


def engine():
    global _engine
    if _engine is None:
        _engine = get_engine()
    return _engine


def session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = get_session_factory(engine())
    return _session_factory


async def get_db():
    """FastAPI dependency for DB session."""
    async with session_factory()() as session:
        yield session


async def init_db():
    """Initialize DB: create tables and pgvector extension."""
    from . import models  # noqa: F401 - register models
    async with engine().begin() as conn:
        await conn.execute(
            __import__("sqlalchemy", fromlist=["text"]).text("CREATE EXTENSION IF NOT EXISTS vector")
        )
        await conn.run_sync(Base.metadata.create_all)
