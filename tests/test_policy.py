from __future__ import annotations

from grokenstein.policy import Decision, PolicyEngine


def make_policy() -> PolicyEngine:
    return PolicyEngine(
        shell_allowlist=("ls", "echo", "pwd", "whoami", "date"),
        kill_switch=False,
        require_approval_for_write=True,
        require_approval_for_shell=True,
    )


def test_policy_requires_approval_for_workspace_write():
    decision = make_policy().evaluate("filesystem", "write_file", ("note.txt", "hello"), {})
    assert decision.decision == Decision.REQUIRE_APPROVAL
    assert decision.action_type == "write"


def test_policy_denies_unsafe_shell_command():
    decision = make_policy().evaluate("shell", "run", ("rm -rf /",), {})
    assert decision.decision == Decision.DENY
    assert "allowlist" in decision.reason.lower()
