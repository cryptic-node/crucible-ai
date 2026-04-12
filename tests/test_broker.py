from __future__ import annotations

from grokenstein.approvals import PendingApprovalStore
from grokenstein.logger import AuditLogger
from grokenstein.policy import PolicyEngine
from grokenstein.tool_broker import ToolBroker


def test_broker_write_approval_round_trip(tmp_path):
    workspace = tmp_path / "workspace"
    logger = AuditLogger(str(tmp_path / "activity.jsonl"))
    approvals = PendingApprovalStore(str(tmp_path / "approvals.json"))
    policy = PolicyEngine(
        shell_allowlist=("ls", "echo", "pwd", "whoami", "date"),
        kill_switch=False,
        require_approval_for_write=True,
        require_approval_for_shell=True,
    )
    broker = ToolBroker(policy=policy, logger=logger, approvals=approvals, workspace_root=workspace)

    result = broker.request_tool_call("session1", "filesystem", "write_file", "note.txt", "hello")
    assert result.status == "approval_required"
    assert result.request_id is not None

    approved = broker.approve("session1", result.request_id)
    assert approved.status == "executed"
    assert (workspace / "note.txt").read_text(encoding="utf-8") == "hello"
