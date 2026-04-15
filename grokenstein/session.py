from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json

from .history import History


@dataclass
class SessionState:
    session_id: str
    mode: str = "plan"
    active_task_id: str | None = None
    history: list[dict[str, str]] = field(default_factory=list)


class SessionStore:
    def __init__(self, data_dir: Path) -> None:
        self.dir = data_dir / "sessions"
        self.dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, session_id: str) -> Path:
        return self.dir / f"{session_id}.json"

    def load(self, session_id: str) -> SessionState:
        path = self.path_for(session_id)
        if not path.exists():
            return SessionState(session_id=session_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        return SessionState(**payload)

    def save(self, state: SessionState) -> None:
        self.path_for(state.session_id).write_text(
            json.dumps(asdict(state), indent=2),
            encoding="utf-8",
        )
