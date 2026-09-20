# ADR-009: Epistemic Assumption Graph and Invalidation Cascades

## Status
Accepted

## Context
When Agent A modifies an API signature, Agent B's ongoing code changes based on the old signature become invalid.

## Decision
We model cross-agent dependencies as a directed acyclic graph (DAG) of assumptions.
When a node statement is disproven, a cascading invalidation event immediately notifies dependent agents.
