from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from datetime import datetime, timezone
import json

from .models import Task, TaskStep, Checkpoint


class TaskStorage:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "tasks.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def _load_raw(self) -> list[dict]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save_raw(self, rows: list[dict]) -> None:
        self.path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    def list(self) -> list[Task]:
        tasks: list[Task] = []
        for row in self._load_raw():
            row["steps"] = [TaskStep(**step) for step in row.get("steps", [])]
            row["checkpoints"] = [Checkpoint(**cp) for cp in row.get("checkpoints", [])]
            tasks.append(Task(**row))
        return tasks

    def get(self, task_id: str) -> Task | None:
        for task in self.list():
            if task.id == task_id:
                return task
        return None

    def save(self, task: Task) -> None:
        rows = self._load_raw()
        payload = asdict(task)
        replaced = False
        for idx, row in enumerate(rows):
            if row["id"] == task.id:
                rows[idx] = payload
                replaced = True
                break
        if not replaced:
            rows.append(payload)
        self._save_raw(rows)

    def delete(self, task_id: str) -> None:
        rows = [row for row in self._load_raw() if row["id"] != task_id]
        self._save_raw(rows)

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()
