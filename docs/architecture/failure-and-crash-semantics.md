# Architecture: Failure and Crash Semantics

## 1. Twelve Crash Boundaries

S-Class explicitly specifies recovery semantics across twelve discrete execution boundaries:

1. **Before Authorization**: Intent persists; safe to replay.
2. **After Authorization**: Authorization persists; action can proceed under existing decision.
3. **Before Effect**: Action pending; safe operations replay; mutating actions re-evaluated.
4. **During Effect**: Operation state recorded; NEVER operations fail closed; cannot auto-replay.
5. **After Effect**: Result recorded; observation pending.
6. **Before Observation**: Effect output available; observation step executed.
7. **After Observation**: Observation persisted; evidence evaluation pending.
8. **Before Evidence Settlement**: Observation verified; evidence receipt creation pending.
9. **After Evidence Settlement**: Evidence receipt committed to ledger; claim promotion pending.
10. **Before Claim Promotion**: Receipt validated; claim update pending.
11. **After Claim Promotion**: Claim state verified; clean state reached.
12. **Before Regression Verification**: Verified claim recorded; regression sweep pending.

## 2. Invariant

At no point can an interrupted execution silently synthesize false project truth. Malformed or corrupt states fail closed.
