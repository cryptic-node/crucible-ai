from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class History:
    entries: list[dict[str, str]] = field(default_factory=list)

    def append(self, role: str, content: str) -> None:
        self.entries.append({"role": role, "content": content})

    def tail(self, count: int = 12) -> list[dict[str, str]]:
        return self.entries[-count:]
