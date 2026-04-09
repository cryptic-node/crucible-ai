# Grokenstein v1.0.0 — Threat Model

## Assets

| Asset                      | Sensitivity | Notes                                           |
|----------------------------|-------------|------------------------------------------------|
| LLM API keys               | CRITICAL    | Access to paid model APIs; exfiltration = cost |
| Workspace files            | HIGH        | User data, documents, code                     |
| Memory records             | HIGH        | Personal context, projects, task history       |
| Bitcoin/Lightning keys     | CRITICAL    | Financial loss; stubs only in v1.0.0           |
| Nostr private keys (nsec)  | HIGH        | Identity impersonation; stubs only in v1.0.0   |
| Audit logs                 | MEDIUM      | Operational data; tampering hides attacks      |
| Session tokens             | MEDIUM      | Session hijacking                              |
| Policy configuration       | HIGH        | Disabling controls enables other attacks       |

---

## Trust Boundaries

1. **User ↔ Brain** — User-supplied input; trust level set at session start
2. **Brain ↔ ToolBroker** — Internal boundary; Brain cannot call handlers directly
3. **ToolBroker ↔ PolicyEngine** — Every tool call evaluated; no bypass possible
4. **Tool ↔ Filesystem** — `/workspace` boundary enforced in tool code
5. **Tool ↔ Shell** — Command allowlist enforced; no arbitrary execution
6. **Memory ↔ DB** — Provenance and workspace isolation enforced in service layer
7. **Finance/Nostr ↔ Live systems** — Stub boundary; no live signing in v1.0.0

---

## Threat Vectors and Mitigations

### 1. Prompt Injection / Jailbreak
**Threat:** Attacker crafts input to make LLM emit tool calls that bypass policy.

**Mitigation:**
- All tool calls go through ToolBroker, which independently validates and calls PolicyEngine
- LLM output is never executed directly; tool calls are parsed and validated against Pydantic schemas
- Brain cannot expose tool handlers to raw LLM output

**Deferred:** Semantic intent classification (detecting indirect injection in multi-step plans)

---

### 2. Path Traversal / Filesystem Escape
**Threat:** Tool call with `../../../etc/passwd` or absolute paths outside `/workspace`.

**Mitigation:**
- `_resolve_safe()` resolves candidate path and verifies it starts with workspace root
- Both read and write operations enforce this check
- Absolute path inputs are resolved relative to workspace root

**Status:** Implemented and tested.

---

### 3. Shell Command Injection / Allowlist Bypass
**Threat:** Attacker crafts command with pipes, redirects, or subshells to escape allowlist.

**Mitigation:**
- Only the base command name is checked against the allowlist
- Dangerous commands (rm, curl | bash, etc.) not in allowlist
- Shell timeout enforced to prevent resource exhaustion

**Deferred:** Full command parsing (no `; rm -rf` pattern detection yet). Consider using `shlex` strict mode and rejecting compound commands.

---

### 4. Secret Exfiltration via Memory
**Threat:** Attacker stores private key or API key in a memory record for later exfiltration.

**Mitigation:**
- MemoryService rejects records with `is_secret=True`
- Memory records are workspace-scoped; cross-workspace read blocked at service layer
- Audit log records input hashes, not raw values

**Deferred:** Content scanning of memory values (detect key-like patterns before storage).

---

### 5. Trust Level Escalation
**Threat:** LOW-trust channel attempts to perform HIGH-trust operations.

**Mitigation:**
- Trust level set at session creation; cannot be changed by user during session
- PolicyEngine checks trust level on every tool call
- Finance operations require HIGH trust; LOW-trust sessions are read-only for sensitive tools
- Identity-changing operations require step-up (require_approval or escalate_channel)

**Deferred:** Cryptographic proof of identity for step-up (TOTP, hardware key).

---

### 6. Policy Engine Bypass / Kill Switch Tampering
**Threat:** Attacker modifies `KILL_SWITCH=false` env var or policy YAML to re-enable denied tools.

**Mitigation:**
- Kill switch is read from environment at startup; not modifiable via API
- Policy config file path is configurable but read-only at runtime
- Per-workspace kill switch in YAML as additional layer
- All tool calls always go through PolicyEngine; no internal bypass path

**Deferred:** Policy config signing (HMAC or GPG) to detect tampering.

---

### 7. Audit Log Tampering
**Threat:** Attacker deletes or modifies audit log to hide activity.

**Mitigation:**
- Audit log written append-only to file
- Each record includes correlation_id and timestamp
- Input hashes allow detection of modified inputs post-hoc
- DB-backed audit table provides secondary record

**Deferred:** Append-only audit log (immutable DB table, hash chaining, remote syslog sink).

---

### 8. Finance / Lightning Payment Execution
**Threat:** LLM or injected prompt triggers live payment.

**Mitigation:**
- All finance tools are stubs; no live RPC client connected in v1.0.0
- PaymentProposal schema has `dry_run=True` by default; validate_not_live() enforced
- PolicyEngine requires HIGH trust + simulation before any finance tool execution
- `require_simulation` decision blocks live execution until dry_run is confirmed first

**Deferred:** Multi-step approval chain (dry_run → user confirm → execute with TOTP).

---

### 9. Nostr Identity Impersonation / Unauthorized Publishing
**Threat:** LLM triggered to publish Nostr events or sign messages as the user.

**Mitigation:**
- NostrSigningBoundary has `dry_run=True` by default; validate_not_live() enforced
- Identity tools (nostr_publish, nostr_sign) trigger `require_approval` from PolicyEngine
- LOW-trust channels trigger `escalate_channel` for identity tools
- Relay allowlist enforced in RelayAllowlist schema

**Deferred:** NIP-46 remote signer integration; approved sender list for DM commands.

---

### 10. Cross-Workspace Memory Leakage
**Threat:** Session in workspace A reads memory records from workspace B.

**Mitigation:**
- MemoryService enforces `workspace_id` filter on all read operations
- `get()` and `list()` check `workspace_id` match before returning
- DB-backed records have FK to workspace; queries scoped by workspace
- Audit log partitioned by workspace

**Deferred:** Row-level security (PostgreSQL RLS) for hard enforcement at DB layer.

---

## Deferred Items Summary

| Item                                    | Priority | Notes                              |
|-----------------------------------------|----------|------------------------------------|
| Semantic injection detection            | HIGH     | Requires intent classifier         |
| Compound shell command rejection        | HIGH     | shlex parsing + pattern deny       |
| Memory content scanning                 | MEDIUM   | Regex/ML for key-like patterns      |
| Cryptographic step-up for trust upgrade | HIGH     | TOTP or hardware key               |
| Policy config signing                   | MEDIUM   | HMAC or GPG verification           |
| Append-only audit log with hash chain   | MEDIUM   | Tamper-evident audit               |
| Multi-step payment approval chain       | HIGH     | Required before live finance       |
| NIP-46 remote signer integration        | HIGH     | Required before live Nostr         |
| PostgreSQL RLS for workspace isolation  | MEDIUM   | Hard enforcement at DB layer       |
