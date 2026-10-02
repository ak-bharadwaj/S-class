# S-Class v6.0.1 — Concrete Control-Plane Runtime

This directory contains the executable S0–S5 control-plane components layered around the canonical semantic authority in `10-CONFORMANCE/sclass_semantics_v6_0_1.py`.

## Authority rule

```text
Command
  -> canonical validation/signature
  -> SQLite CAS transaction
  -> ReferenceReducer
  -> immutable EngineeringState
  -> state_digest
  -> nonce/budget/lease control
  -> OS boundary
  -> observation/evidence/assessment
  -> release/recovery
```

No runtime component may maintain a second canonical engineering-state authority.

## Implemented components

- `SClassControlPlane`: command idempotency and one-writer SQLite transaction boundary.
- `SQLiteCommandLedger`: workspace-scoped command identity and replay protection.
- `SQLiteNonceStore`: single-use nonce issuance/consumption with binding checks.
- `SQLiteBudgetAllocator`: cumulative, versioned budget reservations with atomic availability checks.
- `SQLiteRetryBudgetStore`: monotonic retry consumption and same-failure convergence protection.
- `SQLiteBreakGlassLedger`: atomic bounded break-glass consumption.
- `SQLiteKeyDirectory`: Ed25519 key registration, trust roots, rotation, revocation and expiry.
- `ExecutionAdmission`: atomic BudgetReserved → LeaseIssued → ExecutionIntent admission with nonce consumption.
- `LinuxExecutionBoundary`: fail-closed OS adapter; privileged execution requires Bubblewrap on Linux.
- `ExternalEffectReconciler`: explicit provider-status reconciliation; unknown effects remain unknown.
- `DeterministicRecoveryEngine`: durable recovery-case journal with explicit unresolved-effect handling.
- `CrashHarness`: subprocess crash probes for the K1–K6 transaction boundary.

## Serialization

Durable canonical event/commit/projection/checkpoint objects use the canonical C1 representation. Python pickle is not the durable canonical format.

## Verification

The package-level verification command is:

```text
python -m pytest -q
python 10-CONFORMANCE/spec_integrity.py
node 10-CONFORMANCE/c1_independent.js
python -m compileall -q 10-CONFORMANCE 20-RUNTIME
```

The current package was verified with **69 passing tests**. The OS adapter is fail-closed when Bubblewrap is unavailable; a host without the required sandbox primitive must not be treated as an evidence-bearing production reference environment.
