# Architecture: Execution Ledger vs Assurance Ledger

## 1. Domain Separation

S-Class enforces strict separation between two physical and conceptual ledgers:

```text
                  +---------------------------+
                  |     EXECUTION LEDGER      |
                  |                           |
                  | Owned by: Runtime Harness |
                  | Tracks:                   |
                  | - Tool calls              |
                  | - Operation states        |
                  | - Subagent spawns         |
                  | - Runtime retries         |
                  | - Exit codes / raw stdout |
                  | - Telemetry               |
                  +-------------+-------------+
                                |
                   Normalized Runtime Events /
                   Independent Observation
                                |
                                v
                  +-------------+-------------+
                  |     ASSURANCE LEDGER      |
                  |                           |
                  | Owned by: S-Class Core    |
                  | Tracks:                   |
                  | - Technical obligations   |
                  | - Verified claims         |
                  | - Cryptographic evidence  |
                  | - Verifier assessments    |
                  | - Truth invalidations     |
                  | - Verification frontier   |
                  | - Canonical project truth |
                  +---------------------------+
```

## 2. Hard Prohibition

```python
# FORBIDDEN:
assurance_ledger.direct_mutate_from_execution_ledger(exec_record)
# -> Raises SecurityViolationError
```

The Execution Ledger CANNOT directly mutate Assurance Truth.
All promotions into the Assurance Ledger must pass through independent observation, cryptographic provenance anchoring, and typed domain verification.
