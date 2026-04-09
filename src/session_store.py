from __future__ import annotations

import json
import uuid
from pathlib import Path

from .models import GrokSession


_SESSIONS_DIR = Path(__file__).resolve().parent.parent / ".sessions"


def _ensure_sessions_dir() -> Path:
    _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return _SESSIONS_DIR


def save_session(session: GrokSession) -> str:
    """Persist a GrokSession to disk. Returns the file path."""
    sessions_dir = _ensure_sessions_dir()
    path = sessions_dir / f"{session.session_id}.json"
    payload = {
        "session_id": session.session_id,
        "messages": session.messages,
        "input_tokens": session.input_tokens,
        "output_tokens": session.output_tokens,
        "backend_used": session.backend_used,
        "model_used": session.model_used,
    }
    path.write_text(json.dumps(payload, indent=2))
    return str(path)


def load_session(session_id: str) -> GrokSession:
    """Load a previously saved GrokSession from disk."""
    sessions_dir = _ensure_sessions_dir()
    path = sessions_dir / f"{session_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Session not found: {session_id}")
    payload = json.loads(path.read_text())
    session = GrokSession(session_id=payload["session_id"])
    session.messages = payload.get("messages", [])
    session.input_tokens = payload.get("input_tokens", 0)
    session.output_tokens = payload.get("output_tokens", 0)
    session.backend_used = payload.get("backend_used", "unknown")
    session.model_used = payload.get("model_used", "unknown")
    return session


def new_session_id() -> str:
    return str(uuid.uuid4())


def list_sessions() -> list[str]:
    sessions_dir = _ensure_sessions_dir()
    return [p.stem for p in sessions_dir.glob("*.json")]
