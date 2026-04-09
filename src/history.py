from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HistoryLog:
    """Append-only in-memory log of conversation turns."""
    entries: list[str] = field(default_factory=list)

    def append(self, entry: str) -> None:
        self.entries.append(entry)

    def tail(self, n: int = 10) -> list[str]:
        return self.entries[-n:]

    def clear(self) -> None:
        self.entries.clear()

    def replay(self) -> tuple[str, ...]:
        return tuple(self.entries)

    def __len__(self) -> int:
        return len(self.entries)
