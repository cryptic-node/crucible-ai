from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import yaml

from ..core.config import get_settings
from ..core.trust import TrustLevel
from ..schemas.policy import PolicyDecision, PolicyDecisionEnum, PolicyRequest

FINANCE_TOOLS = frozenset({"finance_balance", "finance_transfer", "bitcoin_pay", "lightning_pay"})
IDENTITY_TOOLS = frozenset({"nostr_publish", "nostr_sign", "identity_update"})
SENSITIVE_TOOLS = frozenset({"shell", "bash", "write_file", "filesystem_write"}) | FINANCE_TOOLS | IDENTITY_TOOLS

HIGH_RISK_ACTIONS = frozenset({"execute", "write", "delete", "sign", "pay", "publish"})
SIMULATION_REQUIRED_ACTIONS = frozenset({"sign", "pay", "publish", "delete"})


class PolicyEngine:
    """
    Structured policy decision engine.

    Returns a PolicyDecision for every tool call or action request.
    Decisions: allow, deny, require_approval, require_simulation, escalate_channel.

    Policy config sources (merged, DB overrides YAML):
    1. YAML file (policy_config_path setting)
    2. DB PolicyConfig table (loaded via load_db_policy_overrides())
    """

    def __init__(self, policy_config: Optional[Dict[str, Any]] = None) -> None:
        self.settings = get_settings()
        self._config: Dict[str, Any] = policy_config if policy_config is not None else self._load_policy_config()
        self._db_overrides: Dict[str, Any] = {}

    def _load_policy_config(self) -> Dict[str, Any]:
        path = self.settings.policy_config_path
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                pass
        return {}

    def _effective_config(self) -> Dict[str, Any]:
        """Merge base YAML config with DB overrides (DB wins per workspace)."""
        if not self._db_overrides:
            return self._config
        merged = dict(self._config)
        base_workspaces = dict(merged.get("workspaces", {}))
        for ws_name, override in self._db_overrides.items():
            if ws_name in base_workspaces:
                base_workspaces[ws_name] = {**base_workspaces[ws_name], **override}
            else:
                base_workspaces[ws_name] = override
        merged["workspaces"] = base_workspaces
        return merged

    def load_db_policy_overrides(self, overrides: Dict[str, Any]) -> None:
        """
        Inject DB-backed per-workspace policy overrides.
        Call this at startup or when policy configs are updated in DB.
        overrides format: {workspace_name: {kill_switch: bool, ...}}
        """
        self._db_overrides = overrides

    def _check_allowed_trust_levels(
        self,
        workspace_cfg: Dict[str, Any],
        trust: TrustLevel,
        request: PolicyRequest,
    ) -> Optional[PolicyDecision]:
        """
        Enforce per-workspace allowed_trust_levels constraint.
        If the workspace defines allowed_trust_levels and the session trust
        is not in that list, deny the request immediately.
        """
        allowed: List[str] = workspace_cfg.get("allowed_trust_levels", [])
        if not allowed:
            return None
        if trust.value not in allowed:
            return PolicyDecision(
                decision=PolicyDecisionEnum.deny,
                explanation=(
                    f"Trust level '{trust.value}' is not permitted in workspace '{request.workspace}'. "
                    f"Allowed trust levels: {', '.join(allowed)}."
                ),
                workspace=request.workspace,
                tool_name=request.tool_name,
                action_type=request.action_type,
                risk_level=request.risk_level,
                dry_run=request.dry_run,
            )
        return None

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        """Evaluate a PolicyRequest and return a PolicyDecision."""
        trust = TrustLevel(request.trust_level) if request.trust_level in TrustLevel.__members__.values() else TrustLevel.LOW

        if self.settings.kill_switch:
            return PolicyDecision(
                decision=PolicyDecisionEnum.deny,
                explanation="Emergency kill switch is active. All tool execution is denied.",
                workspace=request.workspace,
                tool_name=request.tool_name,
                action_type=request.action_type,
                risk_level=request.risk_level,
                dry_run=request.dry_run,
                kill_switch_active=True,
            )

        config = self._effective_config()
        workspace_cfg = config.get("workspaces", {}).get(request.workspace, {})

        if workspace_cfg.get("kill_switch", False):
            return PolicyDecision(
                decision=PolicyDecisionEnum.deny,
                explanation=f"Workspace '{request.workspace}' kill switch is active.",
                workspace=request.workspace,
                tool_name=request.tool_name,
                action_type=request.action_type,
                risk_level=request.risk_level,
                dry_run=request.dry_run,
                kill_switch_active=True,
            )

        trust_denied = self._check_allowed_trust_levels(workspace_cfg, trust, request)
        if trust_denied is not None:
            return trust_denied

        denied_tools = set(workspace_cfg.get("denied_tools", []))
        if request.tool_name and request.tool_name in denied_tools:
            return PolicyDecision(
                decision=PolicyDecisionEnum.deny,
                explanation=f"Tool '{request.tool_name}' is denied in workspace '{request.workspace}'.",
                workspace=request.workspace,
                tool_name=request.tool_name,
                action_type=request.action_type,
                risk_level=request.risk_level,
                dry_run=request.dry_run,
            )

        if request.tool_name in FINANCE_TOOLS:
            if not trust.allows_finance():
                return PolicyDecision(
                    decision=PolicyDecisionEnum.deny,
                    explanation=f"Finance operations require HIGH trust. Current trust: {trust.value}.",
                    workspace=request.workspace,
                    tool_name=request.tool_name,
                    action_type=request.action_type,
                    risk_level=request.risk_level,
                    dry_run=request.dry_run,
                )
            if not request.dry_run:
                return PolicyDecision(
                    decision=PolicyDecisionEnum.require_simulation,
                    explanation="Finance actions must be simulated first (dry_run=True) before live execution.",
                    workspace=request.workspace,
                    tool_name=request.tool_name,
                    action_type=request.action_type,
                    risk_level="critical",
                    dry_run=request.dry_run,
                )

        if request.tool_name in IDENTITY_TOOLS:
            if not trust.allows_identity_change():
                return PolicyDecision(
                    decision=PolicyDecisionEnum.escalate_channel,
                    explanation=f"Identity-changing operations require HIGH trust and step-up approval. Current trust: {trust.value}.",
                    workspace=request.workspace,
                    tool_name=request.tool_name,
                    action_type=request.action_type,
                    risk_level=request.risk_level,
                    dry_run=request.dry_run,
                )
            return PolicyDecision(
                decision=PolicyDecisionEnum.require_approval,
                explanation="Identity-changing operations require explicit user approval.",
                workspace=request.workspace,
                tool_name=request.tool_name,
                action_type=request.action_type,
                risk_level=request.risk_level,
                dry_run=request.dry_run,
            )

        if trust.is_read_only() and request.tool_name in SENSITIVE_TOOLS:
            return PolicyDecision(
                decision=PolicyDecisionEnum.deny,
                explanation=f"LOW trust channels are read-only. Tool '{request.tool_name}' requires higher trust.",
                workspace=request.workspace,
                tool_name=request.tool_name,
                action_type=request.action_type,
                risk_level=request.risk_level,
                dry_run=request.dry_run,
            )

        if request.action_type in SIMULATION_REQUIRED_ACTIONS and not request.dry_run and request.risk_level in ("high", "critical"):
            return PolicyDecision(
                decision=PolicyDecisionEnum.require_simulation,
                explanation=f"High-risk action '{request.action_type}' requires simulation before execution.",
                workspace=request.workspace,
                tool_name=request.tool_name,
                action_type=request.action_type,
                risk_level=request.risk_level,
                dry_run=request.dry_run,
            )

        if request.risk_level == "critical":
            return PolicyDecision(
                decision=PolicyDecisionEnum.require_approval,
                explanation="Critical risk level requires explicit user approval.",
                workspace=request.workspace,
                tool_name=request.tool_name,
                action_type=request.action_type,
                risk_level=request.risk_level,
                dry_run=request.dry_run,
            )

        return PolicyDecision(
            decision=PolicyDecisionEnum.allow,
            explanation="Request approved by policy engine.",
            workspace=request.workspace,
            tool_name=request.tool_name,
            action_type=request.action_type,
            risk_level=request.risk_level,
            dry_run=request.dry_run,
        )


