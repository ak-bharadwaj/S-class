# ADR 0002: SQLite for Authoritative Local State Persistence

## Status
Accepted

## Context
S-Class requires a local state persistence engine to record projects, tasks, claims, action requests, execution identities, observed receipts, verification verdicts, and cryptographic ledger blocks. Building a custom filesystem or JSON-based state store introduces race conditions, crash vulnerability, lack of transactionality, and data corruption risks.

## Decision
1. Standardize on SQLite as the sole foundational storage engine for local state and ledger chains.
2. Enable Write-Ahead Logging (`PRAGMA journal_mode = WAL`) and synchronous flushing (`PRAGMA synchronous = NORMAL`) to guarantee durability and fast concurrent reads.
3. Decouple storage from domain semantics: SQLite provides storage; S-Class provides state machine and transition semantics.
4. Fail closed on state corruption or database retrieval failure during recovery and handoff generation.

## Consequences
- **Positive**: Takes advantage of SQLite's 100% branch test coverage, crash recovery, and zero external dependency footprint.
- **Negative**: Local concurrency requires WAL mode and serialized write transactions.
- **Invariants Upheld**: Invariant I5 (Accepted state references immutable evidence), Invariant I7 (Handoff contains persisted truth, not chat memory).
