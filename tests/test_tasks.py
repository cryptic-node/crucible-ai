from __future__ import annotations

from pathlib import Path

from grokenstein.tasks.storage import TaskStorage
from grokenstein.tasks.manager import TaskManager


def test_task_persistence_and_resume(tmp_path: Path):
    storage = TaskStorage(tmp_path)
    manager = TaskManager(storage, workspace_name="ws", workspace_root=tmp_path)
    task = manager.create("Build planner")
    manager.plan(task.id)
    manager.checkpoint(task.id, "first checkpoint")

    reloaded = TaskStorage(tmp_path).get(task.id)
    assert reloaded is not None
    assert reloaded.title == "Build planner"
    assert len(reloaded.steps) >= 4
    assert reloaded.checkpoints[-1].note == "first checkpoint"
