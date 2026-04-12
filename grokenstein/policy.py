"""Basic policy engine for Grokenstein.

The policy engine evaluates whether a proposed tool invocation is permitted.
It implements a simple least‑privilege model: only whitelisted commands may
be run via the shell tool, and file operations are constrained by the
filesystem tool itself.  As the assistant grows, this component can be
extended to load per‑workspace policies from disk or to incorporate
user‑specified allowlists and denylists.
"""

from __future__ import annotations

from typing import Any, Sequence


class PolicyEngine:
    """Evaluate whether a tool call is allowed."""

    # Simple allowlist of commands permitted in the shell tool
    _allowed_shell_commands = {"ls", "echo", "pwd", "whoami", "date"}

    def is_allowed(self, tool_name: str, method_name: str, args: Sequence[Any], kwargs: dict) -> bool:
        """Return True if the requested tool call should proceed.

        Args:
            tool_name: logical name of the tool (e.g., ``"shell"``)
            method_name: the method on the tool being invoked (e.g., ``"run"``)
            args: positional arguments passed to the method
            kwargs: keyword arguments passed to the method

        Returns:
            Boolean indicating if the call is permitted.
        """
        if tool_name == "shell" and method_name == "run":
            # Expect a single string argument containing the command
            if not args:
                return False
            raw_command = str(args[0])
            # Use shlex to parse the command respecting quotes
            import shlex
            try:
                tokens = shlex.split(raw_command)
            except ValueError:
                return False
            if not tokens:
                return False
            cmd_name = tokens[0]
            # Permit only commands in the allowlist
            if cmd_name not in self._allowed_shell_commands:
                return False
            # Disallow chaining of commands via common shell operators
            for tok in tokens[1:]:
                if tok in {";", "&&", "||", "|"}:
                    return False
            return True
        # By default allow other tools; specific checks can be added here
        return True