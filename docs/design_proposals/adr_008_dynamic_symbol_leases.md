# ADR-008: Dynamic Symbol Lease Allocation in Shared Workspaces

## Status
Accepted

## Context
Multi-agent swarms frequently attempt conflicting edits on shared source code repositories.

## Decision
S-Class enforces fine-grained AST symbol leases. Agents must acquire an exclusive lease before editing a class or function.
Leases auto-expire via TTL heartbeat timers to prevent deadlocks.
