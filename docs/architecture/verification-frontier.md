# Architecture: Verification Frontier

## 1. Deterministic Derivation

The verification frontier is a purely derived, deterministic view of the remaining required verification actions:

```text
Frontier = f(VERIFIED, STALE, FAILED, UNRESOLVED_OBLIGATIONS, DEPENDENCY_GRAPH)
```

## 2. Invariants

1. **Never Trust Caller Frontier**: Caller-provided frontier assertions or agent opinions are rejected. The frontier is recomputed from canonical state.
2. **Never Trust Persisted Derived Timestamp**: A persisted or cached frontier timestamp cannot override a freshly recomputed canonical frontier timestamp.
3. **Determinism**: Given identical canonical state in `StateRepository`, `recompute_frontier()` always yields an identical set of frontier obligations.
