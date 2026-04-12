# Grokenstein v1.0.1 Foundation Plan

## Theme
Make `app/` the authoritative runtime, install selective reviewed memory, and introduce policy-controlled agent modes that let Grokenstein grow into a living wiki/repo librarian without becoming an unsafe wandering agent.

## Why this release exists
The current repo already routes the default CLI through `app.cli.main`, but it still ships `src` as a legacy entrypoint and package. The README also mixes the new `app/` architecture with older `src` usage. That creates documentation drift and makes policy hardening harder than it needs to be.

This release should **not** try to add full autonomy. It should:
1. declare one runtime authority (`app/`)
2. add reviewed memory states instead of raw autosave
3. add explicit agent modes (`interactive`, `observer`, `curator`, `operator`)
4. introduce the pack format for future “flavors”

## Definition of done

### 1. Runtime authority
- `app/` is the only documented runtime.
- `grok` remains the canonical CLI script.
- `grok-legacy` is marked deprecated in docs and kept only as a compatibility escape hatch for one short release window.
- README and UI references no longer tell users to run `python -m grokenstein.src.main`.

### 2. Selective memory
- AI-created memory defaults to `candidate`, not durable truth.
- User-created memory can be `approved` immediately.
- Memory supports provenance, tags, scope, review status, pinning, canonicality, and optional TTL.
- Promotion path exists: `candidate -> approved/rejected/archived`.

### 3. Agent modes
- `interactive`: normal human-driven chat
- `observer`: read-only monitoring and note taking
- `curator`: can draft candidate knowledge, but cannot directly change external state
- `operator`: can prepare actions and drafts, but sensitive actions still require approval / simulation / step-up

### 4. Pack system
- Domain packs are configuration and policy overlays, not forks.
- Packs provide trusted sources, prompt additions, allowed tools, memory defaults, and review rules.
- The base runtime stays the same for Nostr, Bitcoin, Lightning, security, executive assistant, webmaster, fabrication, electrical, and coding flavors.

## Proposed release boundary
Call this release **v1.0.1 - Foundation Hardening**.

Do not include:
- live Nostr signing
- live finance execution
- autonomous repo pushes
- autonomous website deploys
- broad web crawling
- hardware control

## Files in this kit
- `app/schemas/memory_v2.py` — reviewed memory schema for selective persistence
- `app/policy/agentic_overlay.py` — policy overlay for agent modes and step-up gating
- `app/policy/agentic_modes.yaml` — example config for observer/curator/operator modes
- `app/packs/pack_manifest.schema.json` — schema for domain packs
- `app/packs/examples/nostr.pack.yaml` — first example pack
- `app/packs/examples/webmaster.pack.yaml` — second example pack

## Suggested 5-day build order

### Day 1 — runtime cleanup
- Update README so `app/` is the only primary runtime path.
- Mark `src/` as compatibility only.
- Keep `grok-legacy` callable, but document it as deprecated.
- Add a startup log warning when legacy path is used.

### Day 2 — selective memory
- Add reviewed memory schema.
- Add migration for new DB columns:
  - `review_status`
  - `reviewed_by`
  - `reviewed_at`
  - `review_reason`
  - `tags`
  - `scope`
  - `pack_name`
  - `canonical`
  - `pinned`
  - `ttl_seconds`
  - `supersedes_memory_id`
- Add API/CLI endpoints for approve/reject/archive/promote.

### Day 3 — policy agent modes
- Add `agent_mode` to session or execution context.
- Run `agentic_overlay.evaluate_agentic_overlay(...)` before the current policy engine final allow path.
- Default mode for all new sessions: `interactive`.
- Default mode for 24/7 watchers: `observer`.

### Day 4 — pack loader
- Load one optional pack per session/workspace.
- Merge pack prompt, sources, and tool policy with workspace policy.
- Fail closed if a pack requests tools outside the workspace’s allowed set.

### Day 5 — first living knowledge loop
- Add one dry-run repo watcher job.
- Permit it to read docs/changelogs/releases and create `candidate` memories only.
- Add one review screen/CLI command to promote or reject those notes.

## Release notes draft

### Added
- reviewed selective memory schema
- agent modes for controlled automation
- domain pack manifest format
- clear runtime authority around `app/`

### Changed
- `app/` is now the official runtime surface
- AI-generated memory is no longer treated as automatically durable truth

### Security
- safer path for future 24/7 monitoring by separating observation, curation, and operation
- better provenance and review boundaries for persistent memory

## Immediate backlog after v1.0.1
- rate limiting enforcement in ToolBroker
- compound shell command rejection
- memory secret scanning beyond `is_secret`
- step-up approval implementation (TOTP or hardware key)
- hash-chained append-only audit trail
- PostgreSQL RLS for hard workspace isolation
- pack loader + validation at startup

## Opinionated rule
Never let Grokenstein “learn” straight into canonical memory from raw model output. All autonomous learning should enter as candidate evidence with provenance and a review path.
