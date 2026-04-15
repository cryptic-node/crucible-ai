from __future__ import annotations

from dataclasses import dataclass
import json
import urllib.request
from typing import Sequence

from ..config import Settings


class BaseModelAdapter:
    name = "base"

    def complete(self, system_prompt: str, messages: Sequence[dict[str, str]]) -> str:
        raise NotImplementedError


class StubAdapter(BaseModelAdapter):
    name = "stub"

    def complete(self, system_prompt: str, messages: Sequence[dict[str, str]]) -> str:
        last = messages[-1]["content"] if messages else ""
        return (
            "[Grokenstein stub]\n"
            "No live model backend is configured, so this reply is a safe placeholder.\n\n"
            f"Latest input: {last}\n"
            "Use task and project commands to inspect, plan, checkpoint, and resume work."
        )


@dataclass
class OllamaAdapter(BaseModelAdapter):
    settings: Settings
    name: str = "ollama"

    def complete(self, system_prompt: str, messages: Sequence[dict[str, str]]) -> str:
        payload = {
            "model": self.settings.ollama_model,
            "messages": [{"role": "system", "content": system_prompt}, *messages],
            "stream": False,
        }
        req = urllib.request.Request(
            self.settings.ollama_base_url.rstrip("/") + "/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        try:
            return body["message"]["content"]
        except Exception:
            return str(body)


def select_adapter(settings: Settings) -> BaseModelAdapter:
    if settings.model_backend == "ollama":
        try:
            return OllamaAdapter(settings=settings)
        except Exception:
            return StubAdapter()
    return StubAdapter()
