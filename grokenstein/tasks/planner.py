from __future__ import annotations

from pathlib import Path

from ..workspace.inspector import WorkspaceInspector


def generate_plan_steps(goal: str, workspace_root: Path) -> list[str]:
    report = WorkspaceInspector(workspace_root).inspect()
    steps: list[str] = []
    steps.append(f"Inspect the workspace and restate the goal: {goal}.")
    if report.entrypoints:
        steps.append(f"Read the likely entrypoints: {', '.join(report.entrypoints[:4])}.")
    else:
        steps.append("Identify likely entrypoints, configuration files, and tests.")
    steps.append("Draft a minimal implementation plan before changing files.")
    steps.append("Execute the smallest safe step that advances the goal.")
    steps.append("Run focused validation or tests for the changed area.")
    steps.append("Checkpoint progress and list remaining risks or next steps.")
    return steps
