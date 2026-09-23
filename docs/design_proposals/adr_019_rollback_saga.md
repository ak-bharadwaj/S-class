# ADR-019: Rollback and Recovery Saga Engine

## Status
Accepted

## Context
Failed multi-file refactors leave workspaces in broken, unbuildable states.

## Decision
S-Class journals reverse mutations. On verification failure, the saga engine executes compensating writes to restore the clean baseline.
