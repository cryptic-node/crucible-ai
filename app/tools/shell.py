from __future__ import annotations

import re
import shlex
import subprocess
from typing import List, Optional

from ..core.config import get_settings
from ..schemas.tools import ShellInput, ToolResult


SHELL_ALLOWLIST: List[str] = [
    "cat",
    "date",
    "df",
    "diff",
    "du",
    "echo",
    "file",
    "find",
    "grep",
    "head",
    "hostname",
    "jq",
    "ls",
    "printenv",
    "ps",
    "pwd",
    "sed",
    "sort",
    "stat",
    "tail",
    "tr",
    "uname",
    "uniq",
    "uptime",
    "wc",
    "which",
    "whoami",
]

SHELL_ELEVATED_ALLOWLIST: List[str] = [
    "curl",
    "wget",
    "git",
    "python",
    "python3",
    "pip",
    "pip3",
    "top",
]

_SHELL_METACHAR_RE = re.compile(r"[;&|`$(){}<>\\\n]")


def _check_compound_command(command: str) -> Optional[str]:
    """Detect shell metacharacters that allow command injection or chaining."""
    if _SHELL_METACHAR_RE.search(command):
        return f"Shell metacharacters detected in command. Only simple, single commands are allowed."
    return None


def _get_command_name(command: str) -> str:
    """Extract the base command name from a shell command string using shlex."""
    try:
        parts = shlex.split(command)
        if not parts:
            return ""
        cmd = parts[0]
        return cmd.split("/")[-1]
    except ValueError:
        return command.split()[0].split("/")[-1] if command.split() else ""


class ShellTool:
    """Shell tool with command allowlist enforcement and no shell injection."""

    name = "shell"

    def __init__(self) -> None:
        self.settings = get_settings()

    def execute(self, input_data: ShellInput) -> ToolResult:
        meta_err = _check_compound_command(input_data.command)
        if meta_err:
            return ToolResult(
                tool_name="shell",
                success=False,
                error=meta_err,
            )

        cmd_name = _get_command_name(input_data.command)
        all_allowed = SHELL_ALLOWLIST + SHELL_ELEVATED_ALLOWLIST
        if not cmd_name or cmd_name not in all_allowed:
            return ToolResult(
                tool_name="shell",
                success=False,
                error=(
                    f"Command '{cmd_name}' is not in the shell allowlist. "
                    f"Standard: {', '.join(sorted(SHELL_ALLOWLIST))}. "
                    f"Elevated (require HIGH trust): {', '.join(sorted(SHELL_ELEVATED_ALLOWLIST))}"
                ),
            )

        if input_data.dry_run:
            return ToolResult(
                tool_name="shell",
                success=True,
                output=f"[DRY RUN] Would execute: {input_data.command}",
                dry_run=True,
            )

        try:
            argv = shlex.split(input_data.command)
        except ValueError as exc:
            return ToolResult(tool_name="shell", success=False, error=f"Invalid command syntax: {exc}")

        timeout = input_data.timeout or self.settings.shell_timeout
        try:
            result = subprocess.run(
                argv,
                shell=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            return ToolResult(
                tool_name="shell",
                success=result.returncode == 0,
                output=output.strip(),
                error=None if result.returncode == 0 else f"Exit code: {result.returncode}",
                metadata={"returncode": result.returncode, "command": input_data.command},
            )
        except subprocess.TimeoutExpired:
            return ToolResult(tool_name="shell", success=False, error=f"Command timed out after {timeout}s")
        except FileNotFoundError:
            return ToolResult(tool_name="shell", success=False, error=f"Command not found: {cmd_name}")
        except Exception as exc:
            return ToolResult(tool_name="shell", success=False, error=f"Execution error: {exc}")
