# S-Class State & Persistence Model

## 1. Storage Architecture

S-Class utilizes a dual-tier persistence architecture:
1. **Append-Only Cryptographic Ledger (`ledger.jsonl`)**:
   - The primary source of truth for events, receipts, and hash chains.
   - Immune to state database corruption; can be replayed to reconstruct state.
2. **Relational State Database (`sclass.db`)**:
   - SQLite backed store for indexing tasks, projects, claims, checkpoints, and handoffs.
   - Fully version-controlled schema migrations under `src/sclass/storage/migrations/`.

## 2. Versioned Migrations

Schema migrations are strictly linear:
- `001_initial`: Core tables (`projects`, `tasks`, `claims`, `evidence`, `events`).
- `002_execution_identity`: Adds `process_pid`, `executable_hash`, `execution_chain`, `mode`.
- `003_claim_scope`: Adds structured `scope_json`, target files, and test identifiers to claims.
- `004_checkpoint`: Adds `checkpoints` and `handoffs` tables with ledger head bindings.

## 3. Checkpoints & Handoffs

- `ProjectCheckpoint`: Captures workspace fingerprint, git commit SHA, active tasks, verified claims, and ledger head hash.
- `AgentHandoff`: Encapsulates a cryptographic checkpoint, unresolved task list, verified invariant state, and context budget for seamless multi-agent collaboration.
