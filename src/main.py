from __future__ import annotations

import argparse
import sys

from .commands import execute_command, get_command, get_commands, render_command_index
from .models_router import ModelRouter
from .permissions import ToolPermissionContext
from .query_engine import GrokQueryEngine, QueryEngineConfig
from .runtime import GrokRuntime
from .session_store import list_sessions, load_session, new_session_id
from .tools import execute_tool, get_tool, get_tools, render_tool_index


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="grok",
        description=(
            "Grokenstein — an amalgamation of free, public, and available AI models "
            "mashed up into a private, personal, persistent, network-connected AI."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    chat_parser = subparsers.add_parser("chat", help="Start an interactive chat session.")
    chat_parser.add_argument("--backend", default="", help="Force a specific backend (groq, ollama, openrouter, huggingface).")
    chat_parser.add_argument("--model", default="", help="Force a specific model ID.")
    chat_parser.add_argument("--session", default="", help="Resume a session by ID.")
    chat_parser.add_argument("--max-turns", type=int, default=100)

    run_parser = subparsers.add_parser("run", help="Run a single task (non-interactive).")
    run_parser.add_argument("task", help="The task or prompt to run.")
    run_parser.add_argument("--backend", default="")
    run_parser.add_argument("--model", default="")
    run_parser.add_argument("--max-turns", type=int, default=5)

    setup_parser = subparsers.add_parser("setup", help="Show setup/configuration report.")

    models_parser = subparsers.add_parser("models", help="List available model backends and their status.")

    sessions_parser = subparsers.add_parser("sessions", help="List saved sessions.")

    load_parser = subparsers.add_parser("load-session", help="Load and display a saved session.")
    load_parser.add_argument("session_id", help="Session ID to load.")

    tools_parser = subparsers.add_parser("tools", help="List available tools.")
    tools_parser.add_argument("--limit", type=int, default=20)
    tools_parser.add_argument("--deny-tool", action="append", default=[])
    tools_parser.add_argument("--deny-prefix", action="append", default=[])

    commands_parser = subparsers.add_parser("commands", help="List available slash commands.")
    commands_parser.add_argument("--limit", type=int, default=20)

    exec_tool_parser = subparsers.add_parser("exec-tool", help="Execute a specific tool by name.")
    exec_tool_parser.add_argument("name", help="Tool name.")
    exec_tool_parser.add_argument("payload", help="JSON payload string.")

    bootstrap_parser = subparsers.add_parser("bootstrap", help="Run a bootstrap session for a prompt.")
    bootstrap_parser.add_argument("prompt")
    bootstrap_parser.add_argument("--limit", type=int, default=5)

    summary_parser = subparsers.add_parser("summary", help="Print workspace summary.")

    return parser


def _make_config(args: argparse.Namespace) -> QueryEngineConfig:
    return QueryEngineConfig(
        backend=getattr(args, "backend", ""),
        model=getattr(args, "model", ""),
        max_turns=getattr(args, "max_turns", 10),
    )


def _run_chat(args: argparse.Namespace) -> int:
    config = _make_config(args)
    runtime = GrokRuntime(config=config)

    if args.session:
        try:
            saved = load_session(args.session)
            runtime.engine.session = saved
            print(f"Resumed session {saved.session_id} ({len(saved.messages)} messages).")
        except FileNotFoundError:
            print(f"Session not found: {args.session}", file=sys.stderr)
            return 1

    print("Grokenstein chat. Type /help for commands, /exit to quit.")
    print(f"Backend: {runtime.router.select_backend(config.as_router_config()).name}")
    print()

    while True:
        try:
            user_input = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            cmd_name = user_input[1:].split()[0]
            result = execute_command(cmd_name, {"session": runtime.engine.session})
            print(result.message)
            if cmd_name in ("exit", "quit", "q"):
                break
            continue

        response = runtime.chat(user_input)
        print(f"Grok> {response}")
        print()

    return 0


def _run_task(args: argparse.Namespace) -> int:
    config = _make_config(args)
    runtime = GrokRuntime(config=config)
    results = runtime.run_turn_loop(args.task, max_turns=args.max_turns)
    for idx, result in enumerate(results, start=1):
        print(f"## Turn {idx} (backend={result.backend_used})")
        print(result.output)
        print()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "chat":
        return _run_chat(args)

    if args.command == "run":
        return _run_task(args)

    if args.command == "setup":
        from .context import build_grok_context, render_context
        ctx = build_grok_context()
        print("# Grokenstein Setup Report")
        print()
        print(render_context(ctx))
        print()
        router = ModelRouter()
        print("## Model Backend Status")
        for row in router.backend_status():
            print(f"  {row['backend']:<14} configured={row['configured']}  ({row['key_env']})")
        return 0

    if args.command == "models":
        router = ModelRouter()
        print("Available model backends:")
        print()
        for row in router.backend_status():
            print(f"  {row['backend']:<14} configured={row['configured']}")
            print(f"                 env: {row['key_env']}")
        return 0

    if args.command == "sessions":
        sessions = list_sessions()
        if not sessions:
            print("No saved sessions found.")
            return 0
        print(f"Saved sessions ({len(sessions)}):")
        for sid in sessions:
            print(f"  {sid}")
        return 0

    if args.command == "load-session":
        try:
            session = load_session(args.session_id)
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"Session ID:    {session.session_id}")
        print(f"Messages:      {len(session.messages)}")
        print(f"Input tokens:  {session.input_tokens}")
        print(f"Output tokens: {session.output_tokens}")
        print(f"Backend:       {session.backend_used}")
        print(f"Model:         {session.model_used}")
        return 0

    if args.command == "tools":
        perm = ToolPermissionContext.from_iterables(args.deny_tool, args.deny_prefix)
        print(render_tool_index(limit=args.limit, permission_context=perm))
        return 0

    if args.command == "commands":
        print(render_command_index(limit=args.limit))
        return 0

    if args.command == "exec-tool":
        result = execute_tool(args.name, args.payload)
        print(result.message)
        if result.error:
            print(f"Error: {result.error}", file=sys.stderr)
        return 0 if result.handled else 1

    if args.command == "bootstrap":
        runtime = GrokRuntime()
        session = runtime.bootstrap_session(args.prompt, limit=args.limit)
        print(session.as_markdown())
        return 0

    if args.command == "summary":
        engine = GrokQueryEngine.from_workspace()
        print(engine.render_summary())
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
