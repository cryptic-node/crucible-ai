from __future__ import annotations

import json
import os
from typing import Dict, List, Tuple


class MemoryManager:
    """Simple JSON-backed session transcript store."""

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self._data: Dict[str, List[Dict[str, str]]] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.filepath):
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            with open(self.filepath, "w", encoding="utf-8") as fh:
                json.dump({}, fh, indent=2)
            self._data = {}
            return

        try:
            with open(self.filepath, "r", encoding="utf-8") as fh:
                self._data = json.load(fh) or {}
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Memory file {self.filepath} is not valid JSON: {exc}") from exc

    def _save(self) -> None:
        temp_path = f"{self.filepath}.tmp"
        with open(temp_path, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2)
        os.replace(temp_path, self.filepath)

    def load_history(self, conversation_id: str) -> List[Tuple[str, str]]:
        messages = self._data.get(conversation_id, [])
        return [(msg.get("role", "unknown"), msg.get("content", "")) for msg in messages]

    def append_message(self, conversation_id: str, role: str, content: str) -> None:
        if conversation_id not in self._data:
            self._data[conversation_id] = []
        self._data[conversation_id].append({"role": role, "content": content})
        self._save()
