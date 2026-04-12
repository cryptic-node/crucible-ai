# Grokenstein v0.0.4 Iteration Plan

## Theme
Turn the proven v0.0.3 CLI scaffold into a **governed runtime**.

This iteration deliberately avoids web UI gravity and instead builds the trust-critical inner loop:
- model adapter
- policy engine
- tool broker
- approval flow
- structured audit log
- tests

## Why this release exists
v0.0.3 proved the baseline:
- the CLI runs cleanly
- session history persists
- workspace file I/O works
- shell access is constrained
- tmux/detach/re-attach behaves properly

But the assistant response path is still a placeholder echo and the broker/policy stack is too thin for serious work.

v0.0.4 fixes that by giving Grokenstein a governed execution path.

## Definition of done

### 1. Model runtime
- Replace the placeholder echo response path.
- Add a model adapter interface.
- Support a deterministic offline-safe backend.
- Support an optional Ollama backend.

### 2. Broker and policy
- Every side-effecting tool call goes through the broker.
- Policy decisions are explicit: `allow`, `deny`, `require_approval`.
- Workspace writes require approval by default.
- Shell commands require approval by default.
- Unsafe shell commands are denied.

### 3. Auditability
- Every important event is written as JSONL.
- At minimum log:
  - session_started
  - user_message
  - assistant_message
  - tool_requested
  - tool_denied
  - approval_requested
  - approval_granted
  - approval_denied
  - tool_executed
  - tool_error

### 4. Manual control
- Add `!approve`, `!deny`, `!pending`, and `!status`.
- Pending approvals survive until acted on.

### 5. Tests
- Filesystem path escape test
- Policy deny test for unsafe shell
- Policy approval test for writes
- Broker approval round-trip test
- Runtime persistence / command flow test

## What is intentionally not in scope
- web UI
- API server
- vector DB
- git write tools
- network fetch tools
- secrets manager integration
- Nostr signing
- Lightning / Bitcoin actions
- autonomous loops
- multi-agent behavior

## Release boundary
Call this release:

**v0.0.4 — Governed Model Runtime**

## Manual validation checklist
1. Launch inside tmux.
2. Send a normal chat message.
3. Write a file through natural language.
4. Confirm approval is requested.
5. Approve it.
6. Read the file back.
7. Attempt a denied shell command.
8. Attempt a safe shell command.
9. Approve it.
10. Inspect `data/activity.jsonl`.
11. Restart and verify history persists.

## Security posture for this release
- Read-only file actions are allowed.
- Writes are human-gated.
- Shell is allowlisted and human-gated.
- Workspace root is enforced.
- Model output does not bypass policy.
- Audit logs are append-only JSON records.

## Immediate backlog after v0.0.4
- plan mode vs execute mode
- memory promotion rules
- richer task objects and checkpoints
- better source-aware summaries
- stronger shell argument controls
- optional signed audit chain
- pluggable pack/flavor system

## Opinionated rule
Grokenstein should never gain new powers through the chat path alone.
All meaningful capabilities must be routed through the same broker, policy, approval, and audit surfaces.
