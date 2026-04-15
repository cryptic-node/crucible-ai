from __future__ import annotations

from pathlib import Path

from grokenstein.approval_queue import ApprovalQueue
from grokenstein.audit import AuditLogger
from grokenstein.broker import ToolBroker


def test_write_requires_approval_then_executes(tmp_path: Path):
    approvals = ApprovalQueue(tmp_path)
    audit = AuditLogger(tmp_path / "audit.jsonl")
    broker = ToolBroker("s1", tmp_path / "workspace", approvals, audit)

    first = broker.call("fs.write", {"path": "note.txt", "content": "hello"})
    assert first.requires_approval
    assert first.approval_id

    second = broker.approve(first.approval_id)
    assert second.success
    assert (tmp_path / "workspace" / "note.txt").read_text(encoding="utf-8") == "hello"
