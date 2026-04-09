from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..core.config import get_settings
from ..schemas.tools import FilesystemReadInput, FilesystemWriteInput, FilesystemListInput, ToolResult


def _resolve_safe(path_str: str, workspace_root: str) -> Path:
    """
    Resolve path within workspace_root using is_relative_to() for robust enforcement.
    Raises ValueError on any path that resolves outside the workspace root.
    Handles sibling-path attacks like ../workspace_evil/... correctly.
    """
    root = Path(workspace_root).resolve()
    raw = Path(path_str)
    if raw.is_absolute():
        candidate = raw.resolve()
    else:
        candidate = (root / path_str).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError(
            f"Path traversal denied: '{path_str}' resolves to '{candidate}' "
            f"which is outside workspace root '{root}'"
        )
    return candidate


class FilesystemTool:
    """Filesystem tool with robust workspace path enforcement."""

    name = "filesystem"

    def __init__(self) -> None:
        self.settings = get_settings()

    def read(self, input_data: FilesystemReadInput) -> ToolResult:
        if input_data.dry_run:
            return ToolResult(
                tool_name="filesystem_read",
                success=True,
                output=f"[DRY RUN] Would read file: {input_data.path}",
                dry_run=True,
            )
        try:
            safe_path = _resolve_safe(input_data.path, self.settings.workspace_root)
            if not safe_path.exists():
                return ToolResult(tool_name="filesystem_read", success=False, error=f"File not found: {input_data.path}")
            if not safe_path.is_file():
                return ToolResult(tool_name="filesystem_read", success=False, error=f"Not a file: {input_data.path}")
            content = safe_path.read_text(encoding="utf-8")
            return ToolResult(tool_name="filesystem_read", success=True, output=content, metadata={"path": str(safe_path)})
        except ValueError as exc:
            return ToolResult(tool_name="filesystem_read", success=False, error=str(exc))
        except Exception as exc:
            return ToolResult(tool_name="filesystem_read", success=False, error=f"Read error: {exc}")

    def write(self, input_data: FilesystemWriteInput) -> ToolResult:
        if input_data.dry_run:
            return ToolResult(
                tool_name="filesystem_write",
                success=True,
                output=f"[DRY RUN] Would write {len(input_data.content)} chars to: {input_data.path}",
                dry_run=True,
            )
        try:
            safe_path = _resolve_safe(input_data.path, self.settings.workspace_root)
            safe_path.parent.mkdir(parents=True, exist_ok=True)
            safe_path.write_text(input_data.content, encoding="utf-8")
            return ToolResult(
                tool_name="filesystem_write",
                success=True,
                output=f"Written {len(input_data.content)} chars to {input_data.path}",
                metadata={"path": str(safe_path), "bytes_written": len(input_data.content)},
            )
        except ValueError as exc:
            return ToolResult(tool_name="filesystem_write", success=False, error=str(exc))
        except Exception as exc:
            return ToolResult(tool_name="filesystem_write", success=False, error=f"Write error: {exc}")

    def list_dir(self, input_data: FilesystemListInput) -> ToolResult:
        if input_data.dry_run:
            return ToolResult(
                tool_name="filesystem_list",
                success=True,
                output=f"[DRY RUN] Would list directory: {input_data.path}",
                dry_run=True,
            )
        try:
            safe_path = _resolve_safe(input_data.path, self.settings.workspace_root)
            if not safe_path.exists():
                return ToolResult(tool_name="filesystem_list", success=False, error=f"Path not found: {input_data.path}")
            entries = sorted([p.name + ("/" if p.is_dir() else "") for p in safe_path.iterdir()])
            return ToolResult(
                tool_name="filesystem_list",
                success=True,
                output="\n".join(entries),
                metadata={"path": str(safe_path), "count": len(entries)},
            )
        except ValueError as exc:
            return ToolResult(tool_name="filesystem_list", success=False, error=str(exc))
        except Exception as exc:
            return ToolResult(tool_name="filesystem_list", success=False, error=f"List error: {exc}")
