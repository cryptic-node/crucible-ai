from __future__ import annotations

import argparse

from .config import Settings
from .runtime import GrokensteinRuntime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Grokenstein v0.0.5")
    parser.add_argument("--id", default="default-session", help="Session id")
    parser.add_argument("--workspace", default="./workspace", help="Workspace directory")
    parser.add_argument("--data-dir", default="./data", help="Data directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_args(args.workspace, args.data_dir)
    runtime = GrokensteinRuntime(settings=settings, session_id=args.id)

    print("Grokenstein v0.0.5 – dependable apprentice")
    print("Type 'exit' or press Ctrl-D to quit. Type '!help' for commands.\n")

    while True:
        try:
            line = input(">> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line.strip().lower() in {"exit", "quit"}:
            break
        output = runtime.handle_line(line)
        if output:
            print(output)
    runtime.save()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
