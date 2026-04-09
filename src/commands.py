from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GrokCommand:
    """Descriptor for a registered Grokenstein slash command."""
    name: str
    description: str
    aliases: tuple[str, ...] = ()

    def render(self) -> str:
        aliases = f" (aliases: {', '.join(self.aliases)})" if self.aliases else ""
        return f"/{self.name}{aliases} — {self.description}"


@dataclass(frozen=True)
class CommandResult:
    """Result of a command execution."""
    command_name: str
    handled: bool
    message: str


PORTED_COMMANDS: list[GrokCommand] = [
    GrokCommand(
        name="help",
        description="Show available commands.",
        aliases=("?",),
    ),
    GrokCommand(
        name="clear",
        description="Clear the current session history.",
    ),
    GrokCommand(
        name="models",
        description="List available AI model backends.",
    ),
    GrokCommand(
        name="session",
        description="Show current session info.",
    ),
    GrokCommand(
        name="save",
        description="Persist the current session to disk.",
    ),
    GrokCommand(
        name="exit",
        description="Exit the Grokenstein chat loop.",
        aliases=("quit", "q"),
    ),
]

_COMMAND_INDEX: dict[str, GrokCommand] = {c.name: c for c in PORTED_COMMANDS}
for _cmd in PORTED_COMMANDS:
    for _alias in _cmd.aliases:
        _COMMAND_INDEX[_alias] = _cmd


def get_commands() -> list[GrokCommand]:
    return list(PORTED_COMMANDS)


def get_command(name: str) -> GrokCommand | None:
    return _COMMAND_INDEX.get(name)


def execute_command(name: str, context: dict[str, Any] | None = None) -> CommandResult:
    """Dispatch a slash command by name, returning a CommandResult."""
    cmd = get_command(name)
    if cmd is None:
        return CommandResult(name, False, f"Unknown command: /{name}")

    if cmd.name == "help":
        lines = ["Available commands:", ""]
        lines.extend(c.render() for c in PORTED_COMMANDS)
        return CommandResult(name, True, "\n".join(lines))

    if cmd.name == "clear":
        return CommandResult(name, True, "Session history cleared.")

    if cmd.name == "models":
        from .models_router import ModelRouter
        router = ModelRouter()
        rows = router.backend_status()
        lines = ["Model backends:", ""]
        for row in rows:
            lines.append(f"  {row['backend']:<14} configured={row['configured']}  ({row['key_env']})")
        return CommandResult(name, True, "\n".join(lines))

    if cmd.name == "session":
        sess_ctx = (context or {}).get("session")
        if sess_ctx:
            msg = (
                f"Session ID:  {sess_ctx.session_id}\n"
                f"Messages:    {len(sess_ctx.messages)}\n"
                f"Backend:     {sess_ctx.backend_used}\n"
                f"Model:       {sess_ctx.model_used}"
            )
        else:
            msg = "No active session."
        return CommandResult(name, True, msg)

    if cmd.name == "save":
        sess_ctx = (context or {}).get("session")
        if not sess_ctx:
            return CommandResult(name, False, "No active session to save.")
        from .session_store import save_session
        path = save_session(sess_ctx)
        return CommandResult(name, True, f"Session saved to {path}")

    if cmd.name == "exit":
        return CommandResult(name, True, "Goodbye.")

    return CommandResult(name, False, f"Command /{name} is registered but has no handler.")


def render_command_index(limit: int = 20) -> str:
    cmds = get_commands()
    lines = [f"Available commands ({len(cmds)}):", ""]
    for c in cmds[:limit]:
        lines.append(f"  {c.render()}")
    return "\n".join(lines)
