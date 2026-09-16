# ADR-002: Deterministic JSONL Append Ledger as Authority Plane

## Status
Accepted

## Context
A durable project authority plane requires an append-only, human-auditable ledger format.

## Decision
We mandate newline-delimited JSON (JSONL) as the single source of truth for all events.
Each entry is appended with monotonic sequence IDs and cryptographic digests.

## Consequences
- Secondary projections (SQLite, in-memory graphs) can be rebuilt losslessly from JSONL logs.
- Guarantees crash-consistent recovery without proprietary binary formats.
