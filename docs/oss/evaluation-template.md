# S-Class OSS Candidate Evaluation Template

Every third-party OSS dependency, protocol SDK, or execution/verification candidate MUST be evaluated against this schema prior to introducing code or architectural dependencies.

---

## 1. Candidate Overview
- **Project**: [Project Name and Repository URL]
- **Purpose**: [What problem does it solve?]
- **License**: [SPDX License identifier and compatibility with Apache 2.0 / MIT / proprietary distribution]
- **Primary Language / Ecosystem**: [Language, runtime requirements, C-bindings, etc.]

## 2. Maturity & Governance
- **Maturity**: [Age, major version, API stability guarantees, governance body (CNCF, Apache, Linux Foundation, independent)]
- **Maintainer Health**: [Number of core maintainers, organization backing, bus factor, commit activity]
- **Release Cadence**: [Release frequency, semantic versioning adherence, deprecation cycles]

## 3. Engineering Rigor & Trustworthiness
- **Security**: [CVE history, audit reports, vulnerability disclosure policy, memory safety characteristics]
- **Testing**: [Branch/line coverage, fuzzing, fault injection, crash/restart/recovery tests, CI rigor]
- **Production Evidence**: [Major production adopters, scale, real-world deployment track record]
- **Platform Coverage**: [Linux, macOS, Windows support level, architecture support (x86_64, aarch64)]
- **Protocol Compliance**: [Standards conformance, RFC/spec adherence, wire compatibility guarantees]
- **Performance**: [Latency overhead, memory footprint, cold start, throughput under realistic loads]

## 4. Architectural Fit & S-Class Boundaries
- **Integration Cost**: [Effort to integrate, dependency footprint, transitive dependency risks]
- **Failure Modes**: [What happens when it crashes, hangs, corrupts state, or receives malformed input?]
- **What We Adopt**: [Concrete components, schemas, protocols, or libraries we consume]
- **What We DON'T Adopt**: [Specific parts we refuse, delegate, or actively prohibit from owning trust]
- **S-Class Wrapper**: [Adapter interface, boundary translation, invariant enforcement layer]
- **Escape Plan**: [Cost and strategy to replace this component if deprecated, compromised, or divergent]

## 5. Architectural Decision
- **Decision**: `ADOPT` | `WRAP` | `EXTEND` | `REFERENCE` | `REJECT`
- **Architectural Tier**: Tier 1 (Foundational Infrastructure) | Tier 2 (Pluggable Provider) | Tier 3 (Design Reference)
- **Rationale Summary**: [Core thesis explaining why this decision minimizes custom build surface while preserving S-Class invariants]
