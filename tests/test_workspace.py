from __future__ import annotations

from pathlib import Path

from grokenstein.workspace.summary import summarize_workspace
from grokenstein.workspace.search import search_workspace


def test_workspace_summary_is_grounded(tmp_path: Path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")

    summary = summarize_workspace(tmp_path)
    assert "app/main.py" in summary
    assert "README.md" in summary


def test_workspace_search_returns_hits(tmp_path: Path):
    (tmp_path / "module.py").write_text("def planner():\n    return 1\n", encoding="utf-8")
    hits = search_workspace(tmp_path, "planner")
    assert hits
    assert hits[0].path == "module.py"
