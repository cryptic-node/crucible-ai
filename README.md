# Grokenstein v0.0.5

Grokenstein v0.0.5 is the **dependable apprentice** iteration.

This release builds on the governed runtime from v0.0.4 and adds:

- task objects and checkpoint persistence
- plan mode vs execute mode
- workspace inspection, search, and grounded summaries
- resume-after-restart behavior for tasks and sessions
- explicit memory promotion for durable facts
- approval-gated writes and shell execution

## Status

This is a local-first CLI foundation kit. It is intentionally conservative.
It is designed to be easy to inspect, test, and extend before adding more risky powers.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python -m grokenstein.main --id mysession --workspace ./workspace
```

## Useful commands

```text
!help
!task new Add task manager
!task plan
!task show
!task checkpoint first pass complete
!task done
!project inspect
!project summary
!project search planner
!memory promote current_goal Build dependable apprentice
!pending
!approve
!deny
```

## Runtime model

- read-only project inspection is allowed automatically
- filesystem writes require approval
- shell commands require approval and are allowlisted
- task state is stored on disk and resumes across restarts
- durable facts are only stored when explicitly promoted

## Notes

- The default model backend is a safe stub.
- Ollama support is included as an optional local adapter.
- This kit keeps the interface CLI-first on purpose.
