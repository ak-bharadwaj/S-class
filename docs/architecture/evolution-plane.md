# S-Class Evolution Plane Architecture

## 1. Executive Summary & Epistemic Separation

The **Evolution Plane** is the offline harness-optimization and search substrate of S-Class.
It harvests the deep search and evaluation mechanics of **RRSI** (Apache License 2.0, Google LLC):
- Hypothesis-driven structural candidate generation
- Edit-budget annealing from broad exploration to single-edit attribution
- Pre-evaluation deterministic and heuristic critic gates
- Fast smoke verification gates
- Repeated benchmark evaluations ($k$ trials with fixed denominator scoring)
- Empirical noise calibration (variance estimation on baseline runs)
- Multi-objective Pareto selection with non-compensatory domain guards
- Out-of-distribution (OOD) and held-out domain evaluation partitions
- Offline readjudication without re-running compute
- Selective infrastructure reevaluation

### Foundational Invariant
> **RRSI candidate acceptance != S-Class project truth.**
> Evolution candidate scores are empirical signals on the evolution plane. An accepted candidate only updates the evolution-plane frontier; it can never modify project truth or bypass S-Class completion adjudication.

---

## 2. Evolution Substrate Architecture

The evolution substrate is implemented under `src/sclass/evolution/`:

```text
               EvolutionEngine (src/sclass/evolution/engine.py)
                                     │
       ┌──────────────┬──────────────┼──────────────┬──────────────┐
       ▼              ▼              ▼              ▼              ▼
   Domain          Critic          Smoke        Evaluator       Selector
 (domain.py)    (critic.py)    (evaluator.py) (evaluator.py)  (selector.py)
       │              │              │              │              │
       └──────────────┴──────────────┼──────────────┴──────────────┘
                                     │
                     ┌───────────────┴───────────────┐
                     ▼                               ▼
             Evolution History               Attribution Ledger
               (history.py)                   (attribution.py)
```

---

## 3. Trust Kernel Immutability (Section 36)

To prevent optimizer collapse and self-serving benchmark hacking, the **Trust Kernel** is explicitly marked **NON-EVOLVABLE**:
- `authorization` (dual-layer authorizer, HMAC verification)
- `evidence` (sensory receipts, content hashes)
- `canonical_truth` (project state reducer, completion evaluator)
- `ledger_integrity` (hash-chained append-only logs)

The critic strictly rejects any candidate whose edits or hypotheses touch non-evolvable components.

---

## 4. Multi-Objective Selection & Domain Guards

Selection is never decided solely on benchmark score. A candidate is admissible if and only if:
1. **Quality Gain**: $\Delta S \ge \text{Noise Floor}$ (exceeds empirically calibrated variance).
2. **Cost Discipline**: $\Delta C$ stays within budgeted token/cost limits.
3. **Domain Guards**: Non-compensatory constraints are satisfied:
   - Valid execution rate $\ge 95\%$
   - Security failures $= 0$
   - Completion bypass attempts $= 0$
   - Crash rate $\le 2\%$
   - Latency $\le 5000\text{ ms}$

---

## 5. Domain Partitions & Generalization

Evaluation is strictly partitioned across orthogonal benchmark splits:
- `D_evolve`: In-distribution search set
- `D_holdout`: Unseen generalization set
- `D_adversarial`: Edge-case and tamper-resistance set
- `D_security`: Cryptographic authorization boundary set
- `D_recovery`: Crash recovery and bounded retry set
- `D_runtime`: Protocol parity and tool call correctness set

A candidate that improves `D_evolve` but regresses on `D_holdout` or `D_security` is rejected.
