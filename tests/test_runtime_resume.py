from __future__ import annotations

from pathlib import Path

from grokenstein.config import Settings
from grokenstein.runtime import GrokensteinRuntime


def test_runtime_resumes_active_task(tmp_path: Path):
    workspace = tmp_path / "workspace"
    data_dir = tmp_path / "data"
    settings = Settings.from_args(workspace, data_dir)

    rt1 = GrokensteinRuntime(settings, "mysession")
    out = rt1.handle_line("!task new Resume me")
    assert "Created task" in out
    active_id = rt1.state.active_task_id
    rt1.save()

    rt2 = GrokensteinRuntime(settings, "mysession")
    assert rt2.state.active_task_id == active_id
    show = rt2.handle_line("!task show")
    assert "Resume me" in show
