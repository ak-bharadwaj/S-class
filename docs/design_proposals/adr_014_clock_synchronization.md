# ADR-014: Deterministic Clock Synchronization for Distributed Agents

## Status
Accepted

## Context
Distributed agent swarms running on heterogeneous machines experience clock drift.

## Decision
S-Class implements Lamport logical timestamps and vector clocks across all published events.
