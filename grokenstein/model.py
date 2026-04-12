from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterable

from .config import RuntimeConfig


@dataclass(slots=True)
class ModelResponse:
    mode: str
    content: str = ""
    tool_name: str | None = None
    method_name: str | None = None
    args: list[Any] = field(default_factory=list)
    kwargs: dict[str, Any] = field(default_factory=dict)


class BaseModelAdapter(ABC):
    @property
    @abstractmethod
    def backend_name(self) -> str:  # pragma: no cover - interface method
        raise NotImplementedError

    @abstractmethod
    def generate(self, user_message: str, history: Iterable[tuple[str, str]]) -> ModelResponse:  # pragma: no cover - interface method
        raise NotImplementedError


class RuleBasedAdapter(BaseModelAdapter):
    @property
    def backend_name(self) -> str:
        return "rule"

    def generate(self, user_message: str, history: Iterable[tuple[str, str]]) -> ModelResponse:
        stripped = user_message.strip()
        lowered = stripped.lower()

        write_match = re.match(r"^(?:write|save)\s+(.+?)\s+to\s+([\w./-]+)$", stripped, flags=re.IGNORECASE)
        if write_match:
            content, path = write_match.groups()
            return ModelResponse(
                mode="tool_call",
                content=f"I can write that to {path}, but it needs your approval.",
                tool_name="filesystem",
                method_name="write_file",
                args=[path, content],
            )

        read_match = re.match(r"^(?:read|show)(?:\s+file)?\s+([\w./-]+)$", stripped, flags=re.IGNORECASE)
        if read_match:
            path = read_match.group(1)
            return ModelResponse(
                mode="tool_call",
                content=f"Reading {path} from the workspace.",
                tool_name="filesystem",
                method_name="read_file",
                args=[path],
            )

        list_match = re.match(r"^(?:list|ls)(?:\s+files?)?(?:\s+in)?(?:\s+([\w./-]+))?$", lowered)
        if list_match:
            path = list_match.group(1) or "."
            return ModelResponse(
                mode="tool_call",
                content=f"Listing {path} in the workspace.",
                tool_name="filesystem",
                method_name="list_dir",
                args=[path],
            )

        run_match = re.match(r"^(?:run|execute)\s+(.+)$", stripped, flags=re.IGNORECASE)
        if run_match:
            command = run_match.group(1)
            return ModelResponse(
                mode="tool_call",
                content=f"I can run '{command}', but shell execution needs your approval.",
                tool_name="shell",
                method_name="run",
                args=[command],
            )

        if any(token in lowered for token in {"hello", "hi", "hey"}):
            return ModelResponse(
                mode="message",
                content=(
                    "Grokenstein v0.0.4 is online in rule-safe mode. "
                    "I can chat, read workspace files, propose writes, and propose allowlisted shell commands."
                ),
            )

        if "help" in lowered or "what can you do" in lowered:
            return ModelResponse(
                mode="message",
                content=(
                    "I am running in governed rule-safe mode. Try phrases like 'read test.txt', "
                    "'write hello to note.txt', 'list files', or 'run pwd'."
                ),
            )

        return ModelResponse(
            mode="message",
            content=(
                "Rule-safe mode did not detect a tool action in that request. "
                "I can still chat, or you can ask me to read, write, list, or run an allowlisted command."
            ),
        )


class OllamaAdapter(BaseModelAdapter):
    def __init__(self, base_url: str, model_name: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name

    @property
    def backend_name(self) -> str:
        return f"ollama:{self.model_name}"

    def generate(self, user_message: str, history: Iterable[tuple[str, str]]) -> ModelResponse:
        prompt = self._build_prompt(user_message, history)
        payload = json.dumps(
            {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            url=f"{self.base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            return ModelResponse(
                mode="message",
                content=(
                    f"Ollama backend error: {exc}. "
                    "Falling back would be sensible, but this adapter is currently reporting the error directly."
                ),
            )
        except json.JSONDecodeError:
            return ModelResponse(mode="message", content="Ollama returned malformed JSON.")

        raw_text = str(body.get("response", "")).strip()
        return self._parse_response(raw_text)

    def _build_prompt(self, user_message: str, history: Iterable[tuple[str, str]]) -> str:
        history_lines = []
        for role, content in list(history)[-12:]:
            history_lines.append(f"{role.upper()}: {content}")
        history_block = "\n".join(history_lines) if history_lines else "(no history)"
        return f"""
You are Grokenstein's governed planner.
Return ONLY valid JSON in one of these forms:
{{"mode":"message","content":"plain reply"}}
{{"mode":"tool_call","content":"brief explanation","tool_name":"filesystem","method_name":"read_file","args":["notes.txt"],"kwargs":{{}}}}
{{"mode":"tool_call","content":"brief explanation","tool_name":"filesystem","method_name":"list_dir","args":["."],"kwargs":{{}}}}
{{"mode":"tool_call","content":"brief explanation","tool_name":"filesystem","method_name":"write_file","args":["notes.txt","hello"],"kwargs":{{}}}}
{{"mode":"tool_call","content":"brief explanation","tool_name":"shell","method_name":"run","args":["pwd"],"kwargs":{{}}}}

Rules:
- Prefer message replies unless a tool is clearly useful.
- Never request tools outside filesystem.read_file, filesystem.list_dir, filesystem.write_file, shell.run.
- Never request unsafe shell commands.
- Writes and shell commands may require approval.
- Keep content concise.

History:
{history_block}

USER: {user_message}
""".strip()

    def _parse_response(self, raw_text: str) -> ModelResponse:
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            return ModelResponse(mode="message", content=raw_text or "Ollama returned an empty response.")

        mode = str(parsed.get("mode", "message"))
        if mode == "tool_call":
            return ModelResponse(
                mode="tool_call",
                content=str(parsed.get("content", "")),
                tool_name=parsed.get("tool_name"),
                method_name=parsed.get("method_name"),
                args=list(parsed.get("args", [])),
                kwargs=dict(parsed.get("kwargs", {})),
            )
        return ModelResponse(mode="message", content=str(parsed.get("content", raw_text)))


def create_model_adapter(config: RuntimeConfig) -> BaseModelAdapter:
    if config.model_backend == "ollama":
        return OllamaAdapter(base_url=config.ollama_base_url, model_name=config.model_name)
    return RuleBasedAdapter()
