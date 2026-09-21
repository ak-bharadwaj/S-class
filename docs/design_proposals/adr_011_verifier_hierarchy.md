# ADR-011: Multi-Verifier Consensus Hierarchy V0 to V7

## Status
Accepted

## Context
Different types of claims require different levels of epistemic verification.

## Hierarchy
- **V0**: Agent assertion (untrusted claim).
- **V1**: Process observation (PID, exit code).
- **V2**: File/repo diff observation (Merkle diffs).
- **V3**: Deterministic test runs (pytest, jest).
- **V4**: Static analysis (AST, typecheck, lint).
- **V5**: Semantic verification (invariant satisfaction).
- **V6**: Independent verifier model.
- **V7**: Multi-signal corroboration.
