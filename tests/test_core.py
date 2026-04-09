"""Basic smoke tests for Grokenstein core modules."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from grokenstein.src.models import GrokSession, ModelAdapter, ModelBacklog, PermissionDenial, UsageSummary
from grokenstein.src.permissions import ToolPermissionContext
from grokenstein.src.history import HistoryLog
from grokenstein.src.transcript import TranscriptStore
from grokenstein.src.context import build_grok_context
from grokenstein.src.commands import execute_command, get_commands, render_command_index
from grokenstein.src.tools import execute_tool, get_tools, render_tool_index
from grokenstein.src.models_router import ModelRouter, GroqAdapter, OllamaAdapter


def test_usage_summary():
    u = UsageSummary()
    u2 = u.add_turn("hello world", "hi there")
    assert u2.input_tokens == 2
    assert u2.output_tokens == 2


def test_grok_session():
    s = GrokSession(session_id="abc-123")
    s.add_message("user", "hello")
    s.add_message("assistant", "hi")
    assert len(s.messages) == 2
    assert s.messages[0]["role"] == "user"


def test_model_backlog():
    backlog = ModelBacklog(title="test")
    adapter = ModelAdapter(name="groq-llama", backend="groq", model_id="llama3-8b-8192", notes="")
    backlog.adapters.append(adapter)
    lines = backlog.summary_lines()
    assert len(lines) == 1
    assert "groq" in lines[0]


def test_permission_context():
    ctx = ToolPermissionContext.from_iterables(["bash"], ["web_"])
    assert ctx.is_denied("bash")
    assert ctx.is_denied("web_fetch")
    assert not ctx.is_denied("read_file")


def test_history_log():
    log = HistoryLog()
    log.append("turn 1")
    log.append("turn 2")
    assert len(log) == 2
    assert log.tail(1) == ["turn 2"]
    assert log.replay() == ("turn 1", "turn 2")


def test_transcript_store():
    ts = TranscriptStore()
    ts.append("entry 1")
    ts.append("entry 2")
    assert not ts.flushed
    ts.flush()
    assert ts.flushed
    ts.compact(keep_last=1)
    assert ts.entries == ["entry 2"]


def test_grok_context():
    ctx = build_grok_context()
    assert ctx.source_root.exists()
    assert ctx.tests_root.exists()


def test_get_commands():
    cmds = get_commands()
    assert len(cmds) > 0
    names = [c.name for c in cmds]
    assert "help" in names
    assert "exit" in names


def test_execute_help_command():
    result = execute_command("help")
    assert result.handled
    assert "help" in result.message.lower()


def test_execute_models_command():
    result = execute_command("models")
    assert result.handled
    assert "groq" in result.message.lower()


def test_get_tools():
    tools = get_tools()
    assert len(tools) > 0
    names = [t.name for t in tools]
    assert "bash" in names
    assert "read_file" in names


def test_tool_permission_filtering():
    ctx = ToolPermissionContext.from_iterables(["bash"])
    tools = get_tools(permission_context=ctx)
    names = [t.name for t in tools]
    assert "bash" not in names
    assert "read_file" in names


def test_model_router_list_backends():
    router = ModelRouter()
    backends = router.list_backends()
    assert "groq" in backends
    assert "ollama" in backends
    assert "openrouter" in backends
    assert "huggingface" in backends


def test_model_router_stub_completion():
    router = ModelRouter()
    result = router.complete("hello", {"backend": "groq"})
    assert isinstance(result, str)
    assert len(result) > 0


def test_execute_tool_bash():
    result = execute_tool("bash", {"command": "echo hello"})
    assert result.handled
    assert "hello" in result.message


def test_execute_tool_read_nonexistent():
    result = execute_tool("read_file", {"path": "/nonexistent/file.txt"})
    assert not result.handled
    assert result.error


def test_render_tool_index():
    index = render_tool_index()
    assert "bash" in index


def test_render_command_index():
    index = render_command_index()
    assert "help" in index
