# ADR 0007: Multi-Verifier Evidence Adjudication Framework

## Status
Accepted

## Context
Verifying complex software claims (e.g. "implemented feature X securely without regressions") cannot rely on a single verification tool. Unit tests may pass while a SQL injection or hardcoded credential remains undetected. Conversely, static analyzers may produce false positives.

## Decision
1. Implement a pluggable `VerificationProvider` framework where multiple independent verification tools (pytest, Jest, Semgrep, CodeQL, Schemathesis, Syft) contribute evidence.
2. Every provider outputs a standardized `EvidenceReceipt` containing tool identity, command args, execution receipt references, and findings.
3. S-Class acts as the sole authoritative adjudicator:
   - Verifies that receipts match immutable ledger entries.
   - Evaluates multi-verifier confidence.
   - Invalids claims immediately if workspace state changes between observation and adjudication.
4. No single external verifier possesses the authority to declare a claim `ACCEPTED`.

## Consequences
- **Positive**: Substantially higher epistemic confidence in software claims; prevents single-tool blind spots.
- **Negative**: Coordination overhead when running multiple verifiers.
- **Invariants Upheld**: Invariant I4 (Verification cannot be substituted by caller-selected verifier output), Invariant I6 (Workspace mutation invalidates dependent evidence).
