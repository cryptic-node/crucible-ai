from __future__ import annotations

import uuid

from .models import Task, TaskStep, Checkpoint
from .storage import TaskStorage
from .planner import generate_plan_steps


class TaskManager:
    def __init__(self, storage: TaskStorage, workspace_name: str, workspace_root) -> None:
        self.storage = storage
        self.workspace_name = workspace_name
        self.workspace_root = workspace_root

    def create(self, title: str, goal: str | None = None, mode: str = "plan") -> Task:
        now = TaskStorage.now()
        task = Task(
            id=str(uuid.uuid4()),
            title=title,
            goal=goal or title,
            workspace=self.workspace_name,
            mode=mode,
            created_at=now,
            updated_at=now,
        )
        self.storage.save(task)
        return task

    def list(self) -> list[Task]:
        return [task for task in self.storage.list() if task.workspace == self.workspace_name]

    def get(self, task_id: str) -> Task | None:
        task = self.storage.get(task_id)
        if task and task.workspace == self.workspace_name:
            return task
        return None

    def set_mode(self, task_id: str, mode: str) -> Task:
        task = self._must_get(task_id)
        task.mode = mode
        task.updated_at = TaskStorage.now()
        self.storage.save(task)
        return task

    def plan(self, task_id: str) -> Task:
        task = self._must_get(task_id)
        descriptions = generate_plan_steps(task.goal, self.workspace_root)
        task.steps = [TaskStep(description=text) for text in descriptions]
        task.current_step_index = 0
        task.mode = "plan"
        task.last_summary = "Generated a fresh plan from the current workspace snapshot."
        task.updated_at = TaskStorage.now()
        self.storage.save(task)
        return task

    def checkpoint(self, task_id: str, note: str) -> Task:
        task = self._must_get(task_id)
        task.checkpoints.append(Checkpoint(note=note, created_at=TaskStorage.now()))
        task.updated_at = TaskStorage.now()
        self.storage.save(task)
        return task

    def mark_done(self, task_id: str, index: int | None = None) -> Task:
        task = self._must_get(task_id)
        if not task.steps:
            raise ValueError("Task has no steps to complete.")
        idx = index if index is not None else task.current_step_index
        if idx < 0 or idx >= len(task.steps):
            raise IndexError("Step index out of range")
        task.steps[idx].status = "done"
        next_idx = idx + 1
        while next_idx < len(task.steps) and task.steps[next_idx].status == "done":
            next_idx += 1
        task.current_step_index = min(next_idx, len(task.steps) - 1)
        if all(step.status == "done" for step in task.steps):
            task.status = "done"
        task.updated_at = TaskStorage.now()
        self.storage.save(task)
        return task

    def block(self, task_id: str, reason: str) -> Task:
        task = self._must_get(task_id)
        task.status = "blocked"
        task.blocked_reason = reason
        task.updated_at = TaskStorage.now()
        self.storage.save(task)
        return task

    def unblock(self, task_id: str) -> Task:
        task = self._must_get(task_id)
        task.status = "open"
        task.blocked_reason = ""
        task.updated_at = TaskStorage.now()
        self.storage.save(task)
        return task

    def attach_summary(self, task_id: str, summary: str, source_paths: list[str]) -> Task:
        task = self._must_get(task_id)
        task.last_summary = summary
        task.source_paths = source_paths
        task.updated_at = TaskStorage.now()
        self.storage.save(task)
        return task

    def render(self, task: Task) -> str:
        lines = [
            f"Task: {task.title}",
            f"ID: {task.id}",
            f"Goal: {task.goal}",
            f"Mode: {task.mode}",
            f"Status: {task.status}",
        ]
        if task.blocked_reason:
            lines.append(f"Blocked: {task.blocked_reason}")
        if task.steps:
            lines.append("Steps:")
            for idx, step in enumerate(task.steps, start=1):
                marker = "->" if idx - 1 == task.current_step_index else "  "
                lines.append(f"{marker} [{step.status}] {idx}. {step.description}")
        if task.checkpoints:
            lines.append("Checkpoints:")
            for cp in task.checkpoints[-5:]:
                lines.append(f"- {cp.created_at}: {cp.note}")
        if task.last_summary:
            lines.append("Last summary:")
            lines.append(task.last_summary)
        if task.source_paths:
            lines.append("Grounding:")
            lines.extend(f"- {path}" for path in task.source_paths)
        return "\n".join(lines)

    def _must_get(self, task_id: str) -> Task:
        task = self.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        return task
