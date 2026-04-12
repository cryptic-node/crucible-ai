"""CLI entry point for Grokenstein.

Running ``python -m grokenstein.main`` will start an interactive chat
session with the assistant.  The CLI is deliberately simple to keep
dependencies minimal; you can enhance it using libraries like
``prompt_toolkit`` in the future.  Messages are persisted via the
``MemoryManager`` so context is retained across runs.
"""

import argparse
from .runtime import ChatRuntime


def main() -> None:
    """Start an interactive chat session.

    The loop continues until the user types ``exit`` or sends an EOF
    (Ctrl‑D).  Conversation history is stored under ``data/memory.json``.
    You may specify an optional conversation identifier on the command line
    via ``--id``.  This allows multiple sessions to maintain independent
    histories.
    """
    parser = argparse.ArgumentParser(description="Run a Grokenstein chat session")
    parser.add_argument(
        "--id",
        dest="conversation_id",
        default="default",
        help="Unique identifier for the conversation (default: %(default)s)",
    )
    parser.add_argument(
        "--workspace",
        dest="workspace",
        default=None,
        help=(
            "Path to the workspace directory where file operations occur. "
            "Defaults to a 'workspace' directory alongside the package."
        ),
    )
    args = parser.parse_args()
    runtime = ChatRuntime(conversation_id=args.conversation_id, workspace_root=args.workspace)
    # Basic banner
    from . import __version__
    print(f"Grokenstein v{__version__} – your private assistant\n")
    print("Type 'exit' or press Ctrl‑D to quit.  Type '!help' for commands.\n")
    # Main input loop
    while True:
        try:
            user_input = input(">> ").strip()
        except EOFError:
            # Handle Ctrl‑D gracefully
            print("\nExiting...")
            break
        if not user_input:
            # Skip empty inputs
            continue
        # Recognise built‑in exit commands
        if user_input.lower() in {"exit", "quit"}:
            break
        # Pass the message to the runtime and obtain a response
        response = runtime.handle_user_message(user_input)
        print(response)
    # Flush any final state
    runtime.shutdown()


if __name__ == "__main__":
    main()