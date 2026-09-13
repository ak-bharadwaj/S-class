# ADR 0004: OpenTelemetry for Vendor-Neutral Observability

## Status
Accepted

## Context
S-Class requires structured observability across long-running developer sessions, multi-agent collaborations, policy evaluations, and verification test executions. Inventing a proprietary telemetry protocol or logging format fragments observability and limits integration with existing developer tooling and enterprise APMs.

## Decision
1. Standardize all diagnostic telemetry, tracing, and metric emission on OpenTelemetry (OTEL).
2. Establish canonical semantic domain attributes prefixed with `sclass.*` (`sclass.action.id`, `sclass.claim.id`, `sclass.receipt.id`, `sclass.agent.id`).
3. Decouple telemetry from the cryptographic ledger: OTEL provides operational and diagnostic visibility; the append-only SQLite ledger provides authoritative, immutable cryptographic proof.

## Consequences
- **Positive**: Direct compatibility with Jaeger, Prometheus, OpenTelemetry Collector, and commercial observability platforms.
- **Negative**: Adds dependency on OpenTelemetry Python SDK.
- **Invariants Upheld**: Invariant I5 (Accepted state references immutable evidence).
