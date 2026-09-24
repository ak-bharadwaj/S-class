# S-Class Cross-Plane Contract

## 1. The Three Planes of S-Class

S-Class operates across three strictly delineated planes:

```text
                    S-CLASS
              AUTHORITY / TRUTH PLANE
                       │
             ┌─────────┴─────────┐
             │                   │
             ▼                   ▼
        Runtime Plane       Evolution Plane
        Step-Code            RRSI
             │                   │
             └─────────┬─────────┘
                       ▼
              Independent Evidence
                       │
                       ▼
              S-Class Verification
                       │
                       ▼
                Canonical Truth
```

1. **Authority / Truth Plane (S-Class)**:
   - Supreme authority over project truth.
   - Decides: `AUTHORIZED`, `OBSERVED`, `VERIFIED`, `SATISFIED`, `ACCEPTED`, `COMPLETED`.
   - Manages cryptographic HMAC dual-layer authorization, sensory observation receipts, state reduction, and completion adjudication.
2. **Runtime Plane (Step-Code Substrate)**:
   - Operational execution engine.
   - Executes authorized tool calls, runs subprocesses, manages worker lanes and subagents.
   - Emits untrusted execution facts and stdio streams.
3. **Evolution Plane (RRSI Substrate)**:
   - Offline search, candidate proposal, critic filtering, benchmark evaluation, and Pareto frontier optimization.
   - Operates in isolated Git worktrees.
   - Emits untrusted candidate evaluation evidence.

---

## 2. Invariant Rules Governing Cross-Plane Interactions

| Rule ID | Cross-Plane Boundary | Invariant Enforcement |
| :--- | :--- | :--- |
| **CP-1** | Runtime -> Truth | Runtime reporting `status: SUCCESS` or `exit_code: 0` is classified as `UNTRUSTED_CANDIDATE`. It cannot satisfy obligations or close tasks without independent S-Class sensory verification. |
| **CP-2** | Evolution -> Truth | RRSI accepting a candidate marks an evolution-plane milestone only. It cannot alter canonical project obligations or mark software requirements satisfied. |
| **CP-3** | Evolution -> Trust Kernel | Evolution candidates attempting to modify Trust Kernel files (`src/sclass/trust/`, `src/sclass/security/`, `src/sclass/control/`) or components (`authorization`, `evidence`) are rejected by the pre-eval Critic. |
| **CP-4** | Parent -> Child Lane | Child lanes receive explicitly bounded delegation (tools, budget, task scope). Child lanes never inherit parent authority and cannot certify their own evidence. |
| **CP-5** | Runtime -> Permission | Step-Code permission ALLOW cannot override S-Class authorization DENY. S-Class authorization ALLOW cannot override Step-Code permission DENY. |
| **CP-6** | Evolution -> Evaluation | Infrastructure failure (`INVALID_INFRA`) allows selective remeasurement. Candidate failure (`FAIL`) is immutable negative evidence and cannot be erased. |

---

## 3. Evidence Promotion Flow

```text
   External Tool / Candidate Run
                 ↓
     UNTRUSTED CANDIDATE SIGNAL
                 ↓
    Independent Sensory Observer (Filesystem / Git / Process)
                 ↓
         Evidence Receipt (SHA-256 Hashes)
                 ↓
       Typed Independent Verifier
                 ↓
          EvolutionAssessment / Claim State
                 ↓
       S-Class Canonical Assurance Ledger
```
