from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from ..core.audit import get_audit_logger
from ..core.config import get_settings
from ..core.trust import TrustLevel
from ..policy.engine import get_policy_engine
from ..schemas.policy import PolicyDecisionEnum, PolicyRequest
from ..schemas.tools import ToolResult
from ..tools.filesystem import FilesystemTool, FilesystemReadInput, FilesystemWriteInput, FilesystemListInput
from ..tools.shell import ShellTool, ShellInput
from ..tools.web_fetch import WebFetchTool, WebFetchInput


_TOOL_REGISTRY: Dict[str, Any] = {}


def _build_registry() -> Dict[str, Any]:
    fs = FilesystemTool()
    shell = ShellTool()
    web = WebFetchTool()
    return {
        "filesystem_read": (fs.read, FilesystemReadInput),
        "filesystem_write": (fs.write, FilesystemWriteInput),
        "filesystem_list": (fs.list_dir, FilesystemListInput),
        "shell": (shell.execute, ShellInput),
        "web_fetch": (web.fetch, WebFetchInput),
    }


_ACTION_RISK: Dict[str, str] = {
    "filesystem_read": "low",
    "filesystem_list": "low",
    "filesystem_write": "medium",
    "shell": "medium",
    "web_fetch": "low",
}

_ACTION_TYPE: Dict[str, str] = {
    "filesystem_read": "read",
    "filesystem_list": "read",
    "filesystem_write": "write",
    "shell": "execute",
    "web_fetch": "read",
}


class ToolBroker:
    """
    The sole gateway for all tool execution.

    Every call:
    1. Validates input schema (Pydantic)
    2. Queries Policy Engine
    3. Logs audit record
    4. Handles dry_run
    5. Routes to tool handler
    6. Wraps and returns result
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._registry = _build_registry()
        self._policy = get_policy_engine()
        self._audit = get_audit_logger()

    def call(
        self,
        tool_name: str,
        input_data: Dict[str, Any],
        workspace: str = "personal",
        channel: str = "cli",
        trust_level: str = "HIGH",
        dry_run: bool = False,
        correlation_id: Optional[str] = None,
    ) -> ToolResult:
        cid = correlation_id or str(uuid.uuid4())

        if tool_name not in self._registry:
            self._audit.log(
                workspace=workspace,
                actor=channel,
                action=f"tool_call:{tool_name}",
                tool_name=tool_name,
                input_data=input_data,
                policy_decision="deny",
                result_summary="Unknown tool",
                error=f"Unknown tool: {tool_name}",
                correlation_id=cid,
            )
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Unknown tool: '{tool_name}'. Available tools: {', '.join(sorted(self._registry.keys()))}",
            )

        handler, InputSchema = self._registry[tool_name]

        try:
            if dry_run:
                input_data = dict(input_data)
                input_data["dry_run"] = True
            validated = InputSchema(**input_data)
        except Exception as exc:
            self._audit.log(
                workspace=workspace,
                actor=channel,
                action=f"tool_call:{tool_name}",
                tool_name=tool_name,
                input_data=input_data,
                policy_decision="deny",
                result_summary="Schema validation failed",
                error=str(exc),
                correlation_id=cid,
            )
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Input validation failed: {exc}",
            )

        risk = _ACTION_RISK.get(tool_name, "medium")
        action_type = _ACTION_TYPE.get(tool_name, "generic")

        policy_request = PolicyRequest(
            workspace=workspace,
            channel=channel,
            trust_level=trust_level,
            tool_name=tool_name,
            action_type=action_type,
            risk_level=risk,
            dry_run=dry_run or getattr(validated, "dry_run", False),
            input_data=input_data,
        )
        decision = self._policy.evaluate(policy_request)

        if decision.decision in (PolicyDecisionEnum.deny,):
            self._audit.log(
                workspace=workspace,
                actor=channel,
                action=f"tool_call:{tool_name}",
                tool_name=tool_name,
                input_data=input_data,
                policy_decision=decision.decision.value,
                result_summary="Denied by policy",
                error=decision.explanation,
                correlation_id=cid,
            )
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Policy denied: {decision.explanation}",
                metadata={"policy_decision": decision.decision.value, "kill_switch": decision.kill_switch_active},
            )

        if decision.decision == PolicyDecisionEnum.require_approval:
            self._audit.log(
                workspace=workspace,
                actor=channel,
                action=f"tool_call:{tool_name}",
                tool_name=tool_name,
                input_data=input_data,
                policy_decision=decision.decision.value,
                approval_status="pending",
                result_summary="Requires approval",
                correlation_id=cid,
            )
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Approval required: {decision.explanation}",
                metadata={"policy_decision": decision.decision.value},
            )

        if decision.decision == PolicyDecisionEnum.require_simulation:
            self._audit.log(
                workspace=workspace,
                actor=channel,
                action=f"tool_call:{tool_name}",
                tool_name=tool_name,
                input_data=input_data,
                policy_decision=decision.decision.value,
                result_summary="Requires simulation first",
                correlation_id=cid,
            )
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Simulation required first (set dry_run=True): {decision.explanation}",
                metadata={"policy_decision": decision.decision.value},
            )

        if decision.decision == PolicyDecisionEnum.escalate_channel:
            self._audit.log(
                workspace=workspace,
                actor=channel,
                action=f"tool_call:{tool_name}",
                tool_name=tool_name,
                input_data=input_data,
                policy_decision=decision.decision.value,
                result_summary="Channel escalation required",
                error=decision.explanation,
                correlation_id=cid,
            )
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Channel escalation required: {decision.explanation}",
                metadata={"policy_decision": decision.decision.value},
            )

        try:
            result = handler(validated)
            self._audit.log(
                workspace=workspace,
                actor=channel,
                action=f"tool_call:{tool_name}",
                tool_name=tool_name,
                input_data=input_data,
                policy_decision=decision.decision.value,
                approval_status="not_required",
                dry_run=result.dry_run,
                result_summary=result.output[:200] if result.output else "",
                error=result.error,
                correlation_id=cid,
            )
            return result
        except Exception as exc:
            self._audit.log(
                workspace=workspace,
                actor=channel,
                action=f"tool_call:{tool_name}",
                tool_name=tool_name,
                input_data=input_data,
                policy_decision=decision.decision.value,
                result_summary="Tool execution raised exception",
                error=str(exc),
                correlation_id=cid,
            )
            return ToolResult(tool_name=tool_name, success=False, error=f"Tool execution error: {exc}")

    def list_tools(self) -> list[str]:
        return sorted(self._registry.keys())


_broker: Optional[ToolBroker] = None


def get_broker() -> ToolBroker:
    global _broker
    if _broker is None:
        _broker = ToolBroker()
    return _broker


def reset_broker(instance: Optional[ToolBroker] = None) -> None:
    global _broker
    _broker = instance
