from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class WorkspaceCreate(BaseModel):
    name: str
    description: str = ""
    trust_level: str = "MEDIUM"
    policy_yaml: Optional[str] = None


class WorkspaceRead(BaseModel):
    id: str
    name: str
    description: str
    trust_level: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkspaceUpdate(BaseModel):
    description: Optional[str] = None
    trust_level: Optional[str] = None
    policy_yaml: Optional[str] = None
