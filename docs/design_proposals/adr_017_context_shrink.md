# ADR-017: Context Shrink and Minimal Projection Protocol

## Status
Accepted

## Context
Feeding massive continuous file dumps into LLM context windows causes attention degradation and massive token costs.

## Decision
S-Class projects minimal context slices containing only active leases, assumptions, and required AST interfaces.
