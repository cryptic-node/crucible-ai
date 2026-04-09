from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .context import GrokContext, build_grok_context
from .history import HistoryLog
from .models import GrokSession, UsageSummary
from .models_router import ModelRouter
from .session_store import new_session_id, save_session
from .transcript import TranscriptStore


@dataclass(frozen=True)
class QueryEngineConfig:
    """Configuration for a GrokQueryEngine instance."""
    max_turns: int = 10
    backend: str = ""
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 1024
    system_prompt: str = (
        "You are Grokenstein, an amalgamation of free, public, and available AI models "
        "mashed up into a private, personal, persistent, network-connected AI. "
        "Be helpful, concise, and honest."
    )

    def as_router_config(self) -> dict[str, Any]:
        cfg: dict[str, Any] = {
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        if self.backend:
            cfg["backend"] = self.backend
        if self.model:
            cfg["model"] = self.model
        return cfg


@dataclass(frozen=True)
class TurnResult:
    """Outcome of a single conversation turn."""
    turn_index: int
    prompt: str
    output: str
    stop_reason: str
    backend_used: str = ""


@dataclass
class GrokQueryEngine:
    """Core query engine that wires GrokContext, ModelRouter, and session state together."""

    config: QueryEngineConfig = field(default_factory=QueryEngineConfig)
    context: GrokContext = field(default_factory=build_grok_context)
    router: ModelRouter = field(default_factory=ModelRouter)
    session: GrokSession = field(default_factory=lambda: GrokSession(session_id=new_session_id()))
    history: HistoryLog = field(default_factory=HistoryLog)
    transcript_store: TranscriptStore = field(default_factory=TranscriptStore)
    _turn_index: int = field(default=0, init=False, repr=False)

    @classmethod
    def from_workspace(
        cls,
        base: Path | None = None,
        config: QueryEngineConfig | None = None,
    ) -> "GrokQueryEngine":
        ctx = build_grok_context(base)
        return cls(
            config=config or QueryEngineConfig(),
            context=ctx,
        )

    def submit_message(self, prompt: str) -> TurnResult:
        """Send a user message to the router and record the exchange."""
        self._turn_index += 1
        router_config = self.config.as_router_config()

        full_prompt = self._build_full_prompt(prompt)
        response = self.router.complete(full_prompt, router_config)

        adapter = self.router.select_backend(router_config)
        self.session.add_message("user", prompt)
        self.session.add_message("assistant", response)
        self.session.backend_used = adapter.name
        self.session.model_used = getattr(adapter, "model", "unknown")

        usage = UsageSummary().add_turn(prompt, response)
        self.session.input_tokens += usage.input_tokens
        self.session.output_tokens += usage.output_tokens

        entry = f"[turn {self._turn_index}] user: {prompt}\nassistant: {response}"
        self.history.append(entry)
        self.transcript_store.append(entry)

        return TurnResult(
            turn_index=self._turn_index,
            prompt=prompt,
            output=response,
            stop_reason="end_turn",
            backend_used=adapter.name,
        )

    def _build_full_prompt(self, user_message: str) -> str:
        parts = [self.config.system_prompt, ""]
        history_tail = self.history.tail(6)
        if history_tail:
            parts.extend(history_tail)
            parts.append("")
        parts.append(f"User: {user_message}")
        parts.append("Assistant:")
        return "\n".join(parts)

    def run_turn_loop(
        self,
        initial_prompt: str,
        max_turns: int | None = None,
    ) -> list[TurnResult]:
        max_t = max_turns if max_turns is not None else self.config.max_turns
        results: list[TurnResult] = []
        prompt = initial_prompt
        for _ in range(max_t):
            result = self.submit_message(prompt)
            results.append(result)
            if result.stop_reason in ("end_turn", "stop"):
                break
            prompt = result.output
        return results

    def persist_session(self) -> str:
        """Save current session to disk and flush transcript."""
        path = save_session(self.session)
        self.transcript_store.flush()
        return path

    def render_summary(self) -> str:
        lines = [
            "# Grokenstein Session Summary",
            "",
            f"Session ID:    {self.session.session_id}",
            f"Backend:       {self.session.backend_used}",
            f"Model:         {self.session.model_used}",
            f"Turns:         {self._turn_index}",
            f"Messages:      {len(self.session.messages)}",
            f"Input tokens:  {self.session.input_tokens}",
            f"Output tokens: {self.session.output_tokens}",
            "",
            f"History entries: {len(self.history)}",
            f"Transcript flushed: {self.transcript_store.flushed}",
        ]
        return "\n".join(lines)
