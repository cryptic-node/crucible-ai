from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any


class AuditLogger:
    """Append-only JSONL audit logger."""

    def __init__(self, log_path: str) -> None:
        self.log_path = log_path
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def log_event(self, event_type: str, **payload: Any) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            **payload,
        }
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    def log_call(self, tool_name: str, method_name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        self.log_event(
            "tool_call_legacy",
            tool_name=tool_name,
            method_name=method_name,
            args=list(args),
            kwargs=kwargs,
        )
