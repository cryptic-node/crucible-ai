from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class WorkspaceReport:
    root: str
    file_count: int
    entrypoints: list[str]
    interesting_files: list[str]
    tree_preview: list[str]


class WorkspaceInspector:
    def __init__(self, workspace_root: Path) -> None:
        self.root = workspace_root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _tree_preview(self, max_depth: int = 3, max_items: int = 80) -> list[str]:
        lines: list[str] = []
        count = 0
        for path in sorted(self.root.rglob("*")):
            rel = path.relative_to(self.root)
            depth = len(rel.parts)
            if depth > max_depth:
                continue
            prefix = "  " * (depth - 1)
            label = rel.name + ("/" if path.is_dir() else "")
            lines.append(prefix + label)
            count += 1
            if count >= max_items:
                break
        return lines

    def _entrypoints(self) -> list[str]:
        candidates = [
            "main.py",
            "app/main.py",
            "src/main.py",
            "pyproject.toml",
            "README.md",
            "package.json",
            "Dockerfile",
            "docker-compose.yml",
            "tests",
        ]
        hits = []
        for candidate in candidates:
            path = self.root / candidate
            if path.exists():
                hits.append(candidate)
        return hits

    def _interesting_files(self) -> list[str]:
        out: list[str] = []
        patterns = {"*.py", "*.md", "*.toml", "*.yaml", "*.yml", "*.json"}
        for path in sorted(self.root.rglob("*")):
            if path.is_dir():
                continue
            if any(path.match(pattern) for pattern in patterns):
                out.append(str(path.relative_to(self.root)))
            if len(out) >= 40:
                break
        return out

    def inspect(self) -> WorkspaceReport:
        file_count = sum(1 for p in self.root.rglob("*") if p.is_file())
        return WorkspaceReport(
            root=str(self.root),
            file_count=file_count,
            entrypoints=self._entrypoints(),
            interesting_files=self._interesting_files(),
            tree_preview=self._tree_preview(),
        )
