# ADR 0005: Tree-sitter and SCIP for Semantic Intelligence

## Status
Accepted

## Context
To verify claims accurately and efficiently, S-Class must determine which functions, classes, and test suites are impacted when files change. Creating proprietary code parsers or graph databases across multiple languages is economically unviable and fragile.

## Decision
1. Adopt Tree-sitter as the foundational syntax parsing engine for fast, incremental, error-tolerant concrete syntax tree (CST) generation and changed symbol localization.
2. Adopt SCIP (Source Code Intelligence Protocol) as the standardized protocol and schema for cross-file definitions, references, and semantic navigation.
3. Combine Tree-sitter AST ranges and SCIP references into a deterministic verification planner that dictates which test suites must be executed for a given code change.

## Consequences
- **Positive**: High speed, multi-language support (40+ languages), resilient to syntax errors during active coding.
- **Negative**: SCIP indexers must be generated or updated during build or verification cycles.
- **Invariants Upheld**: Invariant I4 (Verification cannot be substituted by caller-selected verifier output).
