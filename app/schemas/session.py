from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    workspace_id: str
    channel: str = "web"
    trust_level: str = "MEDIUM"
    dry_run: bool = False


class SessionRead(BaseModel):
    id: str
    workspace_id: str
    backend_used: str
    model_used: str
    messages: List[Dict[str, Any]]
    input_tokens: int
    output_tokens: int
    trust_level: str
    channel: str
    dry_run: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    session_id: str
    message: str
    dry_run: bool = False


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    backend_used: str
    model_used: str
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    policy_decisions: List[Dict[str, Any]] = Field(default_factory=list)
    dry_run: bool = False
