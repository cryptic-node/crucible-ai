from __future__ import annotations

from dataclasses import dataclass

from .commands import PORTED_COMMANDS, execute_command
from .context import GrokContext, build_grok_context, render_context
from .history import HistoryLog
from .models import GrokSession, PermissionDenial
from .models_router import ModelRouter
from .query_engine import GrokQueryEngine, QueryEngineConfig, TurnResult
from .session_store import new_session_id, save_session
from .tools import PORTED_TOOLS, execute_tool


@dataclass(frozen=True)
class RoutedMatch:
    """A ranked match from prompt routing."""
    kind: str
    name: str
    description: str
    score: int


@dataclass
class RuntimeSession:
    """Full snapshot of a bootstrapped Grokenstein runtime session."""
    prompt: str
    context: GrokContext
    history: HistoryLog
    routed_matches: list[RoutedMatch]
    turn_result: TurnResult | None
    command_messages: tuple[str, ...]
    tool_messages: tuple[str, ...]
    persisted_session_path: str

    def as_markdown(self) -> str:
        lines = [
            "# Grokenstein Runtime Session",
            "",
            f"Prompt: {self.prompt}",
            "",
            "## Context",
            render_context(self.context),
            "",
            "## Routed Matches",
        ]
        if self.routed_matches:
            for m in self.routed_matches:
                lines.append(f"  [{m.kind}] {m.name} (score={m.score}) — {m.description}")
        else:
            lines.append("  (none)")

        lines += ["", "## Turn Result"]
        if self.turn_result:
            lines.append(f"  output: {self.turn_result.output[:200]}")
            lines.append(f"  stop_reason: {self.turn_result.stop_reason}")
            lines.append(f"  backend: {self.turn_result.backend_used}")
        else:
            lines.append("  (none)")

        lines += ["", "## Command Messages"]
        lines.extend(f"  {m}" for m in self.command_messages) or lines.append("  (none)")

        lines += ["", "## Tool Messages"]
        lines.extend(f"  {m}" for m in self.tool_messages) or lines.append("  (none)")

        lines += ["", f"Persisted: {self.persisted_session_path}"]
        return "\n".join(lines)


class GrokRuntime:
    """Top-level Grokenstein runtime. Coordinates engine, tools, and commands."""

    def __init__(self, config: QueryEngineConfig | None = None) -> None:
        self.config = config or QueryEngineConfig()
        self.context = build_grok_context()
        self.engine = GrokQueryEngine(config=self.config, context=self.context)
        self.router = self.engine.router

    def route_prompt(self, prompt: str, limit: int = 5) -> list[RoutedMatch]:
        """Score all tools and commands against a prompt (simple keyword matching)."""
        prompt_lower = prompt.lower()
        matches: list[RoutedMatch] = []

        for tool in PORTED_TOOLS:
            score = sum(
                2 for word in prompt_lower.split()
                if word in tool.name or word in tool.description.lower()
            )
            if score > 0:
                matches.append(RoutedMatch("tool", tool.name, tool.description, score))

        for cmd in PORTED_COMMANDS:
            score = sum(
                1 for word in prompt_lower.split()
                if word in cmd.name or word in cmd.description.lower()
            )
            if score > 0:
                matches.append(RoutedMatch("command", cmd.name, cmd.description, score))

        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[:limit]

    def bootstrap_session(self, prompt: str, limit: int = 5) -> RuntimeSession:
        """Build a full runtime session snapshot for a given prompt."""
        routed = self.route_prompt(prompt, limit=limit)
        turn = self.engine.submit_message(prompt)
        persisted = self.engine.persist_session()

        cmd_msgs = tuple(
            execute_command(c.name, {"session": self.engine.session}).message
            for c in PORTED_COMMANDS[:2]
        )
        tool_msgs: tuple[str, ...] = ()

        return RuntimeSession(
            prompt=prompt,
            context=self.context,
            history=self.engine.history,
            routed_matches=routed,
            turn_result=turn,
            command_messages=cmd_msgs,
            tool_messages=tool_msgs,
            persisted_session_path=persisted,
        )

    def run_turn_loop(
        self,
        prompt: str,
        max_turns: int = 3,
    ) -> list[TurnResult]:
        return self.engine.run_turn_loop(prompt, max_turns=max_turns)

    def chat(self, prompt: str) -> str:
        """Single-turn chat convenience method."""
        result = self.engine.submit_message(prompt)
        return result.output
