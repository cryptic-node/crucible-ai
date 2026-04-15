from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class PolicyDecision:
    decision: str
    reason: str


class PolicyEngine:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()

    def evaluate(self, tool_name: str, payload: dict) -> PolicyDecision:
        if tool_name in {"fs.list", "fs.read", "project.inspect", "project.summary", "project.search"}:
            return PolicyDecision("allow", "read-only tool")
        if tool_name in {"fs.write", "shell"}:
            return PolicyDecision("require_approval", "side-effecting tool")
        return PolicyDecision("deny", f"unknown or disallowed tool: {tool_name}")
