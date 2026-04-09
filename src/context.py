from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GrokContext:
    """Workspace context for a Grokenstein session."""
    source_root: Path
    tests_root: Path
    assets_root: Path
    sessions_root: Path
    python_file_count: int
    test_file_count: int
    asset_file_count: int
    sessions_available: bool


def build_grok_context(base: Path | None = None) -> GrokContext:
    root = base or Path(__file__).resolve().parent.parent
    source_root = root / "src"
    tests_root = root / "tests"
    assets_root = root / "assets"
    sessions_root = root / ".sessions"
    return GrokContext(
        source_root=source_root,
        tests_root=tests_root,
        assets_root=assets_root,
        sessions_root=sessions_root,
        python_file_count=sum(1 for p in source_root.rglob("*.py") if p.is_file()),
        test_file_count=sum(1 for p in tests_root.rglob("*.py") if p.is_file()),
        asset_file_count=sum(1 for p in assets_root.rglob("*") if p.is_file()),
        sessions_available=sessions_root.exists(),
    )


def render_context(context: GrokContext) -> str:
    return "\n".join([
        f"Source root:    {context.source_root}",
        f"Tests root:     {context.tests_root}",
        f"Assets root:    {context.assets_root}",
        f"Sessions root:  {context.sessions_root}",
        f"Python files:   {context.python_file_count}",
        f"Test files:     {context.test_file_count}",
        f"Assets:         {context.asset_file_count}",
        f"Sessions dir:   {context.sessions_available}",
    ])
