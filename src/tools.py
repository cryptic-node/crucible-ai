from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .permissions import ToolPermissionContext


@dataclass(frozen=True)
class GrokTool:
    """Descriptor for a registered Grokenstein tool."""
    name: str
    description: str
    schema: dict[str, Any]

    def render(self) -> str:
        return f"[tool:{self.name}] {self.description}"


@dataclass(frozen=True)
class ToolResult:
    """Result of a tool execution."""
    tool_name: str
    handled: bool
    message: str
    error: str = ""


def _tool_bash(payload: dict[str, Any]) -> ToolResult:
    """Execute a shell command and return stdout."""
    cmd = payload.get("command", "")
    if not cmd:
        return ToolResult("bash", False, "", "No command provided.")
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout + (f"\n[stderr] {result.stderr}" if result.stderr else "")
        return ToolResult("bash", True, output.strip())
    except subprocess.TimeoutExpired:
        return ToolResult("bash", False, "", "Command timed out.")
    except Exception as exc:
        return ToolResult("bash", False, "", str(exc))


def _tool_read_file(payload: dict[str, Any]) -> ToolResult:
    """Read a file from disk."""
    path_str = payload.get("path", "")
    if not path_str:
        return ToolResult("read_file", False, "", "No path provided.")
    path = Path(path_str)
    if not path.exists():
        return ToolResult("read_file", False, "", f"File not found: {path_str}")
    try:
        content = path.read_text(encoding="utf-8")
        return ToolResult("read_file", True, content)
    except Exception as exc:
        return ToolResult("read_file", False, "", str(exc))


def _tool_write_file(payload: dict[str, Any]) -> ToolResult:
    """Write content to a file on disk."""
    path_str = payload.get("path", "")
    content = payload.get("content", "")
    if not path_str:
        return ToolResult("write_file", False, "", "No path provided.")
    path = Path(path_str)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return ToolResult("write_file", True, f"Written {len(content)} chars to {path_str}")
    except Exception as exc:
        return ToolResult("write_file", False, "", str(exc))


def _tool_web_fetch(payload: dict[str, Any]) -> ToolResult:
    """Fetch content from a URL."""
    import urllib.request
    url = payload.get("url", "")
    if not url:
        return ToolResult("web_fetch", False, "", "No URL provided.")
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            raw = resp.read(65536)
            return ToolResult("web_fetch", True, raw.decode("utf-8", errors="replace"))
    except Exception as exc:
        return ToolResult("web_fetch", False, "", str(exc))


PORTED_TOOLS: list[GrokTool] = [
    GrokTool(
        name="bash",
        description="Execute a shell command.",
        schema={"command": "string"},
    ),
    GrokTool(
        name="read_file",
        description="Read a file from the local filesystem.",
        schema={"path": "string"},
    ),
    GrokTool(
        name="write_file",
        description="Write content to a file on the local filesystem.",
        schema={"path": "string", "content": "string"},
    ),
    GrokTool(
        name="web_fetch",
        description="Fetch content from a URL.",
        schema={"url": "string"},
    ),
]

_TOOL_HANDLERS: dict[str, Any] = {
    "bash": _tool_bash,
    "read_file": _tool_read_file,
    "write_file": _tool_write_file,
    "web_fetch": _tool_web_fetch,
}


def get_tools(
    permission_context: ToolPermissionContext | None = None,
) -> list[GrokTool]:
    ctx = permission_context or ToolPermissionContext()
    return [t for t in PORTED_TOOLS if not ctx.is_denied(t.name)]


def get_tool(name: str) -> GrokTool | None:
    return next((t for t in PORTED_TOOLS if t.name == name), None)


def execute_tool(
    name: str,
    payload: dict[str, Any] | str,
    permission_context: ToolPermissionContext | None = None,
) -> ToolResult:
    import json
    ctx = permission_context or ToolPermissionContext()
    if ctx.is_denied(name):
        return ToolResult(name, False, "", f"Tool '{name}' is denied by permission context.")
    handler = _TOOL_HANDLERS.get(name)
    if handler is None:
        return ToolResult(name, False, "", f"Unknown tool: {name}")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = {"command": payload}
    return handler(payload)


def render_tool_index(
    limit: int = 20,
    permission_context: ToolPermissionContext | None = None,
) -> str:
    tools = get_tools(permission_context=permission_context)
    lines = [f"Available tools ({len(tools)}):", ""]
    for t in tools[:limit]:
        lines.append(f"  {t.name} — {t.description}")
    return "\n".join(lines)
