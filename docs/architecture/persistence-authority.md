# Architecture: Persistence Authority

## 1. Authoritative vs Derived State

| State Domain | Storage Engine | Epistemic Authority |
| :--- | :--- | :--- |
| **Tasks & Recovery Records** | SQLite (`StateRepository`) | Authoritative |
| **Tamper-Evident Hash Chain** | JSONL (`LocalLedger`) | Authoritative |
| **Assurance Ledger** | JSONL (`AssuranceLedger`) | Authoritative |
| **Execution Ledger** | JSONL (`ExecutionLedger`) | Runtime authority only |
| **Frontier Cache** | Derived JSON | Derived / Non-authoritative |
| **Agent Context** | LLM memory | Contextual only (Law L10) |

## 2. Invalidation of Derived State

Authoritative state is immutable or ACID-persisted. Any discrepancy between derived caches and authoritative state resolves by discarding the cache and recomputing canonically from authoritative evidence.
