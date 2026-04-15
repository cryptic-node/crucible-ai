from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import json


@dataclass
class DurableFact:
    workspace: str
    key: str
    value: str
    source: str
    created_at: str


class MemoryStore:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "facts.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def _load_all(self) -> list[dict]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save_all(self, items: list[dict]) -> None:
        self.path.write_text(json.dumps(items, indent=2), encoding="utf-8")

    def promote(self, workspace: str, key: str, value: str, source: str) -> DurableFact:
        fact = DurableFact(
            workspace=workspace,
            key=key,
            value=value,
            source=source,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        items = self._load_all()
        items = [i for i in items if not (i["workspace"] == workspace and i["key"] == key)]
        items.append(asdict(fact))
        self._save_all(items)
        return fact

    def list_for_workspace(self, workspace: str) -> list[DurableFact]:
        return [DurableFact(**item) for item in self._load_all() if item["workspace"] == workspace]

    def get(self, workspace: str, key: str) -> DurableFact | None:
        for item in self._load_all():
            if item["workspace"] == workspace and item["key"] == key:
                return DurableFact(**item)
        return None
