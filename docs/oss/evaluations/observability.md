# Subsystem Evaluation: Observability & Telemetry

## 1. Subsystem Scope & Requirements
The Observability Subsystem captures traces, metrics, and logs across S-Class components:
1. **End-to-End Tracing**: Trace an agent prompt from protocol ingress through policy decision, subprocess execution, observation, receipt anchoring, and verification verdict.
2. **Deterministic Correlation**: Correlate actions, tasks, and claims using cryptographic receipts and execution IDs.
3. **Vendor Neutrality**: Allow developers and teams to export telemetry to any local tool (Jaeger, Prometheus, OpenTelemetry Collector) or cloud APM (Datadog, Honeycomb, New Relic) without code changes.

---

## 2. Candidates Evaluated

| Technology | Scope | Pros | Cons | S-Class Decision |
| :--- | :--- | :--- | :--- | :--- |
| **OpenTelemetry (OTEL)** | Traces, Metrics, Logs | Global CNCF standard, OTLP protocol, vendor-agnostic, rich context propagation | Small runtime dependency in Python | **ADOPT (Foundational)** |
| **Custom Local JSONL Logger** | Disk-based event log | Zero dependencies, simple to inspect | Proprietary format, no standard visualization, breaks across distributed nodes | **Secondary / Fallback sink** |
| **Prometheus Client** | Metrics only | Mature metric aggregation | No distributed tracing or structured lifecycle logs | **Export via OTEL Collector** |

---

## 3. Telemetry Architecture

```
                  Agent Protocol Event (ACP / MCP)
                               │ [trace_id: a1b2c3d4...]
                               ▼
                        S-Class Policy Check
                               │ [span: policy.evaluate]
                               ▼
                       Action Execution Plane
                               │ [span: process.execute]
                               ▼
                       Independent Observation
                               │ [span: process.observe]
                               ▼
                     Evidence Receipt Anchoring
                               │ [span: ledger.anchor]
                               ▼
                     Verification Adjudication
                               │ [span: claim.verify]
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
   OpenTelemetry Exporter                 S-Class Cryptographic Ledger
   (OTLP -> Jaeger / Cloud)               (Authoritative SQLite & SHA-256)
   - Diagnostic observability             - Immutable proof of truth
```

### Critical Invariant: Telemetry != Authoritative Ledger
OpenTelemetry provides **diagnostic observability** for humans and monitoring systems. The **cryptographic ledger** (SQLite WAL + SHA-256 hash chain) remains the sole authoritative proof of verification and trust.

---

## 4. Architectural Decision
- Adopt **OpenTelemetry** as the universal telemetry protocol.
- Standardize on `sclass.*` semantic attributes.
- Ensure telemetry export is asynchronous and non-blocking so observability failures never impact core verification operations.
