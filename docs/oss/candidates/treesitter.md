# OSS Candidate Evaluation: Tree-sitter

## 1. Candidate Overview
- **Project**: Tree-sitter (`tree-sitter/tree-sitter`) — https://github.com/tree-sitter/tree-sitter
- **Purpose**: Fast, robust, incremental parser generator tool and incremental parsing library. Builds concrete syntax trees (CST) for source files and efficiently updates syntax trees as files are edited in real time.
- **License**: MIT License (SPDX: `MIT`). Highly permissive and compatible.
- **Primary Language / Ecosystem**: C core with official bindings in Python (`tree-sitter`), Rust, Node.js, and C#. Over 100 grammar repositories maintained by community and language authors.

## 2. Maturity & Governance
- **Maturity**: Developed by GitHub / Atom team starting in 2017. Industry standard powering syntax highlighting and structural code intelligence in Neovim, Emacs, GitHub code navigation, Zed, and Cursor.
- **Maintainer Health**: Actively maintained under tree-sitter organization with core GitHub/Zed engineering contributors.
- **Release Cadence**: Regular stable releases with active 2026 release schedule for core ABI and grammar updates.

## 3. Engineering Rigor & Trustworthiness
- **Security**: Fuzz-tested with AFL and LibFuzzer. C runtime designed for untrusted input; handles arbitrary syntax errors and malformed tokens without crashing or infinite recursion.
- **Testing**: Thousands of corpus tests across dozens of programming languages. Comprehensive regression testing on incremental re-parsing.
- **Production Evidence**: Runs on millions of developer machines daily inside Neovim, Zed, GitHub.com, and Cursor.
- **Platform Coverage**: Cross-platform (Linux, macOS, Windows).
- **Protocol Compliance**: Generates standard S-expression CSTs and query syntax (pattern matching via S-expressions).
- **Performance**: Millisecond to sub-millisecond parsing times. Incremental parsing re-parses only modified subtrees in microseconds.

## 4. Architectural Fit & S-Class Boundaries
- **Integration Cost**: Low. Standard `pip install tree-sitter tree-sitter-languages` or pre-compiled language grammars.
- **Failure Modes**: Missing grammar for niche languages, memory consumption on massive single files (>100MB).
- **What We Adopt**: Incremental parsing, AST/CST node boundary detection, changed symbol identification, syntax error resilience.
- **What We DON'T Adopt**: Tree-sitter does not perform type checking, semantic resolution, or verification decisions. It produces structural syntax facts only.
- **S-Class Wrapper**: `sclass.semantic.syntax.TreeSitterParser` wrapping `SyntaxParser`. Converts file diffs into AST mutation ranges to calculate semantic impact.
- **Escape Plan**: Abstract `SyntaxParser` interface. If Tree-sitter is unavailable for a language, S-Class can fall back to regex heuristics or native AST modules (e.g. Python's `ast` module).

## 5. Architectural Decision
- **Decision**: `ADOPT`
- **Architectural Tier**: Tier 1 (Foundational Syntax Parsing)
- **Rationale Summary**: Writing custom parsers for multi-language projects is impractical and error-prone. Tree-sitter provides robust, incremental, error-tolerant CST generation, enabling S-Class to determine exactly which functions, classes, or symbols changed in a commit.
