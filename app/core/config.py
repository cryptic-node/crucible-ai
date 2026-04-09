from __future__ import annotations

import os
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field("Grokenstein", description="Application name")
    app_version: str = Field("1.0.0", description="Application version")
    debug: bool = Field(False, description="Enable debug mode")

    secret_key: str = Field("changeme-use-strong-random-key", description="JWT/session secret key")
    host: str = Field("0.0.0.0", description="Bind host")
    port: int = Field(8080, description="Bind port")

    database_url: str = Field(
        "postgresql+asyncpg://grok:grokpass@localhost:5432/grokenstein",
        description="Async PostgreSQL connection string",
    )
    database_url_sync: str = Field(
        "postgresql://grok:grokpass@localhost:5432/grokenstein",
        description="Sync PostgreSQL connection string (Alembic)",
    )

    groq_api_key: str = Field("", description="Groq API key")
    groq_model: str = Field("llama3-8b-8192", description="Groq model ID")

    openrouter_api_key: str = Field("", description="OpenRouter API key")
    openrouter_model: str = Field("mistralai/mixtral-8x7b-instruct", description="OpenRouter model ID")

    hf_api_key: str = Field("", description="HuggingFace API key")
    hf_model: str = Field("HuggingFaceH4/zephyr-7b-beta", description="HuggingFace model ID")

    ollama_base_url: str = Field("http://localhost:11434", description="Ollama base URL")
    ollama_model: str = Field("llama3", description="Ollama model ID")

    grok_backend: str = Field("", description="Force backend (groq, ollama, openrouter, huggingface)")

    workspace_root: str = Field("/workspace", description="Workspace root path (tool sandbox)")
    default_workspace: str = Field("personal", description="Default workspace name")

    shell_timeout: int = Field(10, description="Shell tool command timeout in seconds")
    web_fetch_max_bytes: int = Field(65536, description="Web fetch max response size in bytes")
    web_fetch_timeout: int = Field(15, description="Web fetch timeout in seconds")

    audit_log_file: str = Field("logs/audit.jsonl", description="Audit log file path")
    audit_log_db: bool = Field(True, description="Write audit records to database")

    kill_switch: bool = Field(False, description="Emergency kill switch — denies all tool execution")

    embedding_model: str = Field("stub", description="Embedding model (stub = hash-based)")
    embedding_dim: int = Field(1536, description="Embedding vector dimension")

    nostr_relay_allowlist: str = Field("", description="Comma-separated list of allowed Nostr relay URLs")
    bitcoin_rpc_url: str = Field("http://bitcoind:8332", description="Bitcoin RPC URL (stub)")
    lnd_rest_url: str = Field("https://lnd:8080", description="LND REST URL (stub)")

    policy_config_path: str = Field("scripts/policy_config.yaml", description="Policy config YAML path")
    max_requests_per_minute: int = Field(60, description="Rate limit: max requests per minute per session")


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    global _settings
    _settings = None
