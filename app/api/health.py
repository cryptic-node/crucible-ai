from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "Grokenstein", "version": "1.0.0"}


@router.get("/")
async def root() -> dict:
    return {
        "service": "Grokenstein API",
        "version": "1.0.0",
        "docs": "/docs",
        "chat_ui": "/ui",
    }
