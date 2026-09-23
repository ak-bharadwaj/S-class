# Architecture: Replay Semantics

## 1. Classification

Every operation declares an explicit `ReplayClass`:

- **SAFE**: Pure read or idempotent inspection (e.g. `read_file`, `list_dir`, `run_tests`, `typecheck`). Can be replayed without side-effect risk or state duplication.
- **IDEMPOTENT**: Operations that produce identical outcomes given identical input state.
- **NEVER**: Non-idempotent or mutating effects (e.g. `write_file`, `git commit`, `publish`, `deploy`, external messages).

## 2. Replay Invariant

An interrupted or crashed effect classified as `NEVER` is NEVER automatically replayed.
Attempting an automated replay of a `NEVER` operation fails closed with `SecurityViolationError`.
A new technical repair obligation and explicit S-Class authorization are strictly required.
