"""Simple persistent memory layer for Grokenstein.

This module provides a lightweight wrapper around a JSON file for storing
conversation histories.  Each conversation is keyed by a conversation
identifier and stores an ordered list of messages with ``role`` and
``content`` fields.  While trivial, this component establishes a clear
contract for more sophisticated memory implementations (e.g., SQLite,
vector stores) in the future.

The design is influenced by research on memory for AI assistants, which
emphasises keeping facts outside the LLM context window for later
retrieval【972723700336349†L44-L101】.
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Tuple


class MemoryManager:
    """Manage persistent conversation history stored in a JSON file."""

    def __init__(self, filepath: str) -> None:
        """Initialise the memory manager.

        Args:
            filepath: path to a JSON file used to persist memory.
        """
        self.filepath = filepath
        # Load existing memory or create a new store
        self._data: Dict[str, List[Dict[str, str]]] = {}
        self._load()

    def _load(self) -> None:
        """Load the memory store from disk.

        If the file does not exist, an empty structure is created.  If the file
        is malformed, an exception will be raised.
        """
        if not os.path.exists(self.filepath):
            # Ensure parent directory exists
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            # Write an empty JSON object
            with open(self.filepath, "w", encoding="utf-8") as fh:
                json.dump({}, fh, indent=2)
            self._data = {}
            return
        # Read and parse existing file
        try:
            with open(self.filepath, "r", encoding="utf-8") as fh:
                self._data = json.load(fh) or {}
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Memory file {self.filepath} is not valid JSON: {exc}")

    def _save(self) -> None:
        """Persist the current memory store to disk."""
        # Write to a temporary file first to avoid corruption
        temp_path = f"{self.filepath}.tmp"
        with open(temp_path, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2)
        os.replace(temp_path, self.filepath)

    def load_history(self, conversation_id: str) -> List[Tuple[str, str]]:
        """Return the message history for a given conversation.

        Args:
            conversation_id: the identifier of the conversation

        Returns:
            A list of (role, content) tuples in the order they were added.
        """
        messages = self._data.get(conversation_id, [])
        return [(msg.get("role", "unknown"), msg.get("content", "")) for msg in messages]

    def append_message(self, conversation_id: str, role: str, content: str) -> None:
        """Append a new message to a conversation and persist the store.

        Args:
            conversation_id: unique identifier for the conversation
            role: either ``"user"`` or ``"assistant"``
            content: the text of the message
        """
        if conversation_id not in self._data:
            self._data[conversation_id] = []
        self._data[conversation_id].append({"role": role, "content": content})
        self._save()