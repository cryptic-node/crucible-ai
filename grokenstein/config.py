from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple


TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    lowered = raw.strip().lower()
    if lowered in TRUE_VALUES:
        return True
    if lowered in FALSE_VALUES:
        return False
    return default


@dataclass(slots=True)
class RuntimeConfig:
    base_dir: Path
    data_dir: Path
    workspace_root: Path
    memory_path: Path
    audit_log_path: Path
    approval_store_path: Path
    model_backend: str
    model_name: str
    ollama_base_url: str
    shell_allowlist: Tuple[str, ...]
    kill_switch: bool
    require_approval_for_write: bool
    require_approval_for_shell: bool

    @classmethod
    def from_env(
        cls,
        workspace_root: str | None = None,
        base_dir: str | Path | None = None,
        model_backend: str | None = None,
        model_name: str | None = None,
    ) -> "RuntimeConfig":
        resolved_base_dir = Path(base_dir or Path(__file__).resolve().parent.parent).expanduser().resolve()
        data_dir = resolved_base_dir / "data"
        resolved_workspace = (
            Path(workspace_root).expanduser().resolve()
            if workspace_root
            else (resolved_base_dir / "workspace").resolve()
        )

        allowlist_raw = os.getenv("GROKENSTEIN_SHELL_ALLOWLIST", "ls,echo,pwd,whoami,date")
        shell_allowlist = tuple(
            token.strip() for token in allowlist_raw.split(",") if token.strip()
        ) or ("ls", "echo", "pwd", "whoami", "date")

        config = cls(
            base_dir=resolved_base_dir,
            data_dir=data_dir,
            workspace_root=resolved_workspace,
            memory_path=data_dir / "memory.json",
            audit_log_path=data_dir / "activity.jsonl",
            approval_store_path=data_dir / "approvals.json",
            model_backend=(model_backend or os.getenv("GROKENSTEIN_MODEL_BACKEND", "rule")).strip().lower(),
            model_name=(model_name or os.getenv("GROKENSTEIN_MODEL_NAME", "llama3.2:3b")).strip(),
            ollama_base_url=os.getenv("GROKENSTEIN_OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
            shell_allowlist=shell_allowlist,
            kill_switch=env_bool("GROKENSTEIN_KILL_SWITCH", False),
            require_approval_for_write=env_bool("GROKENSTEIN_APPROVE_WRITES", True),
            require_approval_for_shell=env_bool("GROKENSTEIN_APPROVE_SHELL", True),
        )

        config.data_dir.mkdir(parents=True, exist_ok=True)
        config.workspace_root.mkdir(parents=True, exist_ok=True)
        return config
