# ADR-020: Cross-Agent Session Handoff Protocols

## Status
Accepted

## Context
Long-horizon projects benefit from switching models (e.g. Claude Code for planning, OpenAI Codex for terminal execution).

## Decision
S-Class serializes task graphs, active leases, and verified claims into a platform-agnostic handoff envelope.
