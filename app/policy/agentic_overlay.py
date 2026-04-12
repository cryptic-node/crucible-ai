from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Iterable, Optional, Set

from pydantic import BaseModel, Field

from ..schemas.policy import PolicyDecision, PolicyDecisionEnum, PolicyRequest


class AgentMode(str, Enum):
    interactive = "interactive"
    observer = "observer"
    curator = "curator"
    operator = "operator"


class AgenticContext(BaseModel):
    mode: AgentMode = AgentMode.interactive
    step_up_verified: bool = False
    pack_name: Optional[str] = None
    tool_call_budget_remaining: int = Field(25, ge=0)
    write_budget_remaining: int = Field(0, ge=0)
    notes: Optional[str] = None


READ_ACTIONS: Set[str] = {"read", "list", "search", "generic"}
WRITE_ACTIONS: Set[str] = {"write", "delete", "execute", "publish", "sign", "pay"}
DANGEROUS_TOOLS: Set[str] = {
    "shell",
    "bash",
    "filesystem_write",
    "bitcoin_pay",
    "lightning_pay",
    "nostr_publish",
    "nostr_sign",
    "identity_update",
}
CURATOR_DRAFT_TOOLS: Set[str] = {
    "memory_candidate_create",
    "wiki_draft_write",
    "kb_extract_write",
    "repo_note_write",
}


def _decision(
    request: PolicyRequest,
    decision: PolicyDecisionEnum,
    explanation: str,
) -> PolicyDecision:
    return PolicyDecision(
        decision=decision,
        explanation=explanation,
        workspace=request.workspace,
        tool_name=request.tool_name,
        action_type=request.action_type,
        risk_level=request.risk_level,
        dry_run=request.dry_run,
    )


def _is_write_like(action_type: str) -> bool:
    return action_type in WRITE_ACTIONS


def _tool_in(tool_name: Optional[str], values: Iterable[str]) -> bool:
    return bool(tool_name and tool_name in set(values))


def evaluate_agentic_overlay(
    request: PolicyRequest,
    context: AgenticContext,
    workspace_cfg: Optional[Dict[str, Any]] = None,
) -> Optional[PolicyDecision]:
    """Return an overlay policy decision or None to fall through.

    Intended integration point:
        decision = evaluate_agentic_overlay(request, context, workspace_cfg)
        if decision is not None:
            return decision
        return base_engine.evaluate(request)
    """
    workspace_cfg = workspace_cfg or {}

    if context.tool_call_budget_remaining <= 0:
        return _decision(
            request,
            PolicyDecisionEnum.deny,
            "Agent tool-call budget exhausted for this run.",
        )

    if context.mode == AgentMode.interactive:
        return None

    if context.mode == AgentMode.observer:
        if _is_write_like(request.action_type) or _tool_in(request.tool_name, DANGEROUS_TOOLS):
            return _decision(
                request,
                PolicyDecisionEnum.deny,
                "Observer mode is read-only and cannot change external state.",
            )
        return None

    if context.mode == AgentMode.curator:
        if _tool_in(request.tool_name, DANGEROUS_TOOLS):
            return _decision(
                request,
                PolicyDecisionEnum.deny,
                "Curator mode cannot execute shell, sign, publish, or pay.",
            )
        if _is_write_like(request.action_type) and not _tool_in(request.tool_name, CURATOR_DRAFT_TOOLS):
            return _decision(
                request,
                PolicyDecisionEnum.require_approval,
                "Curator mode may only write draft/candidate knowledge without approval.",
            )
        return None

    if context.mode == AgentMode.operator:
        if _tool_in(request.tool_name, {"bitcoin_pay", "lightning_pay", "nostr_sign", "nostr_publish", "identity_update"}):
            if not context.step_up_verified:
                return _decision(
                    request,
                    PolicyDecisionEnum.escalate_channel,
                    "Operator mode requires step-up verification for identity or payment actions.",
                )
            return _decision(
                request,
                PolicyDecisionEnum.require_approval,
                "Identity and payment actions always require explicit approval.",
            )

        if request.action_type in {"write", "delete", "execute"} and request.risk_level in {"high", "critical"}:
            return _decision(
                request,
                PolicyDecisionEnum.require_approval,
                "High-risk operator actions require explicit approval.",
            )
        return None

    return None
