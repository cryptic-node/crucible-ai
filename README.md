# Grokenstein v0.0.3

Grokenstein is an experimental personal AI assistant designed to run on your own
hardware.  It provides a conversational interface, a simple persistent memory
store, and a mechanism for safely executing a small number of tools such as
reading or writing files and running whitelisted shell commands.  This
repository contains a minimal implementation intended to serve as a starting
point for further development.

## Goals and non‑goals

The initial release targets a **private, local‑only assistant**.  It is not
connected to any remote API by default and does not attempt to perform
autonomous actions on your behalf.  Instead it focuses on a robust
architecture that makes it easy to add features later without sacrificing
security or auditability.  In particular we aim to:

* **Protect your data.**  All conversation history and memory are stored on
  disk under the `data/` directory.  External network calls are disabled in
  this version.
* **Enforce least privilege.**  A policy engine and a tool broker mediate
  every tool call, inspired by agent security frameworks【202387827095724†L13-L40】.
* **Make memory persistent.**  Messages are saved to a simple JSON file so
  they can be recalled across restarts.  This design echoes research into
  long‑term memory for assistants【972723700336349†L44-L101】.
* **Offer a clean separation of concerns.**  The chat loop lives in
  `runtime.py`, the policy engine in `policy.py`, tools in the `tools/`
  package, and memory management in `memory.py`.

We intentionally **do not** include any networked model inference, Nostr
integration or Lightning key management in this release.  Those features will
be added incrementally once the baseline is stable.

## Directory structure

```
grokenstein_v0.0.3/
├── README.md          – this file
├── requirements.txt   – Python dependencies
├── grokenstein/
│   ├── __init__.py
│   ├── main.py        – entry point for the CLI interface
│   ├── runtime.py     – top‑level chat loop and orchestrator
│   ├── memory.py      – simple JSON backed memory manager
│   ├── tool_broker.py – mediator for tool calls
│   ├── policy.py      – policy engine defining what is allowed
│   ├── logger.py      – simple audit logger
│   └── tools/
│       ├── __init__.py
│       ├── filesystem.py – safe file read/write operations
│       └── shell.py      – whitelisted shell command runner
└── data/
    └── memory.json    – persisted conversation history (created at runtime)
```

The `workspaces/` directory is not used in this version but is reserved for
future support of multiple trust domains as described in Grokenstein’s
architecture【202387827095724†L13-L40】.  Logging is written to
`data/activity.log`.

## Installation

This project requires Python 3.8 or later.  No external dependencies are
strictly necessary, although optional libraries such as `prompt_toolkit` can
improve the command‑line experience.  To install the baseline environment run:

```sh
cd grokenstein_v0.0.2
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Running Grokenstein

Start the assistant via the command line:

```sh
python -m grokenstein.main --id mysession --workspace /path/to/workspace
```

You will see a prompt (`>>`) asking you to enter messages.  In this version
the assistant responds by echoing your input and maintaining a running
history, and it also supports a handful of built‑in commands:

* `!help` – display a short summary of available commands.
* `!history` – show the conversation history for the current session.
* `!fs list [path]` – list the contents of a directory relative to the
  workspace (defaults to `.`).
* `!fs read <path>` – read a file relative to the workspace.
* `!fs write <path> <content>` – write content to a file relative to the
  workspace.
* `!shell <command>` – run a whitelisted shell command (see `PolicyEngine` for the allowlist).

You can terminate the session by typing `exit` or pressing `Ctrl‑D`.

## New in v0.0.2

This release adds several quality‑of‑life improvements over the previous
prototype:

* **Built‑in help and history.**  You can type `!help` for a list of
  available commands and `!history` to print your conversation so far.
* **Interactive file writes.**  The `!fs write` command now supports
  quoted paths and will prompt you for multiline content if you omit
  a content argument.
* **Workspace configuration.**  A new `--workspace` command line flag lets
  you choose where file operations occur.
* **Improved command parsing.**  `shlex` is used for robust parsing of
  quoted paths and content, and error messages have been refined.
* **Version bump.**  The internal version constant has been updated to
  `0.0.3` and directory references have been updated accordingly.

These enhancements make it easier to explore the assistant and begin
customising its behaviour without needing to inspect the source code directly.
terminate the session by typing `exit` or pressing `Ctrl‑D`.

## Extending the assistant

The core architecture is designed to be extensible.  To add a new tool, place
a new module inside `grokenstein/tools/` and register it in
`tool_broker.py`.  Tools should validate their inputs and consult the
`PolicyEngine` before performing any side effects.  Consult the in‑code
documentation for more details.

Future versions may incorporate local language models (via [Ollama],
[Groq] or similar), richer retrieval augmented generation, Nostr and
Lightning integration, and multiple workspaces.  For the moment, this
repository should be seen as a stepping stone towards those goals.

## References

This project draws inspiration from several sources.  The Grokenstein
architecture and threat model emphasise a layered approach where a brain
component sends requests through a policy‑checking broker【202387827095724†L13-L40】.
Research on open‑source memory layers like Mem0 shows why persistent memory
is important for local assistants【972723700336349†L44-L101】.  IBM’s security
guidelines recommend least‑privilege controls, sandboxing and continuous
logging for AI agents【315594017234579†L69-L82】.  All of these ideas have
influenced the design of this minimal implementation.
