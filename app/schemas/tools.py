from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel


class FilesystemReadInput(BaseModel):
    path: str
    dry_run: bool = False


class FilesystemWriteInput(BaseModel):
    path: str
    content: str
    dry_run: bool = False


class FilesystemListInput(BaseModel):
    path: str
    dry_run: bool = False


class ShellInput(BaseModel):
    command: str
    timeout: Optional[int] = None
    dry_run: bool = False


class WebFetchInput(BaseModel):
    url: str
    max_bytes: Optional[int] = None
    timeout: Optional[int] = None
    dry_run: bool = False


class ToolResult(BaseModel):
    tool_name: str
    success: bool
    output: str = ""
    error: Optional[str] = None
    dry_run: bool = False
    metadata: Dict[str, Any] = {}
