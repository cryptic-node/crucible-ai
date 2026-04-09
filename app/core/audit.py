from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("grokenstein.audit")


def _hash_input(data: Any) -> str:
    normalized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


class AuditLogger:
    """
    Structured JSON audit logger for all sensitive actions.

    Writes to:
    1. Application log (always, via structlog / logging)
    2. File (append-only JSON lines) — when audit_log_file is configured
    3. AuditLog DB table — when write_db=True and Postgres is reachable
       (async write dispatched via asyncio.create_task or run_until_complete)
    """

    def __init__(
        self,
        log_file: Optional[str] = None,
        write_db: bool = False,
    ) -> None:
        self.log_file = log_file
        self.write_db = write_db
        self._file_handle = None
        self._in_memory: list[dict[str, Any]] = []
        if log_file:
            path = Path(log_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._file_handle = open(path, "a", encoding="utf-8")

    def log(
        self,
        *,
        workspace: str,
        actor: str,
        action: str,
        tool_name: Optional[str] = None,
        input_data: Any = None,
        policy_decision: str = "unknown",
        approval_status: str = "not_required",
        dry_run: bool = False,
        result_summary: str = "",
        error: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> dict[str, Any]:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "workspace": workspace,
            "actor": actor,
            "action": action,
            "tool_name": tool_name,
            "input_hash": _hash_input(input_data) if input_data is not None else None,
            "policy_decision": policy_decision,
            "approval_status": approval_status,
            "dry_run": dry_run,
            "result_summary": result_summary,
            "error": error,
            "correlation_id": correlation_id or str(uuid.uuid4()),
        }
        self._write(record)
        return record

    def _write(self, record: dict[str, Any]) -> None:
        line = json.dumps(record)
        logger.info(line)
        if self._file_handle:
            self._file_handle.write(line + "\n")
            self._file_handle.flush()
        self._in_memory.append(record)
        if self.write_db:
            self._write_db_async(record)

    def _write_db_async(self, record: dict[str, Any]) -> None:
        """Fire-and-forget async DB write. Creates a task if a loop is running."""
        import asyncio

        async def _do_write():
            try:
                from ..db.engine import session_factory
                factory = session_factory()
                async with factory() as db:
                    from ..db.repository import AuditRepository
                    repo = AuditRepository(db_session=db)
                    await repo.write(record)
            except Exception as exc:
                logger.warning(f"Audit DB write failed: {exc}")

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_do_write())
        except RuntimeError:
            pass

    def get_records(self) -> list[dict[str, Any]]:
        return list(self._in_memory)

    def close(self) -> None:
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None

    def __del__(self) -> None:
        self.close()


_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    global _audit_logger
    if _audit_logger is None:
        from .config import get_settings
        settings = get_settings()
        _audit_logger = AuditLogger(
            log_file=settings.audit_log_file,
            write_db=settings.audit_log_db,
        )
    return _audit_logger


def reset_audit_logger(logger_instance: Optional[AuditLogger] = None) -> None:
    global _audit_logger
    if _audit_logger:
        _audit_logger.close()
    _audit_logger = logger_instance
