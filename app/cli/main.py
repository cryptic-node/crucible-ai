from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="grok",
        description="Grokenstein v1.0.0 — security-first personal operator AI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    chat_p = subparsers.add_parser("chat", help="Interactive chat session")
    chat_p.add_argument("--workspace", default="personal")
    chat_p.add_argument("--trust", default="HIGH", choices=["HIGH", "MEDIUM", "LOW"])
    chat_p.add_argument("--channel", default="cli")
    chat_p.add_argument("--backend", default="")
    chat_p.add_argument("--model", default="")
    chat_p.add_argument("--dry-run", action="store_true")

    run_p = subparsers.add_parser("run", help="Run a single task")
    run_p.add_argument("task")
    run_p.add_argument("--workspace", default="personal")
    run_p.add_argument("--trust", default="HIGH", choices=["HIGH", "MEDIUM", "LOW"])
    run_p.add_argument("--backend", default="")
    run_p.add_argument("--model", default="")
    run_p.add_argument("--dry-run", action="store_true")

    subparsers.add_parser("serve", help="Start FastAPI web server")
    subparsers.add_parser("models", help="List model backends")
    subparsers.add_parser("tools", help="List available tools")
    subparsers.add_parser("workspaces", help="List workspaces")
    subparsers.add_parser("policy", help="Show policy config")

    tool_p = subparsers.add_parser("exec-tool", help="Execute a tool via broker")
    tool_p.add_argument("tool_name")
    tool_p.add_argument("payload", help="JSON payload string")
    tool_p.add_argument("--workspace", default="personal")
    tool_p.add_argument("--trust", default="HIGH")
    tool_p.add_argument("--dry-run", action="store_true")

    return parser


def _run_chat(args: argparse.Namespace) -> int:
    import uuid
    from ..brain.brain import Brain, BrainSession

    brain = Brain()
    session = BrainSession(
        session_id=str(uuid.uuid4()),
        workspace=args.workspace,
        channel=args.channel,
        trust_level=args.trust,
        dry_run=args.dry_run,
        backend=getattr(args, "backend", ""),
        model=getattr(args, "model", ""),
    )

    print(f"Grokenstein v1.0.0 — workspace={args.workspace} trust={args.trust} dry_run={args.dry_run}")
    print("Type /help for commands, /exit to quit.\n")

    while True:
        try:
            user_input = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not user_input:
            continue

        if user_input == "/exit" or user_input == "/quit":
            print("Goodbye.")
            break
        if user_input == "/help":
            print("Commands: /exit, /quit, /tools, /workspaces, /session")
            continue
        if user_input == "/tools":
            from ..broker.broker import get_broker
            print("Tools:", ", ".join(get_broker().list_tools()))
            continue
        if user_input == "/session":
            print(f"Session: {session.session_id} | Workspace: {session.workspace} | Trust: {session.trust_level}")
            continue

        reply = brain.chat(session, user_input)
        print(f"Grok> {reply}\n")

    return 0


def _run_task(args: argparse.Namespace) -> int:
    import uuid
    from ..brain.brain import Brain, BrainSession

    brain = Brain()
    session = BrainSession(
        session_id=str(uuid.uuid4()),
        workspace=args.workspace,
        channel="cli",
        trust_level=args.trust,
        dry_run=args.dry_run,
        backend=getattr(args, "backend", ""),
        model=getattr(args, "model", ""),
    )
    reply = brain.chat(session, args.task)
    print(reply)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "chat":
        return _run_chat(args)

    if args.command == "run":
        return _run_task(args)

    if args.command == "serve":
        import uvicorn
        from ..main import app
        from ..core.config import get_settings
        s = get_settings()
        uvicorn.run(app, host=s.host, port=s.port)
        return 0

    if args.command == "models":
        try:
            from grokenstein.src.models_router import ModelRouter
        except ImportError:
            from ...src.models_router import ModelRouter
        router = ModelRouter()
        print("Available model backends:")
        for row in router.backend_status():
            print(f"  {row['backend']:<14} configured={row['configured']}  ({row['key_env']})")
        return 0

    if args.command == "tools":
        from ..broker.broker import get_broker
        broker = get_broker()
        print("Available tools:")
        for t in broker.list_tools():
            print(f"  {t}")
        return 0

    if args.command == "workspaces":
        from ..core.trust import WORKSPACE_TRUST_DEFAULTS
        print("Workspaces:")
        for name, trust in WORKSPACE_TRUST_DEFAULTS.items():
            print(f"  {name:<20} trust={trust.value}")
        return 0

    if args.command == "policy":
        from ..core.config import get_settings
        s = get_settings()
        print(f"Kill switch: {s.kill_switch}")
        print(f"Policy config path: {s.policy_config_path}")
        return 0

    if args.command == "exec-tool":
        import json
        from ..broker.broker import get_broker
        try:
            payload = json.loads(args.payload)
        except json.JSONDecodeError:
            payload = {"command": args.payload}
        broker = get_broker()
        result = broker.call(
            args.tool_name,
            payload,
            workspace=args.workspace,
            trust_level=args.trust,
            dry_run=args.dry_run,
        )
        if result.success:
            print(result.output)
        else:
            print(f"Error: {result.error}", file=sys.stderr)
        return 0 if result.success else 1

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
