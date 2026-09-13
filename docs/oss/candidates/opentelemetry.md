# OSS Candidate Evaluation: OpenTelemetry (OTEL)

## 1. Candidate Overview
- **Project**: OpenTelemetry (`open-telemetry/opentelemetry-python` / `opentelemetry-collector`) — https://github.com/open-telemetry
- **Purpose**: Industry-standard, vendor-neutral telemetry framework providing unified specifications, SDKs, and tooling for traces, metrics, and logs across distributed systems.
- **License**: Apache License 2.0 (SPDX: `Apache-2.0`). Permissive and compatible.
- **Primary Language / Ecosystem**: Python SDK, Go Collector, cross-language specifications and wire protocols (OTLP).

## 2. Maturity & Governance
- **Maturity**: CNCF Graduated project. The undisputed global standard for modern observability, backed by all major cloud providers, observability vendors, and open-source ecosystems.
- **Maintainer Health**: Exceptionally healthy. Hundreds of active maintainers across dozens of working groups with institutional steering committee governance.
- **Release Cadence**: Regular bi-weekly minor updates, strict stability guarantees for Trace and Metric APIs, with backwards compatibility policies.

## 3. Engineering Rigor & Trustworthiness
- **Security**: Strict security policies, regular vulnerability disclosure handling, fuzz testing, dependency scanning, automated release signing.
- **Testing**: Thousands of automated unit and integration tests across Python 3.9-3.13, cross-platform CI matrix on Linux, macOS, and Windows.
- **Production Evidence**: Running at global scale across hyperscalers (Google, Microsoft, AWS) and enterprises worldwide.
- **Platform Coverage**: Universal platform support (POSIX and Windows).
- **Protocol Compliance**: Strictly complies with OTLP/gRPC, OTLP/HTTP, and W3C TraceContext standards.
- **Performance**: High-throughput asynchronous batch processors, non-blocking telemetry export, lightweight context propagation.

## 4. Architectural Fit & S-Class Boundaries
- **Integration Cost**: Minimal. Standard Python package `opentelemetry-api` and `opentelemetry-sdk` install cleanly into the S-Class environment.
- **Failure Modes**: Telemetry export failure, collector unreachability, context buffer exhaustion. All OTEL SDK operations fail gracefully without interrupting critical-path execution.
- **What We Adopt**: Trace and span models, semantic attribute conventions, context propagation, OTLP export format.
- **What We DON'T Adopt**: OTEL does not define S-Class trust semantics, evidence verification, or security policy. Telemetry observations are diagnostic exports, not the authoritative cryptographic ledger.
- **S-Class Wrapper**: `sclass.telemetry.otel.OTELTelemetryProvider` wrapping `TelemetryProvider`. Defines canonical `sclass.*` domain attributes:
  - `sclass.project.id`
  - `sclass.task.id`
  - `sclass.claim.id`
  - `sclass.action.id`
  - `sclass.execution.id`
  - `sclass.receipt.id`
  - `sclass.verification.id`
  - `sclass.policy.id`
  - `sclass.agent.id`
- **Escape Plan**: All instrumentation routes through S-Class internal interfaces (`emit_action_span`, `record_verification_metric`). Can swap back to local JSONL loggers or custom tracing if needed without touching business logic.

## 5. Architectural Decision
- **Decision**: `ADOPT`
- **Architectural Tier**: Tier 1 (Foundational Observability)
- **Rationale Summary**: Building a proprietary observability pipeline isolates S-Class from the developer ecosystem. By adopting OpenTelemetry, S-Class events, action lifecycles, and verification proofs integrate seamlessly into IDEs, daemons, CI pipelines, and cloud dashboards.
