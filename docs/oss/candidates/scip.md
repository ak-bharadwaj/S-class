# OSS Candidate Evaluation: SCIP (Source Code Intelligence Protocol)

## 1. Candidate Overview
- **Project**: SCIP (`sourcegraph/scip`) — https://github.com/sourcegraph/scip
- **Purpose**: Language-agnostic protocol and index format for code navigation and cross-repository code intelligence. Defines standard schemas for definitions, references, implementations, document symbols, and package dependencies using Protocol Buffers.
- **License**: Apache License 2.0 (SPDX: `Apache-2.0`). Fully compatible.
- **Primary Language / Ecosystem**: Protocol Buffers schema, Go/Rust/TypeScript/Python bindings and CLI tools. Indexers available for Go, TypeScript, Java/Kotlin, Rust, C/C++, Ruby, Python (`scip-python`).

## 2. Maturity & Governance
- **Maturity**: Created by Sourcegraph in 2022 to succeed LSIF (Language Server Index Format). Used in enterprise code search and navigation across billions of lines of code.
- **Maintainer Health**: Sourcegraph engineering team and active open-source contributors.
- **Release Cadence**: Stable schema specification v1 with backwards-compatible protobuf extensions.

## 3. Engineering Rigor & Trustworthiness
- **Security**: Protocol buffer deserialization with strict length boundaries. Deterministic indexes with content hashes for document symbols.
- **Testing**: End-to-end index snapshot tests, cross-indexer compatibility tests, fuzzing on index parsers.
- **Production Evidence**: Powers Sourcegraph global code search, Cody AI code context engine, and large enterprise codebases (Uber, Datadog).
- **Platform Coverage**: Cross-platform (Linux, macOS, Windows).
- **Protocol Compliance**: Formal Protobuf schema definitions; compatible with LSP symbol resolution semantics.
- **Performance**: High performance serialized Protobuf format. Can index and query millions of symbols in seconds.

## 4. Architectural Fit & S-Class Boundaries
- **Integration Cost**: Low to Moderate. S-Class reads SCIP indexes via `scip-protobuf` Python packages or CLI output.
- **Failure Modes**: Missing indexer for a language, corrupted index file, out-of-sync index after code changes.
- **What We Adopt**: Standardized symbol schema, definition/reference relationship graph, semantic fact extraction.
- **What We DON'T Adopt**: S-Class does not use SCIP to decide trust or safety. SCIP informs *what* was semantically impacted by a change; S-Class verifies whether that change satisfies invariants.
- **S-Class Wrapper**: `sclass.semantic.scip.SCIPSemanticAnalyzer` wrapping `SemanticIndexer`. Queries SCIP index to map modified AST nodes to downstream dependent callers and tests.
- **Escape Plan**: The `SemanticIndexer` interface abstracts the index provider. If SCIP is unavailable, S-Class falls back to Tree-sitter symbol search or regex-based symbol cross-referencing.

## 5. Architectural Decision
- **Decision**: `ADOPT`
- **Architectural Tier**: Tier 1 (Foundational Semantic Intelligence)
- **Rationale Summary**: Reinventing a proprietary code graph database creates technical debt. SCIP provides a battle-tested, open standard for cross-file definitions and references, enabling deterministic verification planning without proprietary lock-in.
