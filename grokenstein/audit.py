from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
from typing import Any


@dataclass
class AuditRecord:
    timestamp: str
    event: str
    session_id: str
    details: dict[str, Any]


class AuditLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _hash_payload(self, payload: Any) -> str:
        encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:16]

    def log(self, event: str, session_id: str, **details: Any) -> None:
        if "payload" in details:
            details["payload_hash"] = self._hash_payload(details.pop("payload"))
        record = AuditRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event=event,
            session_id=session_id,
            details=details,
        )
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), sort_keys=True) + "\n")
