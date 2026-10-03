# Changelog

All notable changes to S-Class are documented here.

## [6.0.1] - 2026-10-03
### Added
- **Layer E OpenTelemetry Tracing**: Distributed tracing hooks and span hierarchy.
- **Reality Lab Empirical Benchmarks**: T1-T10 benchmark suites and timing probes.
- **Fleet Coordination**: Symbol lease manager and assumption graph invalidation cascade.
- **ACP & MCP Protocols**: Agent Client Protocol JSON-RPC router and MCP security gates.

### Security Remediations
- Resolved DEFECT-01 through DEFECT-10:
  - Enforced fail-closed evaluation on untrusted verifiers (DEFECT-01).
  - Sanitized PATH against workspace binary shadowing (DEFECT-02).
  - Enforced cryptographic checksum validation on trusted verifiers (DEFECT-03).
  - Guarded against directory junctions and symlink spoofing (DEFECT-04).
  - Hardened Windows authorization secrets against same-user escalation (DEFECT-05).
  - Sealed JSONL append operations against partial write corruption (DEFECT-07).
