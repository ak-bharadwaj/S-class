# Architecture: Security Boundaries & Dual Authorization

## 1. Dual-Layer Authorization

For any consequential action:

```text
Agent Requests Action
         |
         v
S-Class Obligation / Policy Authorization
         |
         +-- DENIED ---> Execution BLOCKED
         |
         v (ALLOWED)
Step-Code / Runtime Permission Analysis
         |
         +-- DENIED ---> Execution BLOCKED
         |
         v (ALLOWED)
Execution Proceed
```

## 2. Fail-Closed Invariant (Law L8)

- S-Class deny always blocks execution.
- Runtime deny always blocks execution.
- S-Class allow cannot bypass runtime sandboxes.
- Any action parameter modified after S-Class authorization fails closed (action hash mismatch).
- Missing, ambiguous, or corrupt security state fails closed immediately.
