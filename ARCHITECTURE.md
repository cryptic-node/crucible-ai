# Grokenstein v1.0.0 — Architecture

## Component Overview

### `app/core/`
- **`config.py`** — Typed configuration via `pydantic-settings`. All settings read from environment variables. No hardcoded secrets.
- **`trust.py`** — Trust level enum (HIGH/MEDIUM/LOW) and workspace trust defaults.
- **`audit.py`** — Structured JSON audit logger. Every sensitive action emits a JSON record to file and/or DB.

### `app/policy/`
- **`engine.py`** — Policy Engine. Evaluates `PolicyRequest` → `PolicyDecision`. Decisions: `allow`, `deny`, `require_approval`, `require_simulation`, `escalate_channel`. Enforces kill switch, workspace rules, tool restrictions, and trust level gating.

### `app/broker/`
- **`broker.py`** — Tool Broker. The **sole** execution gateway for all tool calls. Flow: schema validation → policy decision → audit log → dry_run handling → tool dispatch → result wrap. Brain cannot call tool handlers directly.

### `app/tools/`
- **`filesystem.py`** — Filesystem tool. All paths resolved and validated against `/workspace`. Path traversal rejected. Supports dry_run.
- **`shell.py`** — Shell tool. Command allowlist enforced. Configurable timeout. Supports dry_run.
- **`web_fetch.py`** — Web fetch tool. URL scheme validation, response size limit, timeout. Supports dry_run.

### `app/memory/`
- **`service.py`** — Memory Service. CRUD, semantic similarity search (stub embeddings), provenance enforcement, ephemeral compaction. Secrets rejected.

### `app/brain/`
- **`brain.py`** — Brain module. Handles chat loop, planning, memory retrieval. Communicates only through ToolBroker and MemoryService. Preserves existing LLM model routing via `ModelRouter`.

### `app/api/`
- **`sessions.py`** — Session create/list/get endpoints.
- **`chat.py`** — Chat message endpoint.
- **`workspaces.py`** — Workspace CRUD.
- **`memory.py`** — Memory CRUD, search, review, compact.
- **`health.py`** — Health check and root endpoint.

### `app/db/`
- **`engine.py`** — Async SQLAlchemy engine, session factory, `init_db()`.
- **`models.py`** — ORM models: `Workspace`, `Session`, `MemoryRecord`, `AuditLog`, `PolicyConfig`.

### `app/schemas/`
- **`session.py`** — Session and Chat Pydantic schemas.
- **`workspace.py`** — Workspace schemas.
- **`memory.py`** — Memory record schemas.
- **`policy.py`** — PolicyRequest and PolicyDecision schemas.
- **`tools.py`** — Tool input/output schemas (ToolResult).

### `app/finance/`
- **`schemas.py`** — Bitcoin node health, wallet balance, LND status, invoice parsing, payment proposal. **Stubs only.** No live signing or payment execution.

### `app/nostr/`
- **`schemas.py`** — Nostr identity, relay allowlist, NIP-46 signing boundary, read/post operations, approved DM commands. **Stubs only.** No live relay connections or signing.

### `app/ui/`
- **`static/index.html`** — Minimal functional web chat UI. Shows chat history, trust level badge, workspace selector, tool usage, policy decisions. Served as static files by FastAPI.

### `app/cli/`
- **`main.py`** — Updated CLI entrypoint integrated with the new architecture.

### `src/` (preserved)
- Existing `models_router.py` (ModelRouter, backend adapters) preserved and reused by Brain.
- Other existing modules preserved for backward compatibility.

---

## Data Flow

```
User Input (CLI / Web)
  │
  ▼
Brain.chat()
  ├──▶ MemoryService.search() [retrieve relevant context]
  ├──▶ ModelRouter.complete() [LLM call]
  └──▶ ToolBroker.call() [for any tool use]
         ├──▶ Input schema validation (Pydantic)
         ├──▶ PolicyEngine.evaluate() [allow/deny/require_*]
         ├──▶ AuditLogger.log() [before and after]
         ├──▶ dry_run check [return simulated output if set]
         └──▶ Tool handler (filesystem/shell/web_fetch)
                └──▶ ToolResult
```

---

## Trust Boundaries

| Boundary                  | Enforcement                                          |
|---------------------------|------------------------------------------------------|
| User → Brain              | Trust level set at session creation                  |
| Brain → ToolBroker        | Brain cannot bypass Broker; tool handlers not exposed|
| ToolBroker → PolicyEngine | Every call evaluated before execution                |
| PolicyEngine → Config     | Kill switch checked first on every evaluation        |
| Filesystem tool → /workspace | All paths resolved and checked against root      |
| Shell tool → Commands     | Allowlist enforced; no shell injection possible      |
| Memory → Secrets          | `is_secret=True` rejected; no raw secrets stored     |
| Finance/Nostr → Live ops  | Stubs only; dry_run=True by default                 |

---

## Module Boundaries

- **Brain** imports: `ToolBroker`, `MemoryService`, `AuditLogger`, `ModelRouter`
- **ToolBroker** imports: `PolicyEngine`, `AuditLogger`, tool handlers
- **PolicyEngine** imports: `Settings`, `TrustLevel`
- **AuditLogger** imports: `Settings` (for log file path)
- **Tool handlers** import: `Settings`, Pydantic schemas
- **MemoryService** imports: Pydantic schemas only
- **No circular imports**; each layer depends only on layers below it.

---

## Database Schema

| Table           | Purpose                                              |
|-----------------|------------------------------------------------------|
| `workspaces`    | Workspace registry with trust level and policy YAML  |
| `sessions`      | Chat session records with workspace FK               |
| `memory_records`| All memory with provenance, trust, retention class   |
| `audit_logs`    | Immutable audit trail of all sensitive actions       |
| `policy_configs`| Per-workspace policy config overrides                |
