from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import uuid


@dataclass
class ApprovalRequest:
    id: str
    session_id: str
    tool_name: str
    payload: dict
    reason: str
    created_at: str


class ApprovalQueue:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "approvals.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def _load(self) -> list[dict]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, rows: list[dict]) -> None:
        self.path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    def add(self, session_id: str, tool_name: str, payload: dict, reason: str) -> ApprovalRequest:
        req = ApprovalRequest(
            id=str(uuid.uuid4()),
            session_id=session_id,
            tool_name=tool_name,
            payload=payload,
            reason=reason,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        rows = self._load()
        rows.append(asdict(req))
        self._save(rows)
        return req

    def list(self, session_id: str | None = None) -> list[ApprovalRequest]:
        rows = [ApprovalRequest(**row) for row in self._load()]
        if session_id is None:
            return rows
        return [row for row in rows if row.session_id == session_id]

    def get(self, request_id: str | None, session_id: str) -> ApprovalRequest | None:
        rows = self.list(session_id=session_id)
        if request_id:
            for row in rows:
                if row.id == request_id:
                    return row
            return None
        return rows[0] if rows else None

    def remove(self, request_id: str) -> None:
        rows = [row for row in self._load() if row["id"] != request_id]
        self._save(rows)
