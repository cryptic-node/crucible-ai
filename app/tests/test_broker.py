"""Tests for Tool Broker — schema rejection, unknown tools, policy integration."""
from __future__ import annotations

import pytest

from ..broker.broker import ToolBroker
from ..core.audit import AuditLogger, reset_audit_logger
from ..policy.engine import PolicyEngine, reset_policy_engine


class FakeAuditLogger(AuditLogger):
    def __init__(self):
        self.records = []

    def log(self, **kwargs):
        self.records.append(kwargs)
        return kwargs

    def close(self): pass


def make_broker(policy_config=None, kill_switch=False):
    from ..core.config import get_settings
    fake_audit = FakeAuditLogger()
    reset_audit_logger(fake_audit)
    engine = PolicyEngine(policy_config=policy_config or {})
    if kill_switch:
        engine.settings = type("FakeSettings", (), {
            "kill_switch": True,
            "policy_config_path": "nonexistent.yaml",
        })()
    reset_policy_engine(engine)
    broker = ToolBroker()
    broker._audit = fake_audit
    return broker, fake_audit


class TestToolBroker:
    def setup_method(self):
        self.broker, self.audit = make_broker()

    def test_unknown_tool_rejected(self):
        result = self.broker.call("nonexistent_tool", {}, trust_level="HIGH")
        assert not result.success
        assert "Unknown tool" in (result.error or "")

    def test_schema_validation_failure(self):
        result = self.broker.call("filesystem_read", {"not_a_valid_field": 123}, trust_level="HIGH")
        assert not result.success
        assert "validation" in (result.error or "").lower()

    def test_shell_call_allowed_high_trust(self):
        result = self.broker.call("shell", {"command": "echo hello", "dry_run": True}, trust_level="HIGH")
        assert result.success
        assert "DRY RUN" in result.output or "hello" in result.output

    def test_shell_call_denied_low_trust(self):
        result = self.broker.call("shell", {"command": "echo hello"}, trust_level="LOW")
        assert not result.success
        assert "Policy denied" in (result.error or "")

    def test_kill_switch_denies_all(self):
        broker, _ = make_broker(kill_switch=True)
        result = broker.call("filesystem_read", {"path": "/workspace/test.txt"}, trust_level="HIGH")
        assert not result.success
        assert "kill switch" in (result.error or "").lower()

    def test_audit_record_created(self):
        self.broker.call("filesystem_read", {"path": "/workspace/test.txt", "dry_run": True}, trust_level="HIGH")
        assert len(self.audit.records) > 0

    def test_list_tools(self):
        tools = self.broker.list_tools()
        assert "shell" in tools
        assert "filesystem_read" in tools
        assert "web_fetch" in tools

    def test_dry_run_override(self):
        result = self.broker.call(
            "filesystem_read",
            {"path": "/workspace/test.txt"},
            trust_level="HIGH",
            dry_run=True,
        )
        assert result.success
        assert result.dry_run or "DRY RUN" in result.output
