from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .approval_queue import ApprovalQueue
from .audit import AuditLogger
from .policy import PolicyEngine
from .tools.fs_tool import FilesystemTool
from .tools.shell_tool import ShellTool


@dataclass
class BrokerResult:
    success: bool
    output: str = ""
    error: str = ""
    requires_approval: bool = False
    approval_id: str | None = None


class ToolBroker:
    def __init__(
        self,
        session_id: str,
        workspace_root: Path,
        approvals: ApprovalQueue,
        audit: AuditLogger,
        shell_timeout: int = 10,
    ) -> None:
        self.session_id = session_id
        self.policy = PolicyEngine(workspace_root=workspace_root)
        self.approvals = approvals
        self.audit = audit
        self.fs = FilesystemTool(workspace_root)
        self.shell = ShellTool(timeout=shell_timeout)

    def call(self, tool_name: str, payload: dict) -> BrokerResult:
        decision = self.policy.evaluate(tool_name, payload)
        self.audit.log(
            "broker.decision",
            self.session_id,
            tool_name=tool_name,
            decision=decision.decision,
            reason=decision.reason,
            payload=payload,
        )
        if decision.decision == "deny":
            return BrokerResult(success=False, error=decision.reason)
        if decision.decision == "require_approval":
            req = self.approvals.add(self.session_id, tool_name, payload, decision.reason)
            self.audit.log(
                "approval.requested",
                self.session_id,
                tool_name=tool_name,
                approval_id=req.id,
                reason=req.reason,
                payload=payload,
            )
            return BrokerResult(
                success=False,
                requires_approval=True,
                approval_id=req.id,
                error=decision.reason,
            )
        return self._execute(tool_name, payload)

    def approve(self, request_id: str | None = None) -> BrokerResult:
        req = self.approvals.get(request_id, session_id=self.session_id)
        if req is None:
            return BrokerResult(success=False, error="No matching approval request")
        result = self._execute(req.tool_name, req.payload)
        self.approvals.remove(req.id)
        self.audit.log(
            "approval.approved",
            self.session_id,
            tool_name=req.tool_name,
            approval_id=req.id,
            success=result.success,
        )
        return result

    def deny(self, request_id: str | None = None) -> BrokerResult:
        req = self.approvals.get(request_id, session_id=self.session_id)
        if req is None:
            return BrokerResult(success=False, error="No matching approval request")
        self.approvals.remove(req.id)
        self.audit.log(
            "approval.denied",
            self.session_id,
            tool_name=req.tool_name,
            approval_id=req.id,
        )
        return BrokerResult(success=True, output=f"Denied {req.tool_name} approval {req.id}")

    def pending(self) -> str:
        rows = self.approvals.list(session_id=self.session_id)
        if not rows:
            return "(no pending approvals)"
        lines = []
        for row in rows:
            lines.append(
                f"{row.id} | {row.tool_name} | {row.reason} | payload={row.payload}"
            )
        return "\n".join(lines)

    def _execute(self, tool_name: str, payload: dict) -> BrokerResult:
        if tool_name == "fs.list":
            res = self.fs.list(payload.get("path", "."))
        elif tool_name == "fs.read":
            res = self.fs.read(payload["path"])
        elif tool_name == "fs.write":
            res = self.fs.write(payload["path"], payload.get("content", ""))
        elif tool_name == "shell":
            res = self.shell.execute(payload["command"])
        else:
            return BrokerResult(success=False, error=f"Unknown tool: {tool_name}")
        self.audit.log(
            "tool.executed",
            self.session_id,
            tool_name=tool_name,
            success=res.success,
            payload=payload,
        )
        return BrokerResult(success=res.success, output=res.output, error=res.error)
