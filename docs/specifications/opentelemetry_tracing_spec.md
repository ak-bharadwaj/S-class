# Layer E — OpenTelemetry Tracing Specification

## 1. Overview
Layer E (Independent Observation) provides standard OpenTelemetry-compliant distributed tracing
for all actions performed by autonomous coding agents.

## 2. Span Hierarchy
```text
[sclass.task]
   └── [sclass.action]
          ├── [sclass.policy.evaluate]
          ├── [sclass.execution.dispatch]
          └── [sclass.verification.assess]
```

## 3. Semantic Attributes
| Attribute | Type | Description |
|-----------|------|-------------|
| `sclass.action.id` | string | Unique UUIDv4 identifier of the executed action |
| `sclass.task.id` | string | Identifier of the parent task or goal |
| `sclass.evidence.id` | string | SHA-256 digest of the observed execution evidence |
| `sclass.agent.id` | string | Agent identity (e.g. `codex-agent-01`, `claude-sub-02`) |
| `sclass.exit_code` | int | Physical process exit status code |
| `sclass.stdout_digest` | string | SHA-256 digest of captured stdout stream |

## 4. Sampling & Export
- Telemetry spans are emitted locally to `artifacts/telemetry.jsonl`.
- Batch exporter transmits spans to OTLP collector with fail-safe buffering.
