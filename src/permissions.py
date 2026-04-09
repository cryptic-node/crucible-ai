from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class ToolPermissionContext:
    """Tracks which tools are explicitly denied by name or prefix."""
    denied_tools: frozenset[str] = field(default_factory=frozenset)
    denied_prefixes: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_iterables(
        cls,
        denied_tools: Iterable[str] = (),
        denied_prefixes: Iterable[str] = (),
    ) -> "ToolPermissionContext":
        return cls(
            denied_tools=frozenset(denied_tools),
            denied_prefixes=tuple(denied_prefixes),
        )

    def is_denied(self, tool_name: str) -> bool:
        if tool_name in self.denied_tools:
            return True
        return any(tool_name.startswith(prefix) for prefix in self.denied_prefixes)
