# Upstream Integration Threat Model & Security Matrix

## 1. Threat Model Scope

This threat model analyzes adversarial vectors introduced by integrating:
1. **Step-Code** execution substrate (out-of-process subprocesses, tool executions, subagent concurrency).
2. **RRSI** evolution substrate (autonomous code modification, benchmark execution, candidate search).

---

## 2. Threat Analysis & Mitigation Matrix

| Threat ID | Adversarial Vector | Attack Mechanism | S-Class Mitigation & Defense |
| :--- | :--- | :--- | :--- |
| **TH-01** | **Runtime Narrative Forgery** | Agent returns `All tests passed!` in message text or exit code 0 without executing tests. | **CompletionEvaluator Independent Adjudication**: Narrative is ignored. Completion requires verified claims backed by fresh sensory receipts. |
| **TH-02** | **Post-Authorization Tampering** | Tool parameters modified after S-Class authorization grant. | **Action Hash Binding**: ActionRequest parameter hash signed in decision token. Runtime verifies parameter hash matches authorized hash before dispatch. |
| **TH-03** | **Trust Kernel Self-Modification** | RRSI generates candidate mutating HMAC verification or authorization rules to inflate score. | **Pre-Eval Critic & Non-Evolvable Boundary**: Critic scans diffs for protected paths and non-evolvable components (`authorization`, `evidence`, `canonical_truth`). |
| **TH-04** | **Subagent Authority Escalation** | Child subagent attempts to certify obligations or spawn unbudgeted workers. | **Strict Non-Delegation of Authority**: Subagent lanes receive explicit tools and budgets only. Subagent replies are sanitized to untrusted candidates. |
| **TH-05** | **Destructive Mutation Replay** | Crash recovery automatically replays file deletions or external network calls. | **Explicit ReplayClass**: `NEVER` operations fail closed immediately on crash recovery and are forbidden from automated re-execution. |
| **TH-06** | **Infinite Self-Healing Loop** | Flaky tool continuously retrying and burning API budgets without termination. | **Bounded Recovery Ladder**: Maximum attempt limits (3 retries) and lane budget exhaustion checks enforce strict termination. |
| **TH-07** | **Benchmark Leakage / Oracle Abuse** | Evolution candidate reads hidden benchmark solutions from test fixtures. | **Critic Leakage Scanner**: Critic rejects diffs containing oracle references or test modifications. |
| **TH-08** | **Infrastructure Flake Masquerading** | Candidate crashes due to logic bug but claims infrastructure failure to obtain remeasurement. | **Explicit Diagnostic Proof**: `INVALID_INFRA` requires logged pipe/timeout proof. Unverified errors remain candidate failures. |

---

## 3. Defense-in-Depth Layering

```text
       Layer 1: Pre-Execution Critic Gate (Blocks forbidden edits)
                          ↓
       Layer 2: Dual-Layer Authorization (S-Class HMAC + Runtime Heuristics)
                          ↓
       Layer 3: 5-Way Conjunction Engine (Fail-closed on any denial)
                          ↓
       Layer 4: Durable Effect Boundary (TX1 -> EFFECT -> TX2)
                          ↓
       Layer 5: Independent Sensory Observers (Physical filesystem & git diffs)
                          ↓
       Layer 6: Typed Evidence Verification (No unverified claim promotion)
                          ↓
       Layer 7: Independent Completion Evaluator (Pure epistemic closure)
```
