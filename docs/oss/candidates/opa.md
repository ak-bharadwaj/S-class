# OSS Candidate Evaluation: Open Policy Agent (OPA)

## 1. Candidate Overview
- **Project**: Open Policy Agent (`open-policy-agent/opa`) — https://github.com/open-policy-agent/opa
- **Purpose**: General-purpose open-source policy engine that decouples policy decision-making from enforcement. Takes arbitrary JSON/structured data as input and evaluates policies written in Rego to return structured decisions (ALLOW, DENY, REQUIRE_APPROVAL).
- **License**: Apache License 2.0 (SPDX: `Apache-2.0`). Fully compatible with S-Class goals.
- **Primary Language / Ecosystem**: Go (core engine). Compiles to WebAssembly (Wasm) and provides C-Go / Python bindings, HTTP REST daemon, and embedded Go packages.

## 2. Maturity & Governance
- **Maturity**: Graduated CNCF project (2021). Active since 2016 (over a decade of production hardening). Stable v1 API with strict semantic versioning.
- **Maintainer Health**: Backed by Styra, VMware, Microsoft, Google, Red Hat, and a broad CNCF governance body. High commit velocity, multi-vendor core maintainers, healthy bus factor.
- **Release Cadence**: Predictable monthly minor releases; immediate security patch releases.

## 3. Engineering Rigor & Trustworthiness
- **Security**: Comprehensive third-party security audits (Cure53 / CNCF). Documented security policy, CVE response process, automated fuzzing (OSS-Fuzz), and hardened memory safety via Go runtime.
- **Testing**: Thousands of unit tests, integration test suites, fuzzing harnesses, end-to-end benchmarks, and cross-platform regression pipelines.
- **Production Evidence**: Battle-tested at Goldman Sachs, Netflix, Pinterest, T-Mobile, Atlassian, and thousands of Kubernetes and cloud-native production environments worldwide.
- **Platform Coverage**: Cross-platform: Linux, macOS, Windows (amd64, arm64). Zero kernel dependencies.
- **Protocol Compliance**: Implements OPA REST API, Wasm ABI, bundle format v1, and OpenTelemetry logging integration.
- **Performance**: In-memory evaluation with compiled Rego rules. Sub-millisecond evaluation latency for standard authorization inputs.

## 4. Architectural Fit & S-Class Boundaries
- **Integration Cost**: Moderate. S-Class can invoke OPA via local embedded Wasm module, lightweight local daemon, or native Python wrapper (`opa-python` / `regopy`).
- **Failure Modes**: Engine crash, syntax error in Rego bundle, query timeout, or policy evaluation exception.
- **What We Adopt**: Rego query engine, structured JSON evaluation semantics, declarative policy bundles.
- **What We DON'T Adopt**: OPA does not enforce decisions, observe processes, or store project state. S-Class owns enforcement, execution intercept, observation, and cryptographic evidence.
- **S-Class Wrapper**: `sclass.control.policy.opa_engine.OPAPolicyEngine` implementing `PolicyEngine` interface. Normalizes `ActionRequest` into canonical OPA JSON input:
  ```json
  {
    "actor": "claude",
    "capability": "terminal.execute",
    "target": "pytest tests/auth/",
    "workspace": "/repo",
    "network": false,
    "risk": "low"
  }
  ```
- **Escape Plan**: Abstract `PolicyEngine` protocol interface (`evaluate(request: ActionRequest) -> PolicyDecision`). Can be seamlessly swapped or augmented with AWS Cedar or native Python rule compiler without altering S-Class authorization boundaries.

## 5. Architectural Decision
- **Decision**: `ADOPT`
- **Architectural Tier**: Tier 1 (Foundational Policy Engine)
- **Rationale Summary**: Re-implementing a domain-specific policy language and authorization engine in Python is wasteful and error-prone. OPA provides a graduated, battle-tested decision engine while S-Class strictly retains enforcement, identity, observation, and audit evidence.
