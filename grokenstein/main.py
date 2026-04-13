"""CLI entry point for Grokenstein."""

from __future__ import annotations

import argparse

from . import __version__
from .runtime import ChatRuntime


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Grokenstein chat session")
    parser.add_argument("--id", dest="conversation_id", default="default", help="Unique session identifier")
    parser.add_argument("--workspace", dest="workspace", default=None, help="Workspace directory for file operations")
    parser.add_argument(
        "--model-backend",
        dest="model_backend",
        default=None,
        choices=("rule", "ollama"),
        help="Override the configured model backend",
    )
    parser.add_argument(
        "--model-name",
        dest="model_name",
        default=None,
        help="Override the configured model name",
    )
    args = parser.parse_args()

    runtime = ChatRuntime(
        conversation_id=args.conversation_id,
        workspace_root=args.workspace,
        model_backend=args.model_backend,
        model_name=args.model_name,
    )

    print(f"Grokenstein v{__version__} – governed model runtime\n")
    print("Type 'exit' or press Ctrl-D to quit. Type '!help' for commands.\n")

    while True:
        try:
            user_input = input(">> ").strip()
        except EOFError:
            print("\nExiting...")
            break
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            break
        response = runtime.handle_user_message(user_input)
        if response:
            print(response)

    runtime.shutdown()


if __name__ == "__main__":
    main()
