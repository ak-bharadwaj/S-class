# FSM Recovery & Self-Healing Loop

When test suites or validation checks fail, the S-Class engine enters the `RECOVERY` state to analyze and construct a clean patch strategy instead of immediately coding.

---

## 1. Recovery State Loop Flow

```
 [ QA / Verification Failed ]
              │
              ▼
  [ Transition to RECOVERY ]
              │
              ▼
  [ Inspect Logs & Stack Traces ]
              │
              ▼
  [ Classify Root Cause ]
              │
              ▼
  [ Compile Failure Report & Patch Tasks ]
              │
              ▼
  [ Assign Tasks & Transition to CODING ]
```

---

## 2. Failure Report & Patch Schema
The recovery processor structures a standard Failure Report:
*   **Failed Files:** Array of source code files triggering errors.
*   **Error Class:** Category (e.g. `SyntaxError`, `Regression`, `AssertionFailure`, `APIContractMismatch`).
*   **Stack Trace Snippet:** Truncated logs pointing to the bug.
*   **Root Cause Hypothesis:** Structural analysis of why the bug occurred.
*   **Patch Tasks:** Ordered tasks assigned to `dss_builder_v2` with specific acceptance criteria.

---

## 3. Loop Safeguards
*   **Retry Limit:** Exits and escalates to the user after 5 failed loop retries.
*   **No Progress Check:** If successive runs yield identical test pass rates and output logs, execution stops and escalates for manual clarification.
