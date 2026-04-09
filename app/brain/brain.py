from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from ..broker.broker import get_broker
from ..core.audit import get_audit_logger
from ..core.config import get_settings
from ..core.trust import TrustLevel
from ..memory.service import InMemoryMemoryService, PostgresMemoryService, get_memory_service
from ..schemas.memory import MemoryCreate, MemorySearch
from ..schemas.tools import ToolResult

try:
    from ...src.models_router import ModelRouter
except ImportError:
    try:
        from grokenstein.src.models_router import ModelRouter
    except ImportError:
        ModelRouter = None  # type: ignore


class BrainSession:
    """Represents a single chat session managed by the Brain."""

    def __init__(
        self,
        session_id: str,
        workspace: str = "personal",
        channel: str = "cli",
        trust_level: str = "HIGH",
        dry_run: bool = False,
        backend: str = "",
        model: str = "",
        db=None,
    ) -> None:
        self.session_id = session_id
        self.workspace = workspace
        self.channel = channel
        self.trust_level = trust_level
        self.dry_run = dry_run
        self.backend = backend
        self.model = model
        self.db = db
        self.messages: List[Dict[str, Any]] = []
        self.tool_calls: List[Dict[str, Any]] = []
        self.policy_decisions: List[Dict[str, Any]] = []

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})

    def add_policy_decision(self, tool_name: str, decision: str, explanation: str = "") -> None:
        self.policy_decisions.append({
            "tool_name": tool_name,
            "decision": decision,
            "explanation": explanation,
        })

    def get_memory_service(self):
        """Return a DB-backed memory service if DB session is available."""
        if self.db is not None:
            return PostgresMemoryService(self.db)
        return get_memory_service()


