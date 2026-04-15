from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TaskStep:
    description: str
    status: str = "pending"


@dataclass
class Checkpoint:
    note: str
    created_at: str


@dataclass
class Task:
    id: str
    title: str
    goal: str
    workspace: str
    mode: str = "plan"
    status: str = "open"
    steps: list[TaskStep] = field(default_factory=list)
    current_step_index: int = 0
    checkpoints: list[Checkpoint] = field(default_factory=list)
    blocked_reason: str = ""
    pending_approval: bool = False
    source_paths: list[str] = field(default_factory=list)
    last_summary: str = ""
    created_at: str = ""
    updated_at: str = ""
