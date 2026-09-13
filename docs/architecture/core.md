# S-Class Core Architecture

## 1. Overview & Trust Control Plane

S-Class transitions autonomous software development from an architectural scaffold into a **Real Trust Control Plane**. 

The fundamental security invariant of S-Class is:
> **An agent must not be able to manufacture the evidence S-Class uses to certify its own claims.**

To achieve this, S-Class operates an independent observation and verification control plane that decouples agent intent from execution reality.

```text
Agent / IDE
    ↓
Action Request
    ↓
Authorization (Policy Engine)
    ↓
Actual Execution (Process Runner)
    ↓
Actual Process Identity (OS Kernel Inspection)
    ↓
Independent Observation (Observation Runtime)
    ↓
Evidence Receipt (Cryptographically Sealed)
    ↓
Verifier (Independent Result Parsing)
    ↓
Claim Assessment (Acceptance Matrix)
    ↓
Verified Project State (Tamper-evident Ledger)
    ↓
Cross-Agent Handoff
```

## 2. Non-Negotiable Architectural Invariants

1. **Agent input is never authoritative**:
   - `ActionRequest` is a request, not an event.
   - Evidence receipts are only emitted by the S-Class observation runtime.
   - Claims are hypotheses until validated by independent verifiers against immutable evidence.
2. **Observation must be independent of the observed**:
   - The runtime observes process exit codes, stdout/stderr, execution duration, and workspace diffs directly from the OS process lifecycle.
   - Test counts and verifier outputs are parsed from raw stdout/stderr by registered verifier plugins, never supplied by the agent.
3. **Execution identity is verified, not declared**:
   - The exact binary path, executable SHA-256 hash, true child PID, and execution chain are captured via OS kernel calls (`ctypes` on Windows, `/proc` on Linux).
   - Wrapper executables, symlinks, and junctions are resolved to their target images.
4. **Trust state is tamper-evident and append-only**:
   - State transitions and evidence receipts are appended to a cryptographic hash chain ledger.
   - In-memory receipts are sealed against attribute mutation.
   - Any corruption or manual edit of ledger events is detected and triggers repair or reset.
5. **Claims require mandatory minimum evidence**:
   - Claims are categorized (`test_pass`, `typecheck`, `lint`, `security`, `behavior`, `feature`, etc.).
   - Claims cannot be satisfied by irrelevant or generic command executions (`EXECUTION_VERIFIED != CLAIM_VERIFIED`).
   - Claim scopes strictly enforce target file and test path coverage.
