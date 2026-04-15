from __future__ import annotations

from pathlib import Path

from .inspector import WorkspaceInspector


def summarize_workspace(workspace_root: Path) -> str:
    report = WorkspaceInspector(workspace_root).inspect()
    lines = [
        f"Workspace: {report.root}",
        f"Files: {report.file_count}",
        "Entrypoints:",
    ]
    lines.extend(f"- {item}" for item in report.entrypoints or ["(none detected)"])
    lines.append("Interesting files:")
    lines.extend(f"- {item}" for item in report.interesting_files[:12] or ["(none)"])
    lines.append("Tree preview:")
    lines.extend(report.tree_preview[:20] or ["(empty workspace)"])
    return "\n".join(lines)
