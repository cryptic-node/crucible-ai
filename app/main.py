from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import health, sessions, chat, chat_stream, workspaces, memory
from .core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Grokenstein",
    description="Security-first, privacy-focused personal operator AI — v1.0.0",
    version="1.0.0",
)

_CORS_ORIGINS = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:3000",
]
if settings.debug:
    _CORS_ORIGINS.extend(["http://localhost:*", "http://127.0.0.1:*"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize DB and load policy overrides on startup."""
    import logging
    log = logging.getLogger("grokenstein.startup")
    try:
        from .db.engine import init_db, session_factory
        await init_db()
        async with session_factory()() as db:
            from .policy.engine import load_policy_overrides_from_db
            await load_policy_overrides_from_db(db)
    except Exception as exc:
        log.warning(f"DB initialization skipped (no live DB): {exc}")


app.include_router(health.router)
app.include_router(sessions.router)
app.include_router(chat_stream.router)
app.include_router(chat.router)
app.include_router(workspaces.router)
app.include_router(memory.router)

ui_dir = Path(__file__).parent / "ui" / "static"
if ui_dir.exists():
    app.mount("/ui", StaticFiles(directory=str(ui_dir), html=True), name="ui")
