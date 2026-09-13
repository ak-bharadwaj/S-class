# Subsystem Evaluation: Semantic Intelligence & Code Parsing

## 1. Subsystem Scope & Requirements
The Semantic Subsystem understands the structural and relational consequences of code modifications:
1. **Changed Symbol Localization**: Identify exact functions, classes, and types affected by a diff.
2. **Impact Boundary Analysis**: Determine downstream callers, modules, and tests requiring re-verification.
3. **Speed & Resilience**: Parse incomplete or temporarily broken code during active agent editing loops without crashing.

---

## 2. Candidates Evaluated

| Technology | Category | Strengths | Weaknesses | S-Class Decision |
| :--- | :--- | :--- | :--- | :--- |
| **Tree-sitter** | Incremental AST Parser | Ultra-fast incremental re-parsing, resilient to syntax errors, C ABI, 40+ languages | AST is purely syntactic; does not resolve cross-file types or references | **ADOPT (Syntax Plane)** |
| **SCIP (Sourcegraph)** | Language-Agnostic Code Index Protocol | Formal protobuf schema for symbols, definitions, references; multi-language indexers | Requires language-specific indexers run ahead-of-time or on-demand | **ADOPT (Semantic Plane)** |
| **LSP (Language Server Protocol)** | Editor Navigation Protocol | Universal IDE support | Heavy stateful background daemons per language; slow for batch analysis | **REJECT for core indexing** |
| **Proprietary Code Graph Engine** | Custom In-Memory AST graph | Tailored to S-Class | Massive engineering effort, breaks across languages, unmaintainable | **REJECT (Anti-pattern)** |

---

## 3. The 2-Tier Semantic Pipeline

```
                       Git Diff / Edited File
                                 │
                                 ▼
                     Tree-sitter Incremental Parser
                       - Concrete Syntax Tree (CST)
                       - Error-tolerant tokenization
                       - Modified AST Nodes & Symbols
                                 │
                     Changed Symbols (e.g. `verify_jwt`)
                                 │
                                 ▼
                        SCIP Index Resolver
                       - Symbol References
                       - Downstream Callers
                       - Dependent Test Files
                                 │
                                 ▼
                     Deterministic Impact Matrix
                 - Tests to execute: `tests/auth/*`
                 - Verifiers required: `SecurityVerifier`
                                 │
                                 ▼
                     Verification Planner (S-Class)
```

---

## 4. Architectural Decision
- Adopt **Tree-sitter** for syntax parsing, symbol bounding, and incremental diff parsing.
- Adopt **SCIP** as the standardized protocol for cross-file references and navigation.
- S-Class consumes these facts to build deterministic verification plans, preventing agents from arbitrarily skipping relevant test suites.
