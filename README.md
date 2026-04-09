# Grokenstein v1.0.0

**Security-first, privacy-focused personal operator AI assistant**

Grokenstein is a local-first AI agent that helps you manage files, information, and communications — with strict policy controls, auditable tool execution, and persistent memory. It is designed to be your personal AI operator, not a cloud service.

---

## Quick Start

```bash
# 1. Copy and configure environment variables
cp .env.example .env
# Edit .env — add at least one LLM backend API key

# 2. Install dependencies
pip install -r requirements.txt

# 3. Interactive chat (CLI)
python -m app.cli.main chat --workspace personal --trust HIGH

# 4. Single task
python -m app.cli.main run "List files in /workspace" --workspace personal

# 5. Start web server
python -m app.cli.main serve
# Then open http://localhost:8080/ui in your browser

# 6. Docker (includes Postgres + pgvector)
docker-compose up
```

---

## Architecture Overview

```
You (CLI / Web UI)
      │
      ▼
┌─────────────┐
│   Brain     │  Chat loop, planning, memory retrieval
│  (brain/)   │  Routes ALL tool calls via ToolBroker
└──────┬──────┘
       │ only via Broker
       ▼
┌─────────────┐    ┌──────────────┐    ┌──────────────┐
│ Tool Broker │───▶│ Policy Engine│    │ Audit Logger │
│ (broker/)   │    │ (policy/)    │◀──▶│ (core/audit) │
└──────┬──────┘    └──────────────┘    └──────────────┘
       │
       ▼
┌──────────────────────────────────────────────┐
│  Tools: filesystem | shell | web_fetch       │
│  Finance stubs | Nostr stubs                 │
└──────────────────────────────────────────────┘
       │
       ▼
┌─────────────┐    ┌──────────────┐
│   Memory    │    │   Database   │
│  Service    │    │  Postgres +  │
│ (memory/)   │    │  pgvector    │
└─────────────┘    └──────────────┘
```

---

## Workspace Model

| Workspace       | Default Trust | Notes                                      |
|-----------------|---------------|--------------------------------------------|
| `personal`      | HIGH          | Full access for local sessions             |
| `consulting`    | MEDIUM        | No live finance execution                  |
| `experiments`   | MEDIUM        | No signing or payments                     |
| `infrastructure`| HIGH          | HIGH trust required for all operations     |

Each workspace has separate memory scope, policy config, and audit partitioning.

---

## Security Principles

1. **Tool Broker is the sole gateway** — Brain never calls tool handlers directly
2. **Policy Engine decides before every tool call** — allow, deny, require_approval, require_simulation, escalate_channel
3. **Workspace isolation** — memory, audit, and policy are partitioned by workspace
4. **Trust levels enforced** — HIGH/MEDIUM/LOW gating on all sensitive operations
5. **Finance requires HIGH trust + simulation first** — no live payment without dry_run → approve → execute
6. **Filesystem locked to /workspace** — path traversal attempts are rejected
7. **Shell uses allowlist** — only known-safe commands are permitted
8. **Secrets never stored in memory tables** — is_secret flag enforced
9. **Structured audit log** — every sensitive action emits a JSON record
10. **Emergency kill switch** — one env var to deny all tool execution

---

## What Is Implemented

- FastAPI backend with session, chat, workspace, memory, and health endpoints
- Policy Engine with all five decision types
- Tool Broker with Pydantic validation, policy gating, audit logging, dry_run
- Filesystem tool (workspace-sandboxed)
- Shell tool (command allowlist)
- Web fetch tool (size + timeout limits)
- Memory Service with semantic search (stub embeddings) and user review/delete
- Structured audit logger (JSON, file-backed)
- Trust level model (HIGH/MEDIUM/LOW)
- Workspace separation (personal, consulting, experiments, infrastructure)
- Finance stubs (Bitcoin, Lightning) with Pydantic schemas
- Nostr stubs (identity, relay allowlist, NIP-46 signing boundary)
- Minimal web chat UI
- CLI entrypoint
- Docker Compose (app, postgres+pgvector, bitcoind stub, lnd stub)
- pytest test suite

---

## What Is Stubbed / Not Yet Implemented

