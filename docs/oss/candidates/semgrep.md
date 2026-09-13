# OSS Candidate Evaluation: Semgrep

## 1. Candidate Overview
- **Project**: Semgrep (`semgrep/semgrep`) — https://github.com/semgrep/semgrep
- **Purpose**: Fast, lightweight static analysis engine for finding bugs, enforcing code standards, and discovering security vulnerabilities across 30+ programming languages. Syntax-aware pattern matching using familiar code syntax.
- **License**: LGPL-2.1 (core engine) / Semgrep Community License.
- **Primary Language / Ecosystem**: OCaml (core engine for AST parsing and matching), Python CLI, rule registries in YAML.

## 2. Maturity & Governance
- **Maturity**: Developed by Return To Corp / Semgrep since 2018. Over 6 years of active production adoption in thousands of DevSecOps pipelines.
- **Maintainer Health**: Full-time engineering team at Semgrep Inc., backed by strong open-source community contributions.
- **Release Cadence**: Frequent weekly releases with continuous rule registry updates.

## 3. Engineering Rigor & Trustworthiness
- **Security**: Strict rule execution time limits, sandboxed rule evaluations, automated testing against thousands of vulnerable code samples.
- **Testing**: Extensive regression tests across AST parsers for Python, JS/TS, Go, Java, Rust, C/C++, Ruby, and more.
- **Production Evidence**: Used by Dropbox, Slack, Figma, Snowflake, and hundreds of top software engineering organizations.
- **Platform Coverage**: Cross-platform (Linux, macOS, Windows via Python CLI and pre-compiled binaries).
- **Protocol Compliance**: Outputs structured SARIF (Static Analysis Results Interchange Format) and JSON.
- **Performance**: High speed pattern matching (~20,000-100,000 lines/second).

## 4. Architectural Fit & S-Class Boundaries
- **Integration Cost**: Low. Installed via `pip install semgrep` or standalone binary.
- **Failure Modes**: Parser syntax error on bleeding-edge syntax, analysis timeout on massive generated files, false positives in complex inter-procedural flows.
- **What We Adopt**: AST-based static pattern matching, security vulnerability detection, rule-based verification evidence.
- **What We DON'T Adopt**: Semgrep outputs are NOT accepted as absolute truth. They serve as `SecurityEvidence` candidate receipts in multi-verifier adjudications (combined with tests and CodeQL).
- **S-Class Wrapper**: `sclass.verification.providers.semgrep_verifier.SemgrepVerifier` implementing `VerificationProvider`. Emits `EvidenceReceipt` with SARIF rule findings, hashes, and run metrics.
- **Escape Plan**: `VerificationProvider` interface abstracts static analyzers. S-Class can run CodeQL, Ruff, Flake8, ESLint, or native linters without modifying the verification engine.

## 5. Architectural Decision
- **Decision**: `WRAP`
- **Architectural Tier**: Tier 2 (Pluggable Security Verification Provider)
- **Rationale Summary**: Semgrep provides fast, multi-language security linting and pattern enforcement out of the box. Wrapping it as an evidence provider enriches S-Class verification decisions without creating a hard proprietary dependency.