class Brain:
    """
    Grokenstein Brain module.

    Handles chat loop, planning, summarization, and memory retrieval.
    Strictly communicates only through ToolBroker and MemoryService.
    Does NOT call tool handlers directly. Does NOT hold raw secrets.
    Preserves existing LLM model routing logic via ModelRouter.
    """

    SYSTEM_PROMPT = (
        "You are Grokenstein, a security-first, privacy-focused personal operator AI. "
        "You help users manage tasks, files, information, and communications. "
        "You operate with strict policy controls and always respect workspace boundaries. "
        "Be helpful, concise, and honest. Flag any uncertainty clearly."
    )

    def __init__(self) -> None:
        self.settings = get_settings()
        self.broker = get_broker()
        self.audit = get_audit_logger()
        if ModelRouter is not None:
            self._router = ModelRouter()
        else:
            self._router = None

    def _build_prompt(self, session: BrainSession, user_message: str) -> str:
        parts = [self.SYSTEM_PROMPT, ""]
        recent = session.messages[-6:] if len(session.messages) > 6 else session.messages
        for msg in recent:
            role = "User" if msg["role"] == "user" else "Assistant"
            parts.append(f"{role}: {msg['content']}")
        parts.append(f"User: {user_message}")
        parts.append("Assistant:")
        return "\n".join(parts)

    async def _retrieve_relevant_memory_async(self, session: BrainSession, query: str) -> str:
        """Retrieve relevant memory using async-safe service dispatch."""
        import inspect
        svc = session.get_memory_service()
        try:
            req = MemorySearch(workspace_id=session.workspace, query=query, limit=3)
            results = svc.search(req)
            if inspect.isawaitable(results):
                results = await results
            if not results:
                return ""
            lines = ["Relevant memory:"]
            for r in results:
                lines.append(f"  [{r.record.memory_class}] {r.record.key}: {r.record.value[:200]}")
            return "\n".join(lines)
        except Exception:
            return ""

    async def _store_exchange_async(self, session: BrainSession, user_message: str, reply: str) -> None:
        """Store the exchange in persistent memory (DB-backed when available)."""
        import inspect
        svc = session.get_memory_service()
        try:
            coro_or_val = svc.create(MemoryCreate(
                workspace_id=session.workspace,
                memory_class="ephemeral",
                key=f"exchange:{session.session_id}:{len(session.messages)}",
                value=f"User: {user_message}\nAssistant: {reply}",
                retention_class="session",
                provenance={"session_id": session.session_id, "channel": session.channel},
                created_by=session.channel,
                session_id=session.session_id,
            ))
            if inspect.isawaitable(coro_or_val):
                await coro_or_val
        except Exception:
            pass

    def _retrieve_relevant_memory(self, session: BrainSession, query: str) -> str:
        """Sync wrapper — used when no async context (e.g. tests)."""
        svc = session.get_memory_service()
        try:
            results = svc.search(MemorySearch(
                workspace_id=session.workspace,
                query=query,
                limit=3,
            ))
            if not results:
                return ""
            lines = ["Relevant memory:"]
            for r in results:
                lines.append(f"  [{r.record.memory_class}] {r.record.key}: {r.record.value[:200]}")
            return "\n".join(lines)
        except Exception:
            return ""

    def _store_exchange(self, session: BrainSession, user_message: str, reply: str) -> None:
        """Sync wrapper — used when no async context (e.g. tests)."""
        svc = session.get_memory_service()
        try:
            svc.create(MemoryCreate(
                workspace_id=session.workspace,
                memory_class="ephemeral",
                key=f"exchange:{session.session_id}:{len(session.messages)}",
                value=f"User: {user_message}\nAssistant: {reply}",
                retention_class="session",
                provenance={"session_id": session.session_id, "channel": session.channel},
                created_by=session.channel,
                session_id=session.session_id,
            ))
        except Exception:
            pass

    async def chat_async(self, session: BrainSession, user_message: str) -> str:
        """Async chat turn — used in FastAPI context for full DB-backed memory."""
        session.add_message("user", user_message)

        mem_context = await self._retrieve_relevant_memory_async(session, user_message)
        prompt = self._build_prompt(session, user_message)
        if mem_context:
            prompt = mem_context + "\n\n" + prompt

        reply = await self._run_llm(session, prompt)
        session.add_message("assistant", reply)
        session.add_policy_decision(
            tool_name="chat",
            decision="allow",
            explanation="Chat turn processed",
        )

        await self._store_exchange_async(session, user_message, reply)

        self.audit.log(
            workspace=session.workspace,
            actor=session.channel,
            action="chat_turn",
            policy_decision="allow",
            dry_run=session.dry_run,
            result_summary=reply[:200],
        )

        return reply

    def chat(self, session: BrainSession, user_message: str) -> str:
        """Sync chat turn — used in tests and CLI context."""
        session.add_message("user", user_message)

        mem_context = self._retrieve_relevant_memory(session, user_message)
        prompt = self._build_prompt(session, user_message)
        if mem_context:
            prompt = mem_context + "\n\n" + prompt

        reply = ""
        if self._router is not None:
            cfg: Dict[str, Any] = {"max_tokens": 1024, "temperature": 0.7}
            if self.settings.grok_backend:
                cfg["backend"] = self.settings.grok_backend
            if session.backend:
                cfg["backend"] = session.backend
            if session.model:
                cfg["model"] = session.model
            try:
                adapter = self._router.select_backend(cfg)
                reply = adapter.complete(prompt, cfg)
            except Exception as exc:
                reply = f"[Brain error] LLM call failed: {exc}"
        else:
            reply = f"[Brain stub] No LLM router available. Echo: {user_message}"

        session.add_message("assistant", reply)
        session.add_policy_decision(
            tool_name="chat",
            decision="allow",
            explanation="Chat turn processed",
        )
        self._store_exchange(session, user_message, reply)

        self.audit.log(
            workspace=session.workspace,
            actor=session.channel,
            action="chat_turn",
            policy_decision="allow",
            dry_run=session.dry_run,
            result_summary=reply[:200],
        )

        return reply

    async def _run_llm(self, session: BrainSession, prompt: str) -> str:
        """Run LLM completion (sync adapter wrapped async)."""
        if self._router is not None:
            cfg: Dict[str, Any] = {"max_tokens": 1024, "temperature": 0.7}
            if self.settings.grok_backend:
                cfg["backend"] = self.settings.grok_backend
            if session.backend:
                cfg["backend"] = session.backend
            if session.model:
                cfg["model"] = session.model
            try:
                adapter = self._router.select_backend(cfg)
                return adapter.complete(prompt, cfg)
            except Exception as exc:
                return f"[Brain error] LLM call failed: {exc}"
        return f"[Brain stub] No LLM router available."

    def call_tool(
        self,
        session: BrainSession,
        tool_name: str,
        input_data: Dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> ToolResult:
        """Call a tool via the broker. Brain never calls tool handlers directly."""
        result = self.broker.call(
            tool_name=tool_name,
            input_data=input_data,
            workspace=session.workspace,
            channel=session.channel,
            trust_level=session.trust_level,
            dry_run=session.dry_run,
            correlation_id=correlation_id,
        )
        session.tool_calls.append({
            "tool_name": tool_name,
            "input": input_data,
            "success": result.success,
            "output": result.output[:200] if result.output else "",
            "error": result.error,
        })
        policy_decision = (result.metadata or {}).get("policy_decision", "allow" if result.success else "deny")
        session.add_policy_decision(
            tool_name=tool_name,
            decision=policy_decision,
            explanation=result.error or "",
        )
        return result


_brain: Optional[Brain] = None


def get_brain() -> Brain:
    global _brain
    if _brain is None:
        _brain = Brain()
    return _brain


def reset_brain(instance: Optional[Brain] = None) -> None:
    global _brain
    _brain = instance
