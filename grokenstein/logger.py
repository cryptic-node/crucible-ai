"""Audit logging utilities for Grokenstein.

Every tool invocation passes through the ``AuditLogger`` to produce an
append‑only record.  This supports post‑hoc analysis of assistant
behaviour and can help detect misuse or anomalous activity.  For
simplicity the log is written as plain text; a structured format (e.g.,
JSON or CSV) may be preferable in future versions.
"""

from __future__ import annotations

import datetime
import os
from typing import Any, Sequence


class AuditLogger:
    """Write tool invocation records to a log file."""

    def __init__(self, log_path: str) -> None:
        self.log_path = log_path
        # Ensure the parent directory exists
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def log_call(self, tool_name: str, method_name: str, args: Sequence[Any], kwargs: dict) -> None:
        """Append a record of a tool invocation to the log file.

        Args:
            tool_name: name of the tool being invoked
            method_name: method on the tool
            args: positional arguments passed to the method
            kwargs: keyword arguments passed to the method
        """
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        record = (
            f"{timestamp}\ttool={tool_name}\tmethod={method_name}\t"
            f"args={args!r}\tkwargs={kwargs!r}\n"
        )
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(record)