"""Tests for Policy Engine — deny paths, approval paths, simulation paths, kill switch."""
from __future__ import annotations

import pytest

from ..policy.engine import PolicyEngine
from ..schemas.policy import PolicyDecisionEnum, PolicyRequest


def make_request(**kwargs) -> PolicyRequest:
    defaults = dict(
        workspace="personal",
        channel="web",
        trust_level="HIGH",
        tool_name=None,
        action_type="generic",
        risk_level="low",
        dry_run=False,
        input_data=None,
    )
    defaults.update(kwargs)
    return PolicyRequest(**defaults)


class TestPolicyEngine:
    def setup_method(self):
        self.engine = PolicyEngine(policy_config={})

    def test_allow_basic_read(self):
        req = make_request(tool_name="filesystem_read", trust_level="HIGH")
        dec = self.engine.evaluate(req)
        assert dec.decision == PolicyDecisionEnum.allow

    def test_deny_finance_low_trust(self):
        req = make_request(tool_name="finance_balance", trust_level="LOW")
        dec = self.engine.evaluate(req)
        assert dec.decision == PolicyDecisionEnum.deny
        assert "HIGH trust" in dec.explanation

    def test_deny_finance_medium_trust(self):
        req = make_request(tool_name="finance_balance", trust_level="MEDIUM")
        dec = self.engine.evaluate(req)
        assert dec.decision == PolicyDecisionEnum.deny

    def test_finance_high_trust_requires_simulation(self):
        req = make_request(tool_name="finance_balance", trust_level="HIGH", dry_run=False)
        dec = self.engine.evaluate(req)
        assert dec.decision == PolicyDecisionEnum.require_simulation

    def test_finance_high_trust_dry_run_allowed(self):
        req = make_request(tool_name="finance_balance", trust_level="HIGH", dry_run=True)
        dec = self.engine.evaluate(req)
        assert dec.decision == PolicyDecisionEnum.allow

    def test_deny_sensitive_tool_low_trust(self):
        req = make_request(tool_name="shell", trust_level="LOW")
        dec = self.engine.evaluate(req)
        assert dec.decision == PolicyDecisionEnum.deny
        assert "LOW trust" in dec.explanation

    def test_identity_tool_escalate_low_trust(self):
        req = make_request(tool_name="nostr_publish", trust_level="LOW")
        dec = self.engine.evaluate(req)
        assert dec.decision == PolicyDecisionEnum.escalate_channel

    def test_identity_tool_require_approval_high_trust(self):
        req = make_request(tool_name="nostr_publish", trust_level="HIGH")
        dec = self.engine.evaluate(req)
        assert dec.decision == PolicyDecisionEnum.require_approval

    def test_kill_switch_denies_all(self):
        engine = PolicyEngine(policy_config={})
        engine.settings = type("FakeSettings", (), {"kill_switch": True, "policy_config_path": "nonexistent.yaml"})()
        req = make_request(tool_name="filesystem_read", trust_level="HIGH")
        dec = engine.evaluate(req)
        assert dec.decision == PolicyDecisionEnum.deny
        assert dec.kill_switch_active

    def test_workspace_kill_switch(self):
        engine = PolicyEngine(policy_config={"workspaces": {"dangerous": {"kill_switch": True}}})
        req = make_request(workspace="dangerous", tool_name="filesystem_read", trust_level="HIGH")
        dec = engine.evaluate(req)
        assert dec.decision == PolicyDecisionEnum.deny
        assert dec.kill_switch_active

    def test_workspace_denied_tool(self):
        engine = PolicyEngine(policy_config={"workspaces": {"personal": {"denied_tools": ["shell"]}}})
        req = make_request(workspace="personal", tool_name="shell", trust_level="HIGH")
        dec = engine.evaluate(req)
        assert dec.decision == PolicyDecisionEnum.deny
        assert "denied" in dec.explanation.lower()

    def test_simulation_required_for_high_risk_action(self):
        req = make_request(action_type="sign", risk_level="high", tool_name=None, trust_level="HIGH", dry_run=False)
        dec = self.engine.evaluate(req)
        assert dec.decision == PolicyDecisionEnum.require_simulation

    def test_critical_risk_requires_approval(self):
        req = make_request(action_type="generic", risk_level="critical", tool_name=None, trust_level="HIGH")
        dec = self.engine.evaluate(req)
        assert dec.decision == PolicyDecisionEnum.require_approval

    def test_low_trust_read_allowed(self):
        req = make_request(tool_name="web_fetch", trust_level="LOW")
        dec = self.engine.evaluate(req)
        assert dec.decision == PolicyDecisionEnum.allow

    def test_medium_trust_shell_allowed(self):
        req = make_request(tool_name="shell", trust_level="MEDIUM")
        dec = self.engine.evaluate(req)
        assert dec.decision == PolicyDecisionEnum.allow

    def test_workspace_allowed_trust_levels_enforced_low_rejected(self):
        """Infrastructure workspace only allows HIGH — LOW must be denied."""
        engine = PolicyEngine(policy_config={
            "workspaces": {
                "infrastructure": {
                    "allowed_trust_levels": ["HIGH"],
                }
            }
        })
        req = make_request(workspace="infrastructure", tool_name="web_fetch", trust_level="LOW")
        dec = engine.evaluate(req)
        assert dec.decision == PolicyDecisionEnum.deny
        assert "not permitted" in dec.explanation.lower() or "allowed trust" in dec.explanation.lower()

    def test_workspace_allowed_trust_levels_enforced_medium_rejected(self):
        """Infrastructure workspace only allows HIGH — MEDIUM must be denied."""
        engine = PolicyEngine(policy_config={
            "workspaces": {
                "infrastructure": {
                    "allowed_trust_levels": ["HIGH"],
                }
            }
        })
        req = make_request(workspace="infrastructure", tool_name="web_fetch", trust_level="MEDIUM")
        dec = engine.evaluate(req)
        assert dec.decision == PolicyDecisionEnum.deny

    def test_workspace_allowed_trust_levels_high_permitted(self):
        """Infrastructure workspace allows HIGH — should pass through."""
        engine = PolicyEngine(policy_config={
            "workspaces": {
                "infrastructure": {
                    "allowed_trust_levels": ["HIGH"],
                }
            }
        })
        req = make_request(workspace="infrastructure", tool_name="web_fetch", trust_level="HIGH")
        dec = engine.evaluate(req)
        assert dec.decision == PolicyDecisionEnum.allow

    def test_workspace_with_no_trust_constraint_allows_low(self):
        """Workspace with no allowed_trust_levels should not deny on trust level alone."""
        engine = PolicyEngine(policy_config={"workspaces": {"personal": {}}})
        req = make_request(workspace="personal", tool_name="web_fetch", trust_level="LOW")
        dec = engine.evaluate(req)
        assert dec.decision == PolicyDecisionEnum.allow

    def test_consulting_medium_trust_allowed(self):
        """Consulting workspace allows MEDIUM trust."""
        engine = PolicyEngine(policy_config={
            "workspaces": {
                "consulting": {
                    "allowed_trust_levels": ["HIGH", "MEDIUM"],
                }
            }
        })
        req = make_request(workspace="consulting", tool_name="web_fetch", trust_level="MEDIUM")
        dec = engine.evaluate(req)
        assert dec.decision == PolicyDecisionEnum.allow

    def test_consulting_low_trust_denied(self):
        """Consulting workspace does not allow LOW trust."""
        engine = PolicyEngine(policy_config={
            "workspaces": {
                "consulting": {
                    "allowed_trust_levels": ["HIGH", "MEDIUM"],
                }
            }
        })
        req = make_request(workspace="consulting", tool_name="web_fetch", trust_level="LOW")
        dec = engine.evaluate(req)
        assert dec.decision == PolicyDecisionEnum.deny