_engine: Optional[PolicyEngine] = None


def get_policy_engine() -> PolicyEngine:
    global _engine
    if _engine is None:
        _engine = PolicyEngine()
    return _engine


def reset_policy_engine(engine: Optional[PolicyEngine] = None) -> None:
    global _engine
    _engine = engine


async def load_policy_overrides_from_db(db) -> None:
    """
    Load per-workspace policy overrides from the PolicyConfig DB table
    and inject them into the running PolicyEngine instance.
    Called at startup when DB is available.

    Policy evaluation keying is by workspace NAME, not UUID.
    This function resolves PolicyConfig.workspace_id (UUID FK) back to
    workspace name via the Workspace table before merging.
    """
    try:
        from ..db.models import PolicyConfig, Workspace
        from sqlalchemy import select
        result = await db.execute(select(PolicyConfig))
        policy_configs = result.scalars().all()
        if not policy_configs:
            return

        ws_result = await db.execute(select(Workspace))
        uuid_to_name: Dict[str, str] = {ws.id: ws.name for ws in ws_result.scalars().all()}

        overrides: Dict[str, Any] = {}
        for pc in policy_configs:
            ws_name = uuid_to_name.get(pc.workspace_id)
            if not ws_name:
                continue
            ws_override: Dict[str, Any] = {"kill_switch": pc.kill_switch}
            if pc.config_yaml:
                try:
                    extra = yaml.safe_load(pc.config_yaml) or {}
                    ws_override.update(extra)
                except Exception:
                    pass
            overrides[ws_name] = ws_override

        if overrides:
            engine = get_policy_engine()
            engine.load_db_policy_overrides(overrides)
    except Exception:
        pass
