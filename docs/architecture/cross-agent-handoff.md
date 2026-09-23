# Architecture: Cross-Agent Handoff (`AssuranceHandoff`)

## 1. Overview

Cross-agent handoffs transport canonical, verified technical state across heterogeneous agent harnesses (e.g. Codex -> Claude Code -> Step-Code).

## 2. Structure of `AssuranceHandoff`

```text
AssuranceHandoff
├── task_id
├── verified_project_state_ref
├── verified_claims
├── active_obligations
├── stale_claims
├── failed_claims
├── open_frontier
├── evidence_references
├── workspace_identity
├── recovery_state
├── active_leases
└── required_next_actions
```

## 3. Law L9 Invariant

> **Handoff carries verified truth.**

Chat transcripts and LLM conversation histories are excluded from authoritative handoffs. Any participating agent runtime can resume execution directly from the verified assurance state.
