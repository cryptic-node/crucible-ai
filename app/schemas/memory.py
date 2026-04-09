from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


MEMORY_CLASSES = (
    "profile",
    "project",
    "task",
    "finance",
    "security",
    "ephemeral",
)

RETENTION_CLASSES = ("persistent", "session", "ephemeral")


class MemoryCreate(BaseModel):
    workspace_id: str
    memory_class: str = Field(..., description="One of: profile, project, task, finance, security, ephemeral")
    key: str
    value: str
    summary: Optional[str] = None
    trust_level: str = "MEDIUM"
    retention_class: str = "persistent"
    provenance: Dict[str, Any] = Field(default_factory=dict)
    is_secret: bool = False
    created_by: str = "system"
    session_id: Optional[str] = None
    source: Optional[str] = Field(None, description="Origin of the memory record (e.g. 'user', 'llm', 'tool', 'import')")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence score 0.0-1.0 for this memory record")
    timestamp: Optional[datetime] = Field(None, description="Explicit timestamp for the event represented (defaults to created_at)")
    content_type: str = Field("text", description="Content encoding hint: text, json, markdown, base64")


class MemoryRead(BaseModel):
    id: str
    workspace_id: str
    memory_class: str
    key: str
    value: str
    summary: Optional[str]
    trust_level: str
    retention_class: str
    provenance: Dict[str, Any]
    is_secret: bool
    created_at: datetime
    updated_at: datetime
    created_by: str
    session_id: Optional[str]
    source: Optional[str] = None
    confidence: float = 1.0
    timestamp: Optional[datetime] = None
    content_type: str = "text"

    model_config = {"from_attributes": True}


class MemorySearch(BaseModel):
    workspace_id: str
    query: str
    memory_class: Optional[str] = None
    limit: int = 10
    min_confidence: float = Field(0.0, ge=0.0, le=1.0)


class MemorySearchResult(BaseModel):
    record: MemoryRead
    score: float


class MemoryDeleteRequest(BaseModel):
    memory_id: str
    reason: str = ""
