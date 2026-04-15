from __future__ import annotations

import shlex

from .approval_queue import ApprovalQueue
from .audit import AuditLogger
from .broker import ToolBroker
from .config import Settings
from .memory import MemoryStore
from .model import select_adapter
from .session import SessionStore
from .tasks import TaskManager, TaskStorage
from .workspace.inspector import WorkspaceInspector
from .workspace.summary import summarize_workspace
from .workspace.search import search_workspace


SYSTEM_PROMPT = (
    "You are Grokenstein, a local-first, security-minded apprentice runtime. "
    "Respect the workspace boundary, separate planning from execution, and be honest about uncertainty."
)


class GrokensteinRuntime:
    def __init__(self, settings: Settings, session_id: str) -> None:
        self.settings = settings
        self.session_id = session_id
        self.settings.workspace_root.mkdir(parents=True, exist_ok=True)
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.audit = AuditLogger(self.settings.audit_log_file or (self.settings.data_dir / "audit.jsonl"))
        self.approvals = ApprovalQueue(self.settings.data_dir)
        self.broker = ToolBroker(
            session_id=session_id,
            workspace_root=self.settings.workspace_root,
            approvals=self.approvals,
            audit=self.audit,
            shell_timeout=self.settings.shell_timeout,
        )
        self.sessions = SessionStore(self.settings.data_dir)
        self.state = self.sessions.load(session_id)
        self.memory = MemoryStore(self.settings.data_dir)
        self.tasks = TaskManager(
            TaskStorage(self.settings.data_dir),
            workspace_name=str(self.settings.workspace_root),
            workspace_root=self.settings.workspace_root,
        )
        self.adapter = select_adapter(self.settings)

    def save(self) -> None:
        self.sessions.save(self.state)

    def active_task(self):
        if not self.state.active_task_id:
            return None
        return self.tasks.get(self.state.active_task_id)

    def handle_line(self, line: str) -> str:
        line = line.strip()
        if not line:
            return ""
        if line.startswith("!"):
            output = self._handle_command(line)
        else:
            output = self._handle_chat(line)
        self.save()
        return output

    def _handle_chat(self, line: str) -> str:
        self.state.history.append({"role": "user", "content": line})
        task = self.active_task()
        task_context = self.tasks.render(task) if task else "No active task."
        facts = self.memory.list_for_workspace(str(self.settings.workspace_root))
        fact_lines = "\n".join(
            f"- {fact.key}: {fact.value}" for fact in facts[:10]
        ) or "(no durable facts)"
        messages = [
            *self.state.history[-8:],
            {"role": "system", "content": f"Mode: {self.state.mode}\nTask:\n{task_context}\nFacts:\n{fact_lines}"},
        ]
        reply = self.adapter.complete(SYSTEM_PROMPT, messages)
        self.state.history.append({"role": "assistant", "content": reply})
        self.audit.log("chat.reply", self.session_id, backend=self.adapter.name)
        return reply

    def _handle_command(self, line: str) -> str:
        parts = shlex.split(line)
        cmd = parts[0]
        args = parts[1:]

        if cmd == "!help":
            return self._help_text()
        if cmd == "!history":
            return "\n".join(
                f"[{row['role'].upper()}] {row['content']}" for row in self.state.history[-20:]
            ) or "(empty)"
        if cmd == "!pending":
            return self.broker.pending()
        if cmd == "!approve":
            req_id = args[0] if args else None
            res = self.broker.approve(req_id)
            return res.output if res.success else f"ERROR: {res.error}"
        if cmd == "!deny":
            req_id = args[0] if args else None
            res = self.broker.deny(req_id)
            return res.output if res.success else f"ERROR: {res.error}"
        if cmd == "!mode":
            if not args or args[0] not in {"plan", "execute"}:
                return f"Current mode: {self.state.mode}"
            self.state.mode = args[0]
            return f"Mode set to {self.state.mode}"
        if cmd == "!fs":
            return self._cmd_fs(args)
        if cmd == "!shell":
            if not args:
                return "Usage: !shell <command>"
            res = self.broker.call("shell", {"command": " ".join(args)})
            if res.requires_approval:
                return f"Approval required: {res.error}\nApproval ID: {res.approval_id}"
            return res.output if res.success else f"ERROR: {res.error}"
        if cmd == "!project":
            return self._cmd_project(args)
        if cmd == "!memory":
            return self._cmd_memory(args)
        if cmd == "!task":
            return self._cmd_task(args)
        return f"Unknown command: {cmd}"

    def _cmd_fs(self, args: list[str]) -> str:
        if not args:
            return "Usage: !fs <list|read|write> ..."
        sub = args[0]
        if sub == "list":
            path = args[1] if len(args) > 1 else "."
            res = self.broker.call("fs.list", {"path": path})
            return res.output if res.success else f"ERROR: {res.error}"
        if sub == "read" and len(args) >= 2:
            res = self.broker.call("fs.read", {"path": args[1]})
            return res.output if res.success else f"ERROR: {res.error}"
        if sub == "write" and len(args) >= 3:
            path = args[1]
            content = " ".join(args[2:])
            res = self.broker.call("fs.write", {"path": path, "content": content})
            if res.requires_approval:
                return f"Approval required: {res.error}\nApproval ID: {res.approval_id}"
            return res.output if res.success else f"ERROR: {res.error}"
        return "Usage: !fs list [path] | !fs read <path> | !fs write <path> <content>"

    def _cmd_project(self, args: list[str]) -> str:
        if not args:
            return "Usage: !project <inspect|summary|search>"
        sub = args[0]
        if sub == "inspect":
            report = WorkspaceInspector(self.settings.workspace_root).inspect()
            lines = [
                f"Workspace: {report.root}",
                f"Files: {report.file_count}",
                "Entrypoints:",
                *[f"- {item}" for item in report.entrypoints or ["(none)"]],
                "Tree:",
                *report.tree_preview[:24],
            ]
            return "\n".join(lines)
        if sub == "summary":
            summary = summarize_workspace(self.settings.workspace_root)
            task = self.active_task()
            if task:
                report = WorkspaceInspector(self.settings.workspace_root).inspect()
                self.tasks.attach_summary(
                    task.id,
                    summary,
                    report.entrypoints[:8] + report.interesting_files[:8],
                )
            return summary
        if sub == "search" and len(args) >= 2:
            query = " ".join(args[1:])
            hits = search_workspace(self.settings.workspace_root, query)
            if not hits:
                return "(no hits)"
            return "\n".join(
                f"{hit.path}:{hit.line_no}: {hit.line}" if hit.line_no else f"{hit.path}: {hit.line}"
                for hit in hits
            )
        return "Usage: !project inspect | !project summary | !project search <query>"

    def _cmd_memory(self, args: list[str]) -> str:
        workspace = str(self.settings.workspace_root)
        if not args:
            return "Usage: !memory <list|get|promote>"
        sub = args[0]
        if sub == "list":
            facts = self.memory.list_for_workspace(workspace)
            if not facts:
                return "(no durable facts)"
            return "\n".join(f"- {fact.key}: {fact.value} ({fact.source})" for fact in facts)
        if sub == "get" and len(args) >= 2:
            fact = self.memory.get(workspace, args[1])
            if not fact:
                return "(not found)"
            return f"{fact.key}: {fact.value}\nsource: {fact.source}\ncreated: {fact.created_at}"
        if sub == "promote" and len(args) >= 3:
            key = args[1]
            value = " ".join(args[2:])
            fact = self.memory.promote(workspace, key, value, source=f"session:{self.session_id}")
            self.audit.log("memory.promoted", self.session_id, key=key)
            return f"Promoted fact: {fact.key} = {fact.value}"
        return "Usage: !memory list | !memory get <key> | !memory promote <key> <value>"

    def _cmd_task(self, args: list[str]) -> str:
        if not args:
            return "Usage: !task <new|list|use|show|mode|plan|done|checkpoint|block|unblock>"
        sub = args[0]
        if sub == "new" and len(args) >= 2:
            title = " ".join(args[1:])
            task = self.tasks.create(title=title)
            self.state.active_task_id = task.id
            self.state.mode = task.mode
            self.audit.log("task.created", self.session_id, task_id=task.id, title=task.title)
            return f"Created task {task.id}\n{self.tasks.render(task)}"
        if sub == "list":
            tasks = self.tasks.list()
            if not tasks:
                return "(no tasks)"
            lines = []
            for task in tasks:
                marker = "*" if task.id == self.state.active_task_id else " "
                lines.append(f"{marker} {task.id} | {task.status} | {task.mode} | {task.title}")
            return "\n".join(lines)
        if sub == "use" and len(args) >= 2:
            task = self.tasks.get(args[1])
            if not task:
                return f"Task not found: {args[1]}"
            self.state.active_task_id = task.id
            self.state.mode = task.mode
            return f"Active task set to {task.id}\n{self.tasks.render(task)}"
        task = self.active_task()
        if task is None:
            return "No active task. Use !task new <title> or !task use <id>."
        if sub == "show":
            return self.tasks.render(task)
        if sub == "mode":
            if len(args) < 2 or args[1] not in {"plan", "execute"}:
                return f"Current task mode: {task.mode}"
            task = self.tasks.set_mode(task.id, args[1])
            self.state.mode = task.mode
            return self.tasks.render(task)
        if sub == "plan":
            task = self.tasks.plan(task.id)
            self.state.mode = task.mode
            self.audit.log("task.planned", self.session_id, task_id=task.id)
            return self.tasks.render(task)
        if sub == "done":
            index = int(args[1]) - 1 if len(args) >= 2 else None
            task = self.tasks.mark_done(task.id, index=index)
            self.audit.log("task.step_done", self.session_id, task_id=task.id)
            return self.tasks.render(task)
        if sub == "checkpoint" and len(args) >= 2:
            note = " ".join(args[1:])
            task = self.tasks.checkpoint(task.id, note)
            self.audit.log("task.checkpoint", self.session_id, task_id=task.id)
            return self.tasks.render(task)
        if sub == "block" and len(args) >= 2:
            task = self.tasks.block(task.id, " ".join(args[1:]))
            return self.tasks.render(task)
        if sub == "unblock":
            task = self.tasks.unblock(task.id)
            return self.tasks.render(task)
        return (
            "Usage: !task show | !task mode <plan|execute> | !task plan | !task done [n] | "
            "!task checkpoint <note> | !task block <reason> | !task unblock"
        )

    def _help_text(self) -> str:
        return (
            "Grokenstein v0.0.5 commands\n"
            "!help\n"
            "!history\n"
            "!mode [plan|execute]\n"
            "!pending\n"
            "!approve [approval_id]\n"
            "!deny [approval_id]\n"
            "!task new <title>\n"
            "!task list\n"
            "!task use <id>\n"
            "!task show\n"
            "!task mode <plan|execute>\n"
            "!task plan\n"
            "!task done [n]\n"
            "!task checkpoint <note>\n"
            "!task block <reason>\n"
            "!task unblock\n"
            "!project inspect\n"
            "!project summary\n"
            "!project search <query>\n"
            "!fs list [path]\n"
            "!fs read <path>\n"
            "!fs write <path> <content>\n"
            "!shell <command>\n"
            "!memory list\n"
            "!memory get <key>\n"
            "!memory promote <key> <value>"
        )
