from __future__ import annotations

import shlex
import subprocess
from typing import List, Optional


class ShellTool:
    def run(self, command: str, cwd: Optional[str] = None) -> str:
        args: List[str] = shlex.split(command)
        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=15,
            shell=False,
        )
        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, args, output=result.stdout, stderr=result.stderr)
        return (result.stdout + result.stderr).strip()