class TestPolicyDBOverrides:
    """Integration tests for DB-backed workspace policy overrides merged into PolicyEngine."""

    def test_db_override_kill_switch_denies_all_tools(self):
        """DB PolicyConfig kill_switch=True for a workspace should deny all tools in that workspace."""
        engine = PolicyEngine(policy_config={})
        engine.load_db_policy_overrides({"secure_workspace": {"kill_switch": True}})
        req = make_request(workspace="secure_workspace", tool_name="filesystem_read", trust_level="HIGH")
        dec = engine.evaluate(req)
        assert dec.decision == PolicyDecisionEnum.deny
        assert dec.kill_switch_active

    def test_db_override_denied_tools_blocks_shell(self):
        """DB PolicyConfig denied_tools=['shell'] should block shell in that workspace."""
        engine = PolicyEngine(policy_config={})
        engine.load_db_policy_overrides({"consulting": {"denied_tools": ["shell"]}})
        req = make_request(workspace="consulting", tool_name="shell", trust_level="HIGH", action_type="execute", risk_level="medium")
        dec = engine.evaluate(req)
        assert dec.decision == PolicyDecisionEnum.deny
        assert "shell" in dec.explanation

    def test_db_override_allowed_trust_levels_deny_low(self):
        """DB PolicyConfig allowed_trust_levels=['HIGH'] should deny LOW trust in that workspace."""
        engine = PolicyEngine(policy_config={})
        engine.load_db_policy_overrides({"infrastructure": {"allowed_trust_levels": ["HIGH"]}})
        req = make_request(workspace="infrastructure", tool_name="filesystem_read", trust_level="LOW")
        dec = engine.evaluate(req)
        assert dec.decision == PolicyDecisionEnum.deny

    def test_db_override_allows_when_matching_trust(self):
        """DB override with allowed_trust_levels=['HIGH','MEDIUM'] should allow MEDIUM trust."""
        engine = PolicyEngine(policy_config={})
        engine.load_db_policy_overrides({"consulting": {"allowed_trust_levels": ["HIGH", "MEDIUM"]}})
        req = make_request(workspace="consulting", tool_name="filesystem_read", trust_level="MEDIUM")
        dec = engine.evaluate(req)
        assert dec.decision == PolicyDecisionEnum.allow

    def test_db_override_merged_with_yaml_config(self):
        """DB overrides should merge with and extend YAML base config."""
        engine = PolicyEngine(policy_config={
            "workspaces": {
                "consulting": {"denied_tools": ["bitcoin_pay"]},
            }
        })
        engine.load_db_policy_overrides({"consulting": {"allowed_trust_levels": ["HIGH"]}})
        merged = engine._effective_config()
        ws = merged["workspaces"]["consulting"]
        assert "denied_tools" in ws
        assert "allowed_trust_levels" in ws

    def test_db_override_does_not_affect_other_workspaces(self):
        """DB overrides for one workspace must not bleed into another."""
        engine = PolicyEngine(policy_config={})
        engine.load_db_policy_overrides({"restricted": {"kill_switch": True}})
        req = make_request(workspace="personal", tool_name="filesystem_read", trust_level="HIGH")
        dec = engine.evaluate(req)
        assert dec.decision == PolicyDecisionEnum.allow
