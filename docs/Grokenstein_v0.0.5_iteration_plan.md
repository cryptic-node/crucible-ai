# Grokenstein v0.0.5 Iteration Plan

## Theme

**Dependable apprentice**

## Goals

1. Separate plan mode from execute mode.
2. Add persistent task objects with steps, checkpoints, and blocked state.
3. Add workspace inspection, search, and grounded summaries.
4. Add resume-after-restart behavior for sessions and tasks.
5. Add explicit memory promotion for durable facts.
6. Keep side effects approval-gated.

## Included in this kit

- CLI runtime with persistent session state
- task manager and JSON storage
- workspace inspector, search, and summary helpers
- approval queue and policy gate
- filesystem and shell tools routed through a broker
- optional Ollama adapter with stub fallback
- tests for planning, persistence, approval flow, and grounding

## Intentionally out of scope

- web UI
- autonomous loops
- git push/commit automation
- live Nostr signing
- live Lightning / Bitcoin actions
- vector DB complexity
