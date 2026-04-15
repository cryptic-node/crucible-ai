from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass
class Settings:
    workspace_root: Path
    data_dir: Path
    model_backend: str = "stub"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    audit_log_file: Path | None = None
    shell_timeout: int = 10

    @classmethod
    def from_args(
        cls,
        workspace_root: str | Path,
        data_dir: str | Path,
    ) -> "Settings":
        workspace = Path(workspace_root).expanduser().resolve()
        data = Path(data_dir).expanduser().resolve()
        audit_file = data / "audit.jsonl"
        backend = os.environ.get("GROK_BACKEND", "stub").strip() or "stub"
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        model = os.environ.get("OLLAMA_MODEL", "llama3")
        timeout = int(os.environ.get("GROK_SHELL_TIMEOUT", "10"))
        return cls(
            workspace_root=workspace,
            data_dir=data,
            model_backend=backend,
            ollama_base_url=base_url,
            ollama_model=model,
            audit_log_file=audit_file,
            shell_timeout=timeout,
        )
