"""Central dispatcher for Grokenstein's tools.

The ``ToolBroker`` acts as the single point through which the assistant can
invoke side‑effecting operations.  It maintains a registry of tool
instances, checks each call against the policy engine, and records
successful invocations in the audit log.  New tools should be added to
the registry in ``__init__``.
"""

from __future__ import annotations

from typing import Any, Dict

from .policy import PolicyEngine
from .logger import AuditLogger
from .tools.filesystem import FilesystemTool
from .tools.shell import ShellTool


class ToolBroker:
    """Route tool calls through policy and logging."""

    def __init__(self, policy: PolicyEngine, logger: AuditLogger, workspace_root: str | None = None) -> None:
        self.policy = policy
        self.logger = logger
        # Determine an allowed workspace path.  Default to project root's workspace directory.
        import os
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        default_workspace = os.path.join(base_dir, "workspace")
        self.workspace_root = workspace_root or default_workspace
        # Ensure workspace directory exists
        os.makedirs(self.workspace_root, exist_ok=True)
        # Initialise tool registry
        self.tools: Dict[str, Any] = {
            "filesystem": FilesystemTool(self.workspace_root),
            "shell": ShellTool(),
            # Additional tools can be registered here
        }

    def call(self, tool_name: str, method_name: str, *args: Any, **kwargs: Any) -> Any:
        """Invoke a method on a registered tool through policy checks.

        Args:
            tool_name: key identifying the tool (e.g. ``"filesystem"``)
            method_name: name of the method on the tool to invoke
            *args: positional arguments for the method
            **kwargs: keyword arguments for the method

        Returns:
            The return value from the tool method.

        Raises:
            KeyError: if the tool is not registered
            PermissionError: if the policy engine denies the call
            AttributeError: if the requested method does not exist on the tool
        """
        # Ensure the tool exists
        if tool_name not in self.tools:
            raise KeyError(f"Tool '{tool_name}' is not registered.")
        tool = self.tools[tool_name]
        # Validate method existence
        if not hasattr(tool, method_name):
            raise AttributeError(f"Tool '{tool_name}' has no method '{method_name}'.")
        # Check policy
        if not self.policy.is_allowed(tool_name, method_name, args, kwargs):
            raise PermissionError(f"Call to {tool_name}.{method_name} denied by policy.")
        # Invoke the method
        method = getattr(tool, method_name)
        result = method(*args, **kwargs)
        # Log the call
        self.logger.log_call(tool_name, method_name, args, kwargs)
        return result