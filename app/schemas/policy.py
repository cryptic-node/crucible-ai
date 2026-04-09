from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class PolicyDecisionEnum(str, Enum):
    allow = "allow"
    deny = "deny"
    require_approval = "require_approval"
    require_simulation = "require_simulation"
    escalate_channel = "escalate_channel"


class PolicyRequest(BaseModel):
    workspace: str
    channel: str
    trust_level: str
    tool_name: Optional[str] = None
    action_type: str = "generic"
    risk_level: str = "low"
    dry_run: bool = False
    input_data: Optional[Dict[str, Any]] = None


class PolicyDecision(BaseModel):
    decision: PolicyDecisionEnum
    explanation: str
    workspace: str
    tool_name: Optional[str] = None
    action_type: str
    risk_level: str
    dry_run: bool
    kill_switch_active: bool = False
    correlation_id: Optional[str] = None
