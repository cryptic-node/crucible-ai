"""Chat runtime orchestrator for Grokenstein.

This module ties together the memory manager, policy engine and tool broker
to provide a simple chat loop.  For now the response generation is a
placeholder that simply echoes the user's input.  In future iterations
this component can be extended to call a local language model or
external service to produce intelligent replies, and to leverage
retrieval‑augmented memory.
"""

from __future__ import annotations

import os
import datetime
import shlex
from typing import List, Tuple

from .memory import MemoryManager
from .policy import PolicyEngine
from .tool_broker import ToolBroker
from .logger import AuditLogger


class ChatRuntime:
    """High‑level orchestrator for user messages and assistant replies."""

    def __init__(
        self,
        conversation_id: str = "default",
        workspace_root: str | None = None,
    ) -> None:
        """Create a new runtime.

        Args:
            conversation_id: identifier for this chat session.  Each ID
                corresponds to a separate conversation history.
            workspace_root: optional path to the workspace directory used
                for file operations.  If not provided, a ``workspace``
                directory alongside the package will be used.
        """
        # Determine paths for persistent state
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        data_dir = os.path.join(base_dir, "data")
        # Ensure data directory exists
        os.makedirs(data_dir, exist_ok=True)
        memory_path = os.path.join(data_dir, "memory.json")
        log_path = os.path.join(data_dir, "activity.log")

        # Instantiate core components
        self.conversation_id: str = conversation_id
        self.memory = MemoryManager(memory_path)
        self.policy = PolicyEngine()
        self.logger = AuditLogger(log_path)
        # Pass the workspace root to the tool broker (if None, broker will choose a default)
        self.broker = ToolBroker(policy=self.policy, logger=self.logger, workspace_root=workspace_root)

    def handle_user_message(self, user_message: str) -> str:
        """Process a message from the user and return the assistant's reply.

        The method distinguishes between two kinds of input:

        1. **Tool invocations**, which are prefixed with an exclamation
           point (``!``).  Supported commands are ``!fs`` for filesystem
           operations and ``!shell`` for shell commands.  See below for
           usage.
        2. **Chat messages**, which are stored in memory and answered by
           the assistant via a placeholder echo function.

        Supported tool commands:

        * ``!fs list [path]`` – list the contents of a directory relative
          to the workspace (defaults to ``.`` if omitted).
        * ``!fs read <path>`` – read a file relative to the workspace.
        * ``!fs write <path> <content>`` – write the provided content to
          the file at ``path``.  Intermediate directories will be created.
        * ``!shell <command>`` – run a whitelisted shell command.  The
          allowlist is defined in ``PolicyEngine``.

        Args:
            user_message: the raw text from the user

        Returns:
            The assistant's response as a string.
        """
        stripped = user_message.strip()
        # Built‑in meta commands
        if stripped.lower() in {"!help", "help"}:
            return self._help_message()
        if stripped.lower() in {"!history", "history"}:
            return self._history_message()
        # Determine if this is a tool invocation
        if stripped.startswith("!"):
            try:
                return self._handle_tool_invocation(stripped)
            except Exception as exc:
                return f"Error: {exc}"
        # Otherwise treat as a chat message
        # Record the user message in memory
        self.memory.append_message(self.conversation_id, "user", user_message)
        # Generate the assistant reply using a placeholder function
        assistant_reply = self._generate_reply(user_message)
        # Record the assistant's reply
        self.memory.append_message(self.conversation_id, "assistant", assistant_reply)
        return assistant_reply

    def _handle_tool_invocation(self, command: str) -> str:
        """Parse and execute a tool invocation string.

        The command must begin with ``!``.  This method does not consult
        memory or the LLM; it delegates directly to the tool broker and
        returns the result as a string.

        Args:
            command: raw command string beginning with ``!``

        Returns:
            The result of the tool call formatted for display.
        """
        # Use shlex for robust parsing (handles quoted paths and content)
        try:
            tokens = shlex.split(command)
        except ValueError as exc:
            return f"Error parsing command: {exc}"
        if not tokens:
            return ""
        verb = tokens[0][1:]
        if verb == "fs":
            # Filesystem operations
            if len(tokens) < 2:
                return "Usage: !fs [list/read/write] ..."
            op = tokens[1]
            if op == "list":
                # Optional path argument
                rel_path = tokens[2] if len(tokens) > 2 else "."
                result = self.broker.call("filesystem", "list_dir", rel_path)
                return "\n".join(result) or "(empty)"
            if op == "read":
                if len(tokens) < 3:
                    return "Usage: !fs read <path>"
                rel_path = tokens[2]
                return self.broker.call("filesystem", "read_file", rel_path)
            if op == "write":
                if len(tokens) < 3:
                    return "Usage: !fs write <path> [content]"
                rel_path = tokens[2]
                # If there is content provided on the same line, join the remaining tokens
                if len(tokens) > 3:
                    content = " ".join(tokens[3:])
                else:
                    # Otherwise, prompt the user for multiline input until 'EOF' is entered
                    print(
                        "Enter file content, then type a single line containing 'EOF' to finish:"
                    )
                    lines: List[str] = []
                    while True:
                        try:
                            line = input()
                        except EOFError:
                            break
                        if line.strip() == "EOF":
                            break
                        lines.append(line)
                    content = "\n".join(lines)
                self.broker.call("filesystem", "write_file", rel_path, content)
                return "OK"
            return f"Unknown filesystem operation: {op}"
        elif verb == "shell":
            # A shell command may contain spaces; reconstruct it from the original string
            # The token list includes '!shell' as tokens[0]
            if len(tokens) < 2:
                return "Usage: !shell <command>"
            # Extract the command portion after the '!shell ' prefix
            # Find the position of the first space after '!shell'
            prefix = "!shell"
            if command.startswith(prefix):
                shell_cmd = command[len(prefix):].lstrip()
            else:
                # Fallback: join tokens excluding the first
                shell_cmd = " ".join(tokens[1:])
            return self.broker.call("shell", "run", shell_cmd)
        else:
            return f"Unknown tool prefix: {verb}"

    def _help_message(self) -> str:
        """Return a static help string describing built‑in commands."""
        lines = [
            "Available commands:",
            "  !help                Show this help message.",
            "  !history             Show the conversation history.",
            "  !fs list [path]      List directory contents in the workspace.",
            "  !fs read <path>      Read a file from the workspace.",
            "  !fs write <path> [content]  Write content to a file in the workspace.  If",
            "                           no content is provided on the same line you will",
            "                           be prompted to enter multiline text ending with 'EOF'.",
            "  !shell <command>     Run a whitelisted shell command.",
            "Messages not starting with '!' are sent to the assistant chat system.",
        ]
        return "\n".join(lines)

    def _history_message(self) -> str:
        """Return a formatted conversation history for the current session."""
        history = self.memory.load_history(self.conversation_id)
        if not history:
            return "(no history)"
        # Format the history lines
        formatted = []
        for role, content in history:
            prefix = "YOU" if role == "user" else "ASSISTANT"
            formatted.append(f"[{prefix}] {content}")
        return "\n".join(formatted)

    def _generate_reply(self, user_message: str) -> str:
        """Create a reply for the user.

        This is a stub implementation.  Future versions should include a
        call to a local language model or retrieval augmented generation
        pipeline.  The function can inspect previous conversation history
        via ``self.memory.load_history()``.

        Args:
            user_message: the message provided by the user

        Returns:
            A simple echo reply.
        """
        # For demonstration, just echo the input with a prefix
        return f"You said: {user_message} (NOTE: language model not yet integrated)"

    def shutdown(self) -> None:
        """Clean up resources before exiting.

        Currently this method is a placeholder.  It could flush buffered
        state, close database connections or perform other teardown tasks.
        """
        # In the future, any necessary teardown can be implemented here
        pass