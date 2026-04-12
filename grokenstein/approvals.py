from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class PendingApproval:
    request_id: str
    session_id: str
    tool_name: str
    method_name: str
    args: List[Any]
    kwargs: Dict[str, Any]
    reason: str
    created_at: str


class PendingApprovalStore:
    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self._data: Dict[str, Dict[str, Any]] = {}
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
            raise RuntimeError(f"Approval store {self.filepath} is not valid JSON: {exc}") from exc

    def _save(self) -> None:
        temp_path = f"{self.filepath}.tmp"
        with open(temp_path, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2)
        os.replace(temp_path, self.filepath)

    def create(
        self,
        session_id: str,
        tool_name: str,
        method_name: str,
        args: List[Any],
        kwargs: Dict[str, Any],
        reason: str,
    ) -> PendingApproval:
        request = PendingApproval(
            request_id=uuid.uuid4().hex[:12],
            session_id=session_id,
            tool_name=tool_name,
            method_name=method_name,
            args=args,
            kwargs=kwargs,
            reason=reason,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._data[request.request_id] = asdict(request)
        self._save()
        return request

    def get(self, request_id: str) -> Optional[PendingApproval]:
        item = self._data.get(request_id)
        if not item:
            return None
        return PendingApproval(**item)

    def list_for_session(self, session_id: str) -> List[PendingApproval]:
        approvals = [
            PendingApproval(**item)
            for item in self._data.values()
            if item.get("session_id") == session_id
        ]
        approvals.sort(key=lambda approval: approval.created_at)
        return approvals

    def pop(self, request_id: str) -> Optional[PendingApproval]:
        item = self._data.pop(request_id, None)
        if item is None:
            return None
        self._save()
        return PendingApproval(**item)

    def remove(self, request_id: str) -> Optional[PendingApproval]:
        return self.pop(request_id)
