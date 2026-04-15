from __future__ import annotations

from dataclasses import dataclass
import re
import shlex
import subprocess


ALLOWLIST = {
    "pwd", "whoami", "date", "uname", "ls", "cat", "grep", "find", "echo", "head", "tail"
}
METACHAR_RE = re.compile(r"[;&|`$(){}<>\\\n]")


@dataclass
class ToolResult:
    success: bool
    output: str = ""
    error: str = ""


class ShellTool:
    def __init__(self, timeout: int = 10) -> None:
        self.timeout = timeout

    def execute(self, command: str) -> ToolResult:
        if METACHAR_RE.search(command):
            return ToolResult(False, error="Shell metacharacters are not allowed")
        try:
            argv = shlex.split(command)
        except Exception as exc:
            return ToolResult(False, error=f"Invalid command syntax: {exc}")
        if not argv:
            return ToolResult(False, error="No command supplied")
        if argv[0].split("/")[-1] not in ALLOWLIST:
            return ToolResult(False, error=f"Command not allowlisted: {argv[0]}")
        try:
            result = subprocess.run(argv, capture_output=True, text=True, timeout=self.timeout)
            output = (result.stdout or "").strip()
            if result.stderr:
                output = (output + "\n[stderr]\n" + result.stderr.strip()).strip()
            if result.returncode != 0:
                return ToolResult(False, output=output, error=f"Exit code {result.returncode}")
            return ToolResult(True, output=output)
        except Exception as exc:
            return ToolResult(False, error=str(exc))
