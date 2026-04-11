"""Shell tool for Grokenstein.

This tool runs whitelisted shell commands.  It delegates policy
enforcement to the ``PolicyEngine`` via the ``ToolBroker``; here we
perform only basic execution and output capture.  ``subprocess.run`` is
used with ``shell=False`` to avoid invoking a full shell, which helps
reduce the risk of injection attacks.  Only the command name and its
arguments are executed as provided by the caller.
"""

from __future__ import annotations

import subprocess
from typing import List, Optional


class ShellTool:
    """Execute simple shell commands from an allowlist."""

    def run(self, command: str, cwd: Optional[str] = None) -> str:
        """Run a shell command.

        The command must be a single string containing the executable and
        its arguments.  The policy engine ensures the command is
        whitelisted; this method trusts that check and simply executes
        the command.  Execution occurs with ``shell=False`` to prevent
        the invocation of a real shell.  The current working directory
        may be specified; otherwise it defaults to the process CWD.

        Args:
            command: the full command string
            cwd: optional working directory to run the command in

        Returns:
            The standard output as a string.  Standard error is merged
            into the output for simplicity.

        Raises:
            subprocess.CalledProcessError: if the command returns a non‑zero exit code
        """
        # Split command into program and arguments respecting whitespace
        # Do not use shell=True; policy enforces allowed commands
        import shlex
        args: List[str] = shlex.split(command)
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
        # If the command failed, raise an exception to be handled by the caller
        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, args, result.stdout, result.stderr)
        # Return combined stdout and stderr
        return (result.stdout + result.stderr).strip()