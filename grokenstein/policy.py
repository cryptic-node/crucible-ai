from __future__ import annotations

import shlex
from dataclasses import dataclass
from enum import Enum
from typing import Any, Sequence


class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


@dataclass(slots=True)
class PolicyDecision:
    decision: Decision
    reason: str
    action_type: str
    risk_level: str


class PolicyEngine:
    def __init__(
        self,
        shell_allowlist: Sequence[str],
        kill_switch: bool = False,
        require_approval_for_write: bool = True,
        require_approval_for_shell: bool = True,
    ) -> None:
        self.shell_allowlist = set(shell_allowlist)
        self.kill_switch = kill_switch
        self.require_approval_for_write = require_approval_for_write
        self.require_approval_for_shell = require_approval_for_shell

    def evaluate(
        self,
        tool_name: str,
        method_name: str,
        args: Sequence[Any],
        kwargs: dict[str, Any],
    ) -> PolicyDecision:
        if self.kill_switch:
            return PolicyDecision(
                decision=Decision.DENY,
                reason="Global kill switch is enabled.",
                action_type="blocked",
                risk_level="critical",
            )

        if tool_name == "filesystem":
            if method_name == "list_dir":
                return PolicyDecision(Decision.ALLOW, "Workspace listing allowed.", "list", "low")
            if method_name == "read_file":
                return PolicyDecision(Decision.ALLOW, "Workspace read allowed.", "read", "low")
            if method_name == "write_file":
                if self.require_approval_for_write:
                    return PolicyDecision(
                        Decision.REQUIRE_APPROVAL,
                        "Workspace writes require approval.",
                        "write",
                        "medium",
                    )
                return PolicyDecision(Decision.ALLOW, "Workspace write allowed.", "write", "medium")

        if tool_name == "shell" and method_name == "run":
            if not args:
                return PolicyDecision(Decision.DENY, "Missing shell command.", "execute", "high")
            raw_command = str(args[0])
            parsed = self._parse_shell_command(raw_command)
            if parsed is None:
                return PolicyDecision(Decision.DENY, "Invalid shell command syntax.", "execute", "high")
            if not parsed:
                return PolicyDecision(Decision.DENY, "Empty shell command.", "execute", "high")

            command_name = parsed[0]
            if command_name not in self.shell_allowlist:
                return PolicyDecision(
                    Decision.DENY,
                    f"Command '{command_name}' is not in the shell allowlist.",
                    "execute",
                    "high",
                )

            for token in parsed[1:]:
                if token in {";", "&&", "||", "|", "`", "$()"}:
                    return PolicyDecision(
                        Decision.DENY,
                        "Shell chaining operators are not permitted.",
                        "execute",
                        "high",
                    )
                if token.startswith("/") or ".." in token:
                    return PolicyDecision(
                        Decision.DENY,
                        "Shell path arguments must stay inside the workspace.",
                        "execute",
                        "high",
                    )

            if self.require_approval_for_shell:
                return PolicyDecision(
                    Decision.REQUIRE_APPROVAL,
                    "Shell commands require approval.",
                    "execute",
                    "high",
                )
            return PolicyDecision(Decision.ALLOW, "Shell command allowed.", "execute", "high")

        return PolicyDecision(
            decision=Decision.DENY,
            reason=f"Tool call {tool_name}.{method_name} is not allowed in this release.",
            action_type="blocked",
            risk_level="high",
        )

    @staticmethod
    def _parse_shell_command(command: str) -> list[str] | None:
        try:
            return shlex.split(command)
        except ValueError:
            return None
