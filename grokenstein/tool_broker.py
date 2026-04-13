from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from .approvals import PendingApproval, PendingApprovalStore
from .logger import AuditLogger
from .policy import Decision, PolicyDecision, PolicyEngine
from .tools.filesystem import FilesystemTool
from .tools.shell import ShellTool


@dataclass(slots=True)
class ToolCallResult:
    status: str
    message: str
    output: Any = None
    request_id: str | None = None


class ToolBroker:
    def __init__(
        self,
        policy: PolicyEngine,
        logger: AuditLogger,
        approvals: PendingApprovalStore,
        workspace_root: str | Path,
    ) -> None:
        self.policy = policy
        self.logger = logger
        self.approvals = approvals
        self.workspace_root = Path(workspace_root).expanduser().resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.tools: Dict[str, Any] = {
            "filesystem": FilesystemTool(str(self.workspace_root)),
            "shell": ShellTool(),
        }

    def request_tool_call(
        self,
        session_id: str,
        tool_name: str,
        method_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> ToolCallResult:
        self.logger.log_event(
            "tool_requested",
            session_id=session_id,
            tool_name=tool_name,
            method_name=method_name,
            args=list(args),
            kwargs=kwargs,
        )

        decision = self.policy.evaluate(tool_name, method_name, args, kwargs)
        if decision.decision == Decision.DENY:
            self.logger.log_event(
                "tool_denied",
                session_id=session_id,
                tool_name=tool_name,
                method_name=method_name,
                reason=decision.reason,
                action_type=decision.action_type,
                risk_level=decision.risk_level,
            )
            return ToolCallResult(status="denied", message=decision.reason)

        if decision.decision == Decision.REQUIRE_APPROVAL:
            pending = self.approvals.create(
                session_id=session_id,
                tool_name=tool_name,
                method_name=method_name,
                args=list(args),
                kwargs=kwargs,
                reason=decision.reason,
            )
            self.logger.log_event(
                "approval_requested",
                session_id=session_id,
                request_id=pending.request_id,
                tool_name=tool_name,
                method_name=method_name,
                reason=decision.reason,
                args=list(args),
                kwargs=kwargs,
            )
            return ToolCallResult(
                status="approval_required",
                message=decision.reason,
                request_id=pending.request_id,
            )

        return self._execute(session_id=session_id, tool_name=tool_name, method_name=method_name, args=list(args), kwargs=kwargs, decision=decision)

    def approve(self, session_id: str, request_id: str | None = None) -> ToolCallResult:
        pending = self._resolve_pending(session_id, request_id)
        if pending is None:
            return ToolCallResult(status="error", message="No matching pending approval found.")

        decision = self.policy.evaluate(pending.tool_name, pending.method_name, pending.args, pending.kwargs)
        if decision.decision == Decision.DENY:
            self.approvals.remove(pending.request_id)
            self.logger.log_event(
                "tool_denied",
                session_id=session_id,
                request_id=pending.request_id,
                tool_name=pending.tool_name,
                method_name=pending.method_name,
                reason=decision.reason,
                action_type=decision.action_type,
                risk_level=decision.risk_level,
            )
            return ToolCallResult(status="denied", message=decision.reason, request_id=pending.request_id)

        self.approvals.remove(pending.request_id)
        self.logger.log_event(
            "approval_granted",
            session_id=session_id,
            request_id=pending.request_id,
            tool_name=pending.tool_name,
            method_name=pending.method_name,
        )
        return self._execute(
            session_id=session_id,
            tool_name=pending.tool_name,
            method_name=pending.method_name,
            args=pending.args,
            kwargs=pending.kwargs,
            decision=decision,
            request_id=pending.request_id,
        )

    def deny(self, session_id: str, request_id: str | None = None) -> ToolCallResult:
        pending = self._resolve_pending(session_id, request_id)
        if pending is None:
            return ToolCallResult(status="error", message="No matching pending approval found.")
        self.approvals.remove(pending.request_id)
        self.logger.log_event(
            "approval_denied",
            session_id=session_id,
            request_id=pending.request_id,
            tool_name=pending.tool_name,
            method_name=pending.method_name,
        )
        return ToolCallResult(
            status="denied",
            message=f"Denied pending request {pending.request_id}.",
            request_id=pending.request_id,
        )

    def list_pending(self, session_id: str) -> List[PendingApproval]:
        return self.approvals.list_for_session(session_id)

    def _resolve_pending(self, session_id: str, request_id: str | None) -> PendingApproval | None:
        if request_id:
            pending = self.approvals.get(request_id)
            if pending and pending.session_id == session_id:
                return pending
            return None
        pending_list = self.approvals.list_for_session(session_id)
        if len(pending_list) == 1:
            return pending_list[0]
        return None

    def _execute(
        self,
        session_id: str,
        tool_name: str,
        method_name: str,
        args: List[Any],
        kwargs: Dict[str, Any],
        decision: PolicyDecision,
        request_id: str | None = None,
    ) -> ToolCallResult:
        if tool_name not in self.tools:
            message = f"Tool '{tool_name}' is not registered."
            self.logger.log_event(
                "tool_error",
                session_id=session_id,
                request_id=request_id,
                tool_name=tool_name,
                method_name=method_name,
                error=message,
            )
            return ToolCallResult(status="error", message=message, request_id=request_id)

        tool = self.tools[tool_name]
        if not hasattr(tool, method_name):
            message = f"Tool '{tool_name}' has no method '{method_name}'."
            self.logger.log_event(
                "tool_error",
                session_id=session_id,
                request_id=request_id,
                tool_name=tool_name,
                method_name=method_name,
                error=message,
            )
            return ToolCallResult(status="error", message=message, request_id=request_id)

        method = getattr(tool, method_name)
        try:
            if tool_name == "shell":
                kwargs = {**kwargs, "cwd": str(self.workspace_root)}
            output = method(*args, **kwargs)
        except Exception as exc:  # pragma: no cover - exercised by runtime more than unit tests
            self.logger.log_event(
                "tool_error",
                session_id=session_id,
                request_id=request_id,
                tool_name=tool_name,
                method_name=method_name,
                error=repr(exc),
            )
            return ToolCallResult(status="error", message=f"Error: {exc}", request_id=request_id)

        self.logger.log_event(
            "tool_executed",
            session_id=session_id,
            request_id=request_id,
            tool_name=tool_name,
            method_name=method_name,
            action_type=decision.action_type,
            risk_level=decision.risk_level,
        )
        return ToolCallResult(status="executed", message="OK", output=output, request_id=request_id)
