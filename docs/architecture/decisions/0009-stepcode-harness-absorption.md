# ADR 0009: Step-Code Harness Absorption & Assurance-Plane Consolidation

## Status
Accepted

## Context
Step-Code provides a mature runtime execution plane for terminal coding agents, including durable operation state, tool execution, session management, and command permission analysis. S-Class requires a mature execution harness while maintaining its position as the independent epistemic authority for technical obligations, evidence verification, recovery, and completion.

## Decision
1. Separate execution and assurance into two explicit planes.
2. Adapt Step-Code's durable operation lifecycle into lower execution handling via `StepCodeHarness`.
3. Separate runtime truth from project truth across two ledgers: `ExecutionLedger` (runtime) and `AssuranceLedger` (S-Class).
4. Establish dual-layer authorization: S-Class policy gate + Step-Code runtime permission analysis.
5. Retain S-Class as the sole authority for Technical Obligations, Claim/Evidence Graphs, Mutation Invalidation, Bounded Recovery, and Independent Completion Adjudication.

## Consequences
- S-Class does not duplicate general LLM provider loops, conversation trees, or tool runners.
- Any execution harness (Step-Code, Claude Code, Codex, Custom) can operate the project without altering S-Class assurance semantics.
- Runtime claims or goal complete signals can never directly establish verified project truth.
