# ADR-003: SQLite Transient Indexed Projections

## Status
Accepted

## Context
High-frequency queries on claim states and symbol leases require low-latency indexing.

## Decision
SQLite is utilized exclusively as a transient, disposable read-projection derived from canonical JSONL logs.
The SQLite database file can be dropped and rebuilt at any time without data loss.

## Consequences
- ACID transactional concurrency for fast microsecond reads and lease checks.
- Zero fear of database corruption since JSONL remains the immutable source of truth.
