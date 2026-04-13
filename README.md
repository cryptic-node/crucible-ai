# Grokenstein v0.0.4

Grokenstein v0.0.4 is a **governed model runtime** built on the v0.0.3 CLI scaffold.
It keeps the local-first command-line workflow, but replaces the placeholder echo loop with:

- a model adapter layer
- a real policy decision model (`allow`, `deny`, `require_approval`)
- an approval queue for risky actions
- append-only JSONL audit logging
- optional Ollama support for a local LLM backend
- repeatable tests for the core trust boundaries

This release still avoids the tempting UI rabbit hole. It focuses on the inside-out backbone.

## What changed from v0.0.3

- Normal chat can now run through a model adapter instead of a hardcoded echo.
- Tool calls can be proposed from natural language and routed through the broker.
- Filesystem writes and shell commands require approval by default.
- Audit logging is now structured JSONL instead of plain text.
- `!approve`, `!deny`, `!pending`, and `!status` were added to the CLI.
- Path handling is more robust.
- Tests were added for policy, broker, runtime, and workspace safety.

## Supported model backends

### 1. Rule-safe mode (default)
No external dependency. This is a deterministic fallback that can:
- answer simple capability questions
- propose safe tool calls from natural language like:
  - `read test.txt`
  - `list files`
  - `write hello to note.txt`
  - `run pwd`

### 2. Ollama mode (optional)
If you already have Ollama running locally, Grokenstein can talk to it using the local HTTP API.

Set environment variables before launching:

```bash
export GROKENSTEIN_MODEL_BACKEND=ollama
export GROKENSTEIN_MODEL_NAME=llama3.2:3b
export GROKENSTEIN_OLLAMA_BASE_URL=http://127.0.0.1:11434
```

Then run Grokenstein normally.

## Install

Runtime dependencies are standard-library only.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For tests:

```bash
pip install -r requirements-dev.txt
```

## Run

```bash
python -m grokenstein.main --id mysession --workspace ./workspace
```

Optional model override flags:

```bash
python -m grokenstein.main \
  --id mysession \
  --workspace ./workspace \
  --model-backend rule
```

Or:

```bash
python -m grokenstein.main \
  --id mysession \
  --workspace ./workspace \
  --model-backend ollama \
  --model-name llama3.2:3b
```

## CLI commands

- `!help` — show commands
- `!history` — show session history
- `!status` — show backend, workspace, and pending approval count
- `!pending` — list pending approvals
- `!approve [request_id]` — approve one pending request
- `!deny [request_id]` — deny one pending request
- `!fs list [path]` — list workspace directory
- `!fs read <path>` — read workspace file
- `!fs write <path> [content]` — write workspace file, approval required by default
- `!shell <command>` — run an allowlisted shell command, approval required by default

## Suggested smoke test

Inside Grokenstein:

```text
hello Grokenstein
write hello-from-v0.0.4 to note.txt
!pending
!approve
!fs read note.txt
run pwd
!pending
!approve
```

## Run tests

```bash
pytest -q
```

## Files added in this kit

- `Grokenstein_v0.0.4_iteration_plan.md`
- `RELEASE_CHECKLIST_v0.0.4.md`
- `grokenstein/config.py`
- `grokenstein/model.py`
- `grokenstein/approvals.py`
- updated runtime / broker / policy / logger / tools
- `tests/` covering safety boundaries and approval flow
