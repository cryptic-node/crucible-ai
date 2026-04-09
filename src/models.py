from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelAdapter:
    """Represents a single model backend adapter."""
    name: str
    backend: str
    model_id: str
    notes: str
    status: str = "available"


@dataclass(frozen=True)
class PermissionDenial:
    """Captures a denied tool execution with a reason."""
    tool_name: str
    reason: str


@dataclass(frozen=True)
class UsageSummary:
    """Tracks token usage across a session."""
    input_tokens: int = 0
    output_tokens: int = 0

    def add_turn(self, prompt: str, output: str) -> "UsageSummary":
        return UsageSummary(
            input_tokens=self.input_tokens + len(prompt.split()),
            output_tokens=self.output_tokens + len(output.split()),
        )


@dataclass
class GrokSession:
    """Persistent session record for a Grokenstein run."""
    session_id: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    backend_used: str = "unknown"
    model_used: str = "unknown"

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})

    def usage(self) -> UsageSummary:
        return UsageSummary(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
        )


@dataclass
class ModelBacklog:
    """Registry of planned or available model adapters."""
    title: str
    adapters: list[ModelAdapter] = field(default_factory=list)

    def summary_lines(self) -> list[str]:
        return [
            f"- {adapter.name} [{adapter.status}] — backend={adapter.backend}, model={adapter.model_id}"
            for adapter in self.adapters
        ]