- **Live Nostr signing** — NIP-46 remote signer not wired; schemas only
- **Live Bitcoin/Lightning** — RPC/REST clients not connected; schemas only
- **Real pgvector embeddings** — uses deterministic hash-based stub; wire in real model via `EMBEDDING_MODEL`
- **Alembic migrations** — engine and Base defined; run `alembic init` and configure
- **Mobile/PWA session** — out of scope for v1.0.0
- **Rate limiting enforcement** — scaffold defined in policy config; not enforced in broker yet

---

## Secrets Warning

**Never** store private keys, nsecs, wallet seeds, or API secrets in:
- Memory records (the service rejects `is_secret=True` records)
- Session messages
- Chat history
- Audit logs (inputs are hashed, not stored raw)

Use a proper secrets manager (environment variables, Vault, hardware key) for all sensitive credentials.

---

## Roadmap

- [ ] Real pgvector embeddings (sentence-transformers or OpenAI)
- [ ] NIP-46 remote signing integration
- [ ] Live Bitcoin RPC client
- [ ] Live LND gRPC/REST client
- [ ] Alembic migration setup
- [ ] Rate limiting enforcement in Tool Broker
- [ ] Web UI memory review page
- [ ] Step-up approval flow (TOTP or hardware key)
- [ ] Multi-user session support

---

## Features

- **Multi-model routing** — automatically picks the best available backend based on environment variables
- **Persistent sessions** — conversations are saved to disk and resumable
- **Tool execution** — bash, file read/write, and web fetch tools built in
- **Slash commands** — `/help`, `/models`, `/save`, `/clear`, `/exit`
- **Pure Python** — no heavy frameworks, no containers

---

## Supported Backends

| Backend      | Environment Variable   | Notes                          |
|--------------|------------------------|--------------------------------|
| Groq         | `GROQ_API_KEY`         | Llama3, Mixtral via groq SDK   |
| Ollama       | *(none required)*      | Local inference, default local |
| OpenRouter   | `OPENROUTER_API_KEY`   | Access to 100+ models          |
| HuggingFace  | `HF_API_KEY`           | Inference API                  |

Backend priority: Groq → Ollama → OpenRouter → HuggingFace.  
Override with `GROK_BACKEND=ollama` (or any backend name).

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set at least one API key (or use Ollama locally)
export GROQ_API_KEY=your_key_here

# Start a chat session
python -m grokenstein.src.main chat

# Run a one-shot task
python -m grokenstein.src.main run "Summarize the Fermi paradox in 3 sentences"

# List available backends
python -m grokenstein.src.main models

# Show all tools
python -m grokenstein.src.main tools

# Resume a saved session
python -m grokenstein.src.main chat --session <session-id>
```

---

## Project Structure

```
grokenstein/
├── src/
│   ├── __init__.py
│   ├── main.py            # CLI entrypoint (argparse)
│   ├── models.py          # Core dataclasses
│   ├── models_router.py   # Multi-model backend router
│   ├── context.py         # Workspace context (GrokContext)
│   ├── runtime.py         # GrokRuntime — top-level orchestrator
│   ├── query_engine.py    # GrokQueryEngine — turn loop + session
│   ├── permissions.py     # ToolPermissionContext
│   ├── history.py         # In-memory conversation log
│   ├── transcript.py      # Flushable transcript store
│   ├── session_store.py   # Disk-backed session persistence
│   ├── tools.py           # Tool registry (bash, file, web)
│   └── commands.py        # Slash command registry
├── tests/
│   └── __init__.py
├── assets/
├── .sessions/             # Auto-created by session_store
├── README.md
├── LICENSE
├── requirements.txt
├── pyproject.toml
└── .gitignore
```

---

## Architecture

Grokenstein mirrors the agent harness pattern from a Python port of Claude Code, with all subsystem names adapted for the Grokenstein identity:

| claude-code concept | Grokenstein equivalent    |
|---------------------|---------------------------|
| `PortRuntime`       | `GrokRuntime`             |
| `PortingModule`     | `ModelAdapter`            |
| `PortContext`       | `GrokContext`             |
| `QueryEnginePort`   | `GrokQueryEngine`         |
| `PortingBacklog`    | `ModelBacklog`            |

---

## License

This is free and unencumbered software released into the public domain. See [LICENSE](LICENSE).
