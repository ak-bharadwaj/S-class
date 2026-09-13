# ADR 0008: OpenCodeReview Reference Architecture for Deterministic / Agent Split

## Status
Accepted

## Context
AI-assisted coding systems often succumb to the failure mode of delegating all decisions—including file selection, rule application, and verification scope—to large language models. This leads to nondeterministic skips, hallucinated verifications, and inefficient token usage. OpenCodeReview demonstrated high production reliability by cleanly separating deterministic engineering from agent reflection.

## Decision
1. Mine OpenCodeReview as a reference architecture (Tier 3), adopting its structural design patterns without importing its application code directly into the S-Class runtime.
2. Adopt the **Deterministic Engineering + Agent Reasoning** split:
   - Deterministic filters (AST diffs, SCIP symbol references, rule matching) select files and target test suites.
   - Agents provide reasoning and qualitative reflection on the deterministically selected scope.
3. Adopt the **Unified Capability Provider** pattern for MCP tool aggregation: external tools are discovered and wrapped into an internal provider registry with collision resolution.
4. Adopt real-world PR and repository benchmarks to evaluate S-Class false acceptance rates.

## Consequences
- **Positive**: Eliminates agent hallucination in test selection; drastically improves verification determinism and efficiency.
- **Negative**: Requires maintaining deterministic analysis pipelines alongside agent protocols.
- **Invariants Upheld**: Invariant I1 (Agent claims are untrusted), Invariant I4 (Verification cannot be substituted by caller-selected verifier output).
