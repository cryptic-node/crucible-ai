from __future__ import annotations

import os
from typing import Any


class BackendAdapter:
    """Base class for a model backend adapter."""

    name: str = "base"
    default_model: str = ""

    def complete(self, prompt: str, config: dict[str, Any] | None = None) -> str:
        raise NotImplementedError


class GroqAdapter(BackendAdapter):
    """Adapter for Groq API (Llama, Mixtral models via groq SDK)."""

    name = "groq"
    default_model = "llama3-8b-8192"

    def __init__(self) -> None:
        self.api_key = os.environ.get("GROQ_API_KEY", "")
        self.model = os.environ.get("GROQ_MODEL", self.default_model)

    def complete(self, prompt: str, config: dict[str, Any] | None = None) -> str:
        cfg = config or {}
        model = cfg.get("model", self.model)
        if not self.api_key:
            return f"[GroqAdapter stub] No GROQ_API_KEY set. Would call model={model} with prompt: {prompt[:80]}..."
        try:
            from groq import Groq  # type: ignore
            client = Groq(api_key=self.api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=cfg.get("max_tokens", 1024),
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            return f"[GroqAdapter error] {exc}"


class OllamaAdapter(BackendAdapter):
    """Adapter for Ollama local inference."""

    name = "ollama"
    default_model = "llama3"

    def __init__(self) -> None:
        self.base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = os.environ.get("OLLAMA_MODEL", self.default_model)

    def complete(self, prompt: str, config: dict[str, Any] | None = None) -> str:
        import urllib.request
        import json
        cfg = config or {}
        model = cfg.get("model", self.model)
        payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                return data.get("response", "")
        except Exception as exc:
            return f"[OllamaAdapter stub] Would call {self.base_url}/api/generate model={model}. Error: {exc}"


class OpenRouterAdapter(BackendAdapter):
    """Adapter for OpenRouter (multi-model proxy)."""

    name = "openrouter"
    default_model = "mistralai/mixtral-8x7b-instruct"

    def __init__(self) -> None:
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "")
        self.model = os.environ.get("OPENROUTER_MODEL", self.default_model)
        self.base_url = "https://openrouter.ai/api/v1"

    def complete(self, prompt: str, config: dict[str, Any] | None = None) -> str:
        import urllib.request
        import json
        cfg = config or {}
        model = cfg.get("model", self.model)
        if not self.api_key:
            return f"[OpenRouterAdapter stub] No OPENROUTER_API_KEY set. Would call model={model}."
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": cfg.get("max_tokens", 1024),
        }).encode()
        try:
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://github.com/cryptic-node/Grokenstein",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                return data["choices"][0]["message"]["content"]
        except Exception as exc:
            return f"[OpenRouterAdapter error] {exc}"


class HuggingFaceAdapter(BackendAdapter):
    """Adapter for HuggingFace Inference API."""

    name = "huggingface"
    default_model = "HuggingFaceH4/zephyr-7b-beta"

    def __init__(self) -> None:
        self.api_key = os.environ.get("HF_API_KEY", "")
        self.model = os.environ.get("HF_MODEL", self.default_model)
        self.base_url = "https://api-inference.huggingface.co/models"

    def complete(self, prompt: str, config: dict[str, Any] | None = None) -> str:
        import urllib.request
        import json
        cfg = config or {}
        model = cfg.get("model", self.model)
        if not self.api_key:
            return f"[HuggingFaceAdapter stub] No HF_API_KEY set. Would call model={model}."
        payload = json.dumps({"inputs": prompt, "parameters": {"max_new_tokens": cfg.get("max_tokens", 512)}}).encode()
        try:
            req = urllib.request.Request(
                f"{self.base_url}/{model}",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
                if isinstance(data, list) and data:
                    return data[0].get("generated_text", "")
                return str(data)
        except Exception as exc:
            return f"[HuggingFaceAdapter error] {exc}"


_BACKENDS: dict[str, type[BackendAdapter]] = {
    "groq": GroqAdapter,
    "ollama": OllamaAdapter,
    "openrouter": OpenRouterAdapter,
    "huggingface": HuggingFaceAdapter,
}

_PRIORITY_ORDER = ["groq", "ollama", "openrouter", "huggingface"]


class ModelRouter:
    """Routes completion requests to the appropriate backend adapter.

    Backend selection order (highest to lowest priority):
      1. Explicit backend from config dict
      2. GROK_BACKEND environment variable
      3. First backend with an API key set
      4. Ollama (local, no key required)
    """

    def __init__(self) -> None:
        self._adapters: dict[str, BackendAdapter] = {
            name: cls() for name, cls in _BACKENDS.items()
        }

    def select_backend(self, config: dict[str, Any] | None = None) -> BackendAdapter:
        cfg = config or {}
        explicit = cfg.get("backend") or os.environ.get("GROK_BACKEND", "")
        if explicit and explicit in self._adapters:
            return self._adapters[explicit]

        for name in _PRIORITY_ORDER:
            adapter = self._adapters[name]
            env_key = {
                "groq": "GROQ_API_KEY",
                "ollama": None,
                "openrouter": "OPENROUTER_API_KEY",
                "huggingface": "HF_API_KEY",
            }.get(name)
            if env_key and os.environ.get(env_key):
                return adapter
            if name == "ollama":
                return adapter

        return self._adapters["ollama"]

    def complete(self, prompt: str, config: dict[str, Any] | None = None) -> str:
        adapter = self.select_backend(config)
        return adapter.complete(prompt, config)

    def list_backends(self) -> list[str]:
        return list(self._adapters.keys())

    def backend_status(self) -> list[dict[str, str]]:
        env_map = {
            "groq": "GROQ_API_KEY",
            "ollama": "OLLAMA_BASE_URL (default http://localhost:11434)",
            "openrouter": "OPENROUTER_API_KEY",
            "huggingface": "HF_API_KEY",
        }
        rows = []
        for name in _PRIORITY_ORDER:
            key = env_map.get(name, "")
            if "API_KEY" in key:
                env_var = key.split(" ")[0]
                configured = "yes" if os.environ.get(env_var) else "no"
            else:
                configured = "local"
            rows.append({"backend": name, "key_env": key, "configured": configured})
        return rows
