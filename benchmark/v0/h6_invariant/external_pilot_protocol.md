# External Developer Pilot Protocol Specification: S-Class Verification Layer

**Version**: 1.0  
**Target Sample**: 3–5 Independent External Senior Software Engineers  
**Primary Research Goal**: Determine whether S-Class semantic governance provides measurable developer value and reduces missed constraints in real-world engineering workflows over plain agent + pytest loops.

---

## 1. Study Design & Baseline Comparison

Each participating engineer will complete 4 production-like software engineering tasks under two randomized treatment conditions:

- **Condition A (B2)**: Plain Agent + Pytest Test Repair Loop
- **Condition B (B4)**: Agent + S-Class Semantic Governance + Pytest Test Repair Loop

---

## 2. Developer Measurement Protocol

For each task completed by an external developer, the pilot framework captures:

| Metric | Measurement Unit | Developer Collection Method |
| :--- | :--- | :--- |
| **Missed Constraints Caught** | Count | Automated log diff + developer audit check |
| **Developer Review Effort** | Likert Scale (1–5) | Post-task survey (1 = Effortless, 5 = High Friction) |
| **False Alarms vs Useful Catches** | Ratio | Developer inline classification |
| **Review Time Added** | Seconds | Active IDE timer tracking |
| **Silent Invariant Violations** | Count | Code review audit of tests vs preserved invariants |

---

## 3. Post-Task Qualitative Interview Questions

1. *"Did S-Class catch any critical engineering constraints or edge cases that your unit test suite failed to catch?"*
2. *"Did the S-Class specification synthesis and epistemic gate clarify ambiguous requirements or add friction?"*
3. *"Would you deploy S-Class in production for high-risk security/compliance repositories?"*
