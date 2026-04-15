from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass


@dataclass
class ToolResult:
    success: bool
    output: str = ""
    error: str = ""


class FilesystemTool:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)

    def _resolve_safe(self, rel_path: str) -> Path:
        candidate = (self.workspace_root / rel_path).resolve()
        if self.workspace_root not in candidate.parents and candidate != self.workspace_root:
            raise ValueError(f"Path outside workspace: {rel_path}")
        return candidate

    def list(self, rel_path: str = ".") -> ToolResult:
        try:
            path = self._resolve_safe(rel_path)
            if not path.exists():
                return ToolResult(False, error=f"Path not found: {rel_path}")
            if not path.is_dir():
                return ToolResult(False, error=f"Not a directory: {rel_path}")
            entries = sorted(p.name + ("/" if p.is_dir() else "") for p in path.iterdir())
            return ToolResult(True, output="\n".join(entries) if entries else "(empty)")
        except Exception as exc:
            return ToolResult(False, error=str(exc))

    def read(self, rel_path: str) -> ToolResult:
        try:
            path = self._resolve_safe(rel_path)
            if not path.exists() or not path.is_file():
                return ToolResult(False, error=f"File not found: {rel_path}")
            return ToolResult(True, output=path.read_text(encoding="utf-8"))
        except Exception as exc:
            return ToolResult(False, error=str(exc))

    def write(self, rel_path: str, content: str) -> ToolResult:
        try:
            path = self._resolve_safe(rel_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return ToolResult(True, output=f"Wrote {len(content)} chars to {rel_path}")
        except Exception as exc:
            return ToolResult(False, error=str(exc))
