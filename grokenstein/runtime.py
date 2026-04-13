from __future__ import annotations

import shlex
from pathlib import Path
from typing import List

from .approvals import PendingApprovalStore
from .config import RuntimeConfig
from .logger import AuditLogger
from .memory import MemoryManager
from .model import ModelResponse, create_model_adapter
from .policy import PolicyEngine
from .tool_broker import ToolBroker, ToolCallResult


class ChatRuntime:
    def __init__(
        self,
        conversation_id: str = "default",
        workspace_root: str | None = None,
        base_dir: str | Path | None = None,
        model_backend: str | None = None,
        model_name: str | None = None,
    ) -> None:
        self.conversation_id = conversation_id
        self.config = RuntimeConfig.from_env(
            workspace_root=workspace_root,
            base_dir=base_dir,
            model_backend=model_backend,
            model_name=model_name,
        )
        self.memory = MemoryManager(str(self.config.memory_path))
        self.logger = AuditLogger(str(self.config.audit_log_path))
        self.approvals = PendingApprovalStore(str(self.config.approval_store_path))
        self.policy = PolicyEngine(
            shell_allowlist=self.config.shell_allowlist,
            kill_switch=self.config.kill_switch,
            require_approval_for_write=self.config.require_approval_for_write,
            require_approval_for_shell=self.config.require_approval_for_shell,
        )
        self.broker = ToolBroker(
            policy=self.policy,
            logger=self.logger,
            approvals=self.approvals,
            workspace_root=self.config.workspace_root,
        )
        self.model = create_model_adapter(self.config)
        self.logger.log_event(
            "session_started",
            session_id=self.conversation_id,
            model_backend=self.model.backend_name,
            workspace_root=str(self.config.workspace_root),
        )

    def handle_user_message(self, user_message: str) -> str:
        stripped = user_message.strip()
        if not stripped:
            return ""

        if stripped.lower() in {"!help", "help"}:
            return self._help_message()
        if stripped.lower() in {"!history", "history"}:
            return self._history_message()
        if stripped.lower() in {"!status", "status"}:
            return self._status_message()
        if stripped.lower() in {"!pending", "pending"}:
            return self._pending_message()
        if stripped.startswith("!approve"):
            return self._approve_command(stripped)
        if stripped.startswith("!deny"):
            return self._deny_command(stripped)

        if stripped.startswith("!"):
            try:
                return self._handle_tool_invocation(stripped)
            except Exception as exc:  # pragma: no cover - CLI safety net
                self.logger.log_event(
                    "tool_error",
                    session_id=self.conversation_id,
                    error=repr(exc),
                )
                return f"Error: {exc}"

        self.logger.log_event(
            "user_message",
            session_id=self.conversation_id,
            content=user_message,
        )
        self.memory.append_message(self.conversation_id, "user", user_message)
        history = self.memory.load_history(self.conversation_id)
        model_response = self.model.generate(user_message, history)

        if model_response.mode == "tool_call":
            broker_result = self.broker.request_tool_call(
                self.conversation_id,
                model_response.tool_name or "",
                model_response.method_name or "",
                *model_response.args,
                **model_response.kwargs,
            )
            assistant_reply = self._format_tool_result(model_response, broker_result)
        else:
            assistant_reply = model_response.content

        self.memory.append_message(self.conversation_id, "assistant", assistant_reply)
        self.logger.log_event(
            "assistant_message",
            session_id=self.conversation_id,
            content=assistant_reply,
        )
        return assistant_reply

    def _handle_tool_invocation(self, command: str) -> str:
        tokens = shlex.split(command)
        if not tokens:
            return ""
        verb = tokens[0][1:]

        if verb == "fs":
            if len(tokens) < 2:
                return "Usage: !fs [list/read/write] ..."
            op = tokens[1]
            if op == "list":
                rel_path = tokens[2] if len(tokens) > 2 else "."
                result = self.broker.request_tool_call(
                    self.conversation_id,
                    "filesystem",
                    "list_dir",
                    rel_path,
                )
                return self._format_direct_result(result)
            if op == "read":
                if len(tokens) < 3:
                    return "Usage: !fs read <path>"
                result = self.broker.request_tool_call(
                    self.conversation_id,
                    "filesystem",
                    "read_file",
                    tokens[2],
                )
                return self._format_direct_result(result)
            if op == "write":
                if len(tokens) < 3:
                    return "Usage: !fs write <path> [content]"
                rel_path = tokens[2]
                if len(tokens) > 3:
                    content = " ".join(tokens[3:])
                else:
                    print("Enter file content, then type a single line containing 'EOF' to finish:")
                    lines: List[str] = []
                    while True:
                        try:
                            line = input()
                        except EOFError:
                            break
                        if line.strip() == "EOF":
                            break
                        lines.append(line)
                    content = "\n".join(lines)
                result = self.broker.request_tool_call(
                    self.conversation_id,
                    "filesystem",
                    "write_file",
                    rel_path,
                    content,
                )
                return self._format_direct_result(result)
            return f"Unknown filesystem operation: {op}"

        if verb == "shell":
            if len(tokens) < 2:
                return "Usage: !shell <command>"
            shell_cmd = command[len("!shell") :].lstrip()
            result = self.broker.request_tool_call(
                self.conversation_id,
                "shell",
                "run",
                shell_cmd,
            )
            return self._format_direct_result(result)

        return f"Unknown tool prefix: {verb}"

    def _format_tool_result(self, model_response: ModelResponse, result: ToolCallResult) -> str:
        lead = model_response.content.strip()
        body = self._format_direct_result(result)
        if lead and lead != body:
            return f"{lead}\n{body}"
        return body

    def _format_direct_result(self, result: ToolCallResult) -> str:
        if result.status == "executed":
            if isinstance(result.output, list):
                return "\n".join(result.output) or "(empty)"
            if result.output in (None, ""):
                return "OK"
            return str(result.output)
        if result.status == "approval_required":
            return (
                f"Approval required: {result.message}\n"
                f"Request ID: {result.request_id}\n"
                f"Use !approve {result.request_id} or !deny {result.request_id}."
            )
        return result.message

    def _approve_command(self, command: str) -> str:
        parts = shlex.split(command)
        request_id = parts[1] if len(parts) > 1 else None
        if request_id is None and len(self.broker.list_pending(self.conversation_id)) > 1:
            return "Multiple pending requests exist. Use !pending and approve one by request ID."
        result = self.broker.approve(self.conversation_id, request_id)
        return self._format_direct_result(result)

    def _deny_command(self, command: str) -> str:
        parts = shlex.split(command)
        request_id = parts[1] if len(parts) > 1 else None
        if request_id is None and len(self.broker.list_pending(self.conversation_id)) > 1:
            return "Multiple pending requests exist. Use !pending and deny one by request ID."
        result = self.broker.deny(self.conversation_id, request_id)
        return self._format_direct_result(result)

    def _help_message(self) -> str:
        return "\n".join(
            [
                "Available commands:",
                "  !help                 Show this help message.",
                "  !history              Show conversation history.",
                "  !status               Show backend, workspace, and approval info.",
                "  !pending              List pending approvals.",
                "  !approve [request_id] Approve a pending action.",
                "  !deny [request_id]    Deny a pending action.",
                "  !fs list [path]       List workspace directory contents.",
                "  !fs read <path>       Read a file from the workspace.",
                "  !fs write <path> [content]  Write a file in the workspace.",
                "  !shell <command>      Run an allowlisted shell command.",
                "Messages not starting with '!' go through the governed model runtime.",
            ]
        )

    def _history_message(self) -> str:
        history = self.memory.load_history(self.conversation_id)
        if not history:
            return "(no history)"
        formatted = []
        for role, content in history:
            prefix = "YOU" if role == "user" else "ASSISTANT"
            formatted.append(f"[{prefix}] {content}")
        return "\n".join(formatted)

    def _status_message(self) -> str:
        pending_count = len(self.broker.list_pending(self.conversation_id))
        return "\n".join(
            [
                f"Session: {self.conversation_id}",
                f"Model backend: {self.model.backend_name}",
                f"Workspace: {self.config.workspace_root}",
                f"Pending approvals: {pending_count}",
                f"Audit log: {self.config.audit_log_path}",
            ]
        )

    def _pending_message(self) -> str:
        pending = self.broker.list_pending(self.conversation_id)
        if not pending:
            return "(no pending approvals)"
        lines = ["Pending approvals:"]
        for item in pending:
            lines.append(
                f"  {item.request_id} -> {item.tool_name}.{item.method_name} args={item.args!r} reason={item.reason}"
            )
        return "\n".join(lines)

    def shutdown(self) -> None:
        self.logger.log_event("session_shutdown", session_id=self.conversation_id)
