# Architecture: Recovery Lifecycle (D9 Kernel)

## 1. Lifecycle Stages

The D9 recovery lifecycle transitions deterministically:

```text
FAILURE / DRIFT
       |
       v
CANONICAL DIAGNOSIS
       |
       v
REPAIR OBLIGATION (Deterministic, identity-bound)
       |
       v
BOUNDED RECOVERY PLANNER (Declarative only; no direct execution)
       |
       v
S-CLASS AUTHORIZATION
       |
       v
RUNTIME EXECUTION
       |
       v
INDEPENDENT OBSERVATION
       |
       v
FRESH EVIDENCE (Old pre-repair evidence rejected)
       |
       v
TARGET CLAIM RE-VERIFICATION
       |
       v
REGRESSION FRONTIER VERIFICATION
       |
       v
CONVERGENCE
       |
       v
FRONTIER RECOMPUTATION
```

## 2. Hard Bounds

Autonomous recovery loops are strictly bounded by:
- Maximum attempts (monotonic counter)
- Maximum recursion depth
- Maximum budget / cost limits
- Fan-out limits

When bounds are exceeded, recovery terminates fail-closed with `RecoveryExhaustedError`.
